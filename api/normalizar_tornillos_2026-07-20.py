# -*- coding: utf-8 -*-
"""
Normaliza precios_historicos de tornillos T00x a PRECIO POR UNIDAD
(regla de Pablo 20-07-2026). Clasifica cada fila por ID:

  KEEP    : precio < UMBRAL_UNIDAD → ya viene por unidad.
  CONVERT : pack conocido → precio/pack.
            pack se toma de (a) texto ("BOLSA X 100","x 100 un","X 500",
            "CAJA X 10.000"), (b) unidad="caja N", o (c) precio > 100.000 =
            caja entera → ÷ factor del maestro.
  DELETE  : rango medio sin info de pack (caja parcial ambigua) → no confiable.

Backup completo antes. Dry-run por defecto; --apply ejecuta.
"""
import os, sys, re, json
from collections import defaultdict
from supabase import create_client

APPLY = "--apply" in sys.argv
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY"))
DATA = os.path.join(os.path.dirname(__file__), "data"); STAMP = "2026-07-20"

FAC = {"T001":4000,"T002":10000,"T003":10000,"T004":8000,"T006":5000,"T009":3500,"T010":8000,"T012":6500}
UMBRAL_UNIDAD = 100.0     # precio < 100 → ya por unidad
UMBRAL_CAJA   = 100000.0  # precio > 100.000 sin pack → caja entera (÷factor)

def pg(t):
    o,d,p=[],0,1000
    while True:
        r=sb.table(t).select("*").range(d,d+p-1).execute();x=r.data or [];o.extend(x)
        if len(x)<p:break
        d+=p
    return o

items = pg("presupuesto_items")
itx = defaultdict(list)
for it in items: itx[it.get("codigo_material")].append(it)
def texto_para(cod, precio):
    for it in itx.get(cod,[]):
        if abs((it.get("precio") or 0)-precio) < max(1.0,0.02*precio):
            return it.get("texto_original") or ""
    return ""

_RE_PACK = re.compile(r"[xX]\s*(\d{1,3}(?:[.,]\d{3})+|\d{2,})")
def pack_de_texto(txt):
    packs = [int(re.sub(r"[.,]","",m)) for m in _RE_PACK.findall(txt or "")]
    packs = [n for n in packs if n >= 100]
    return max(packs) if packs else None
def pack_de_unidad(u):
    m = re.search(r"caja\s*(\d[\d.,]*)", str(u or ""), re.I)
    return int(re.sub(r"[.,]","",m.group(1))) if m else None

ph = pg("precios_historicos")
keep, convert, delete, bkp = [], [], [], []
for r in ph:
    cod = r.get("codigo_material")
    if cod not in FAC: continue
    bkp.append(r)
    precio = r.get("precio") or 0
    fac = FAC[cod]
    if precio < UMBRAL_UNIDAD:
        keep.append(r); continue
    txt = texto_para(cod, precio)
    # unidad="caja N" tiene PRIORIDAD: si la fila ya fue normalizada a la caja,
    # el precio es por-caja-N sin importar lo que diga el texto original
    # (ej. Insuma "x 100 un" ya quedó ×100 en "caja 10.000" → ÷10.000, no ÷100).
    pack_u = pack_de_unidad(r.get("unidad"))
    pack = pack_u or pack_de_texto(txt)
    metodo = None
    if pack:
        metodo = f"{'unidad caja' if pack_u else 'texto'} pack {pack}"
    elif precio > UMBRAL_CAJA:
        pack = fac; metodo = f"caja entera ÷{fac}"
    if pack:
        nuevo = round(precio / pack, 4)
        convert.append((r, nuevo, pack, metodo, txt))
    else:
        delete.append((r, txt))

print(f"=== NORMALIZAR TORNILLOS {STAMP} — {'APPLY' if APPLY else 'DRY-RUN'} ===")
print(f"KEEP (ya por unidad): {len(keep)} | CONVERT: {len(convert)} | DELETE (ambiguo): {len(delete)}\n")
print("-- CONVERT --")
for r, nuevo, pack, metodo, txt in sorted(convert, key=lambda x:(x[0]['codigo_material'], x[1])):
    print(f"  {r['codigo_material']} {str(r.get('proveedor'))[:15]:15} {r.get('precio'):>11} ÷{pack:<6} = {nuevo:>8.3f}/u [{metodo}] {str(txt)[:34]}")
print("\n-- DELETE (ambiguo, sin pack) --")
for r, txt in sorted(delete, key=lambda x:(x[0]['codigo_material'], x[0].get('precio') or 0)):
    print(f"  {r['codigo_material']} {str(r.get('proveedor'))[:15]:15} {r.get('precio'):>11} cant={r.get('cantidad')} {str(txt)[:34]}")

# resumen rango por codigo tras normalizar (keep + convert)
print("\n-- Rango POR UNIDAD resultante por código --")
res = defaultdict(list)
for r in keep: res[r['codigo_material']].append(r.get('precio'))
for r, nuevo, *_ in convert: res[r['codigo_material']].append(nuevo)
for cod in sorted(res):
    v = sorted(res[cod]); print(f"  {cod}: {len(v)} filas | ${v[0]:.2f} – ${v[-1]:.2f}/u")

if not APPLY:
    print("\nDRY-RUN: nada escrito. Correr con --apply."); sys.exit(0)

with open(os.path.join(DATA, f"backup_tornillos_normalizados_{STAMP}.json"), "w", encoding="utf-8") as f:
    json.dump({"convert":[{"id":r["id"],"nuevo_precio":nuevo,"pack":pack} for r,nuevo,pack,_,_ in convert],
               "delete":[r["id"] for r,_ in delete], "filas":bkp}, f, ensure_ascii=False, indent=1, default=str)

for r, nuevo, pack, metodo, txt in convert:
    sb.table("precios_historicos").update({
        "precio": nuevo, "unidad": "UN",
        "conversion_aplicada": f"a precio por unidad (÷{pack}) 20-07",
    }).eq("id", r["id"]).execute()
for r, txt in delete:
    sb.table("precios_historicos").delete().eq("id", r["id"]).execute()
print(f"\nAPLICADO: convert={len(convert)} delete={len(delete)} keep(sin tocar)={len(keep)}")
