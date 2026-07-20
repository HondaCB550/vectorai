# -*- coding: utf-8 -*-
"""
Aplica el modelo de unidad decidido por Pablo (20-07-2026):
  - TORNILLOS T00x → canónico POR UNIDAD: conversion_unidades.unidad_base='UN'
    para todos los códigos de tornillo por pack (factor = tamaño de caja del
    maestro, usado solo para detectar la caja entera en el texto).
  - CHAPAS → canónico POR METRO LINEAL, separadas por tipo: se agregan filas
    conversion_unidades modo 'ml' para los códigos de chapa por metro.
  - CHAPA DATA: re-tipar precios_historicos de CH001 (galvanizada) que en
    realidad son CINCALUM (→ CH019) + sacar aliases cincalum de CH001.

Todo por IDs explícitos, backup antes. Dry-run por defecto; --apply ejecuta.
"""
import os, sys, json
from supabase import create_client

APPLY = "--apply" in sys.argv
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY"))
DATA = os.path.join(os.path.dirname(__file__), "data"); STAMP = "2026-07-20"

# Packs del maestro (para detectar caja entera en el texto)
TORNILLOS = {"T001":4000,"T002":10000,"T003":10000,"T004":8000,"T006":5000,"T009":3500,"T010":8000,"T012":6500}
CHAPAS_ML = ["CH001","CH009","CH010","CH019","CH020","CH021"]

# Chapa data: re-tipar CH001 (galvanizada) → en realidad cincalum (CH019)
CH_BORRAR_DUP = [   # duplican una fila que YA existe en CH019
    ("ec0713c5-0e56-4c11-9e36-891a0fc33daa","CH001","CAROSIO",12892.91),
    ("c174edff-d820-472d-a0ab-0b978c641a75","CH001","SAUCE",13601.06),
]
CH_REPUNTAR_CH019 = [  # cincalum real, no duplicado → mover a CH019
    ("54a22c5c-4867-415d-ab30-4830c28d114f","CH001","BAUKRAFT",15720.91),
]
CH_ALIAS_BORRAR = [  # aliases cincalum en CH001 (CH019 ya tiene equivalentes)
    ("7abeef1b-1e62-4a1e-adba-c9c9606fb5c3","CH001","chapa cincalum c25 acan x 1,00 mts"),
    ("23f61405-1227-47c3-8538-ac80366c4430","CH001","chapa cincalum c25 0,5 x ml"),
    ("73b956d4-aed3-4ec6-8064-b67437168130","CH001","chapa c25 acanalada cincalum x m"),
]

def get_ph(pid):
    r = sb.table("precios_historicos").select("*").eq("id", pid).execute()
    return r.data[0] if r.data else None
def get_alias_id(aid):
    r = sb.table("material_denominaciones").select("*").eq("id", aid).execute()
    return r.data[0] if r.data else None

print(f"=== MODELO DE UNIDAD {STAMP} — {'APPLY' if APPLY else 'DRY-RUN'} ===\n")

# 1) conversion_unidades actual
conv = sb.table("conversion_unidades").select("*").execute().data or []
conv_por_cod = {c["codigo_material"]: c for c in conv}
upd_conv, ins_conv = [], []
for cod, fac in TORNILLOS.items():
    c = conv_por_cod.get(cod)
    if c and (c.get("unidad_base") != "UN" or c.get("unidad_comercial") != "un" or c.get("factor") != fac):
        upd_conv.append((c["id"], cod, fac))
    elif not c:
        ins_conv.append({"codigo_material":cod,"unidad_comercial":"un","factor":fac,"unidad_base":"UN","activo":True})
for cod in CHAPAS_ML:
    c = conv_por_cod.get(cod)
    if not c:
        ins_conv.append({"codigo_material":cod,"unidad_comercial":"ml","factor":1,"unidad_base":"ML","activo":True})
    elif c.get("unidad_comercial") != "ml":
        upd_conv.append((c["id"], cod, 1))  # forzar modo ml (unidad_base ML)

print(f"conversion_unidades → update: {len(upd_conv)} | insert: {len(ins_conv)}")
for _id, cod, fac in upd_conv: print(f"   UPD {cod} (id={_id}) factor={fac}")
for r in ins_conv: print(f"   INS {r['codigo_material']} modo={r['unidad_comercial']} factor={r['factor']} base={r['unidad_base']}")

# 2) chapa data — verificar
ch_del, ch_rep, ch_al_del, ch_bkp, probs = [], [], [], [], []
for pid, cod, prov, precio in CH_BORRAR_DUP:
    row = get_ph(pid)
    if not row or row.get("codigo_material")!=cod or prov.upper() not in str(row.get("proveedor","")).upper() or abs((row.get("precio") or 0)-precio)>1:
        probs.append(f"CH del {pid}: no coincide/no existe"); continue
    ch_bkp.append(row); ch_del.append(pid)
for pid, cod, prov, precio in CH_REPUNTAR_CH019:
    row = get_ph(pid)
    if not row or row.get("codigo_material")!=cod or prov.upper() not in str(row.get("proveedor","")).upper() or abs((row.get("precio") or 0)-precio)>1:
        probs.append(f"CH rep {pid}: no coincide/no existe"); continue
    ch_bkp.append(row); ch_rep.append(pid)
for aid, cod, den in CH_ALIAS_BORRAR:
    a = get_alias_id(aid)
    if not a or a.get("codigo_material")!=cod or a.get("denominacion")!=den:
        probs.append(f"CH alias {aid}: no coincide/no existe"); continue
    ch_bkp.append(a); ch_al_del.append(aid)

print(f"\nchapa precios → borrar dup: {len(ch_del)} | re-apuntar CH019: {len(ch_rep)} | aliases borrar: {len(ch_al_del)}")
for r in ch_bkp:
    if "denominacion" in r: print(f"   ALIAS DEL {r['id']} @ {r.get('codigo_material')} :: {r.get('denominacion')}")
    else:
        acc = "REPUNTAR→CH019" if r["id"] in ch_rep else "BORRAR(dup)"
        print(f"   {acc:15} {r['id']} {str(r.get('proveedor'))[:16]:16} precio={r.get('precio')} cod={r.get('codigo_material')}")
if probs:
    print("\n[!] AVISOS:"); [print("   -",p) for p in probs]

if not APPLY:
    print("\nDRY-RUN: nada escrito. Correr con --apply."); sys.exit(0)

# Backup
with open(os.path.join(DATA, f"backup_modelo_unidad_{STAMP}.json"), "w", encoding="utf-8") as f:
    json.dump({"conv_update":[u[0] for u in upd_conv], "conv_insert":ins_conv,
               "chapa_borrar":ch_del, "chapa_repuntar":ch_rep, "alias_borrar":ch_al_del,
               "filas":ch_bkp}, f, ensure_ascii=False, indent=1, default=str)

# Aplicar conversion_unidades
for _id, cod, fac in upd_conv:
    modo = "ml" if cod in CHAPAS_ML else "un"
    base = "ML" if modo=="ml" else "UN"
    sb.table("conversion_unidades").update({"unidad_comercial":modo,"factor":fac,"unidad_base":base}).eq("id",_id).execute()
if ins_conv:
    sb.table("conversion_unidades").insert(ins_conv).execute()
# Aplicar chapa
for pid in ch_del: sb.table("precios_historicos").delete().eq("id", pid).execute()
for pid in ch_rep: sb.table("precios_historicos").update({"codigo_material":"CH019"}).eq("id", pid).execute()
for aid in ch_al_del: sb.table("material_denominaciones").delete().eq("id", aid).execute()

print(f"\nAPLICADO: conv upd={len(upd_conv)} ins={len(ins_conv)} | chapa del={len(ch_del)} rep={len(ch_rep)} alias_del={len(ch_al_del)}")
