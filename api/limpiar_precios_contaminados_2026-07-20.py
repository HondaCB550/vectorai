# -*- coding: utf-8 -*-
"""
Limpieza de precios_historicos + material_denominaciones contaminados (20-07-2026).
Detectado armando el Índice de canasta representativa.

Alcance (decisión Pablo 20-07): cemento (CONS101), hierro aleteado Ø12 (CONS118),
chapa sinusoidal C25 (CH001). Tornillos T00x → revisión aparte, NO se tocan acá.

Acciones POR IDs EXPLÍCITOS (nunca predicado amplio):
  precios_historicos:
    - RE-APUNTAR a CONS129 (cemento blanco): 6 filas hoy en CONS101 que son
      "CEMENTO BLANCO CIMSA / BCO PINGUINO" (producto real, código equivocado).
    - BORRAR: 7 filas no-cemento en CONS101 (placa cementicia ×6, basecoat ×1);
      6 filas de varilla roscada Fischer en CONS118; 11 filas de chapa entera
      (off-base por metro) en CH001.
  material_denominaciones (fix reproducibilidad en vivo):
    - RE-APUNTAR a CONS129: aliases de cemento blanco.
    - BORRAR: aliases de productos distintos (placa, basecoat, varilla roscada,
      upn/ipn, chapa entera).

Backups a api/data/backup_*_2026-07-20.json ANTES de cualquier escritura.
Uso:  railway run python limpiar_precios_contaminados_2026-07-20.py           (dry-run)
      railway run python limpiar_precios_contaminados_2026-07-20.py --apply   (ejecuta)
"""
import os, sys, json, datetime
from supabase import create_client

APPLY = "--apply" in sys.argv
URL = os.getenv("SUPABASE_URL"); KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
if not URL or not KEY:
    sys.exit("Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY")
sb = create_client(URL, KEY)
DATA = os.path.join(os.path.dirname(__file__), "data")
STAMP = "2026-07-20"

# ── precios_historicos ────────────────────────────────────────────────────────
# (id, codigo_actual_esperado, proveedor_contiene, precio_aprox)  — para verificar
PH_REPUNTAR_CONS129 = [  # cemento blanco: código equivocado, producto real
    ("825acfcf-45bc-4bdb-8b8f-1eb46a52f554", "CONS101", "LAPRIDA", 39900.0),
    ("fcc1b337-bcf9-465c-a398-f8bc2307f5f9", "CONS101", "LAPRIDA", 39900.0),
    ("422624b6-3693-41c7-9f31-15599805ebfe", "CONS101", "NUEVO PILAR", 42352.94),
    ("9b089349-5579-4ec6-b725-c658a68a64da", "CONS101", "NUEVO PILAR", 42352.94),
    ("4f744384-0183-4311-b9b2-fc7ae6181767", "CONS101", "SAN RAFAEL", 60850.62),
    ("6d2b5a62-2e0e-47df-9586-76947daccef1", "CONS101", "SAN RAFAEL", 60850.62),
]
PH_BORRAR = [  # producto distinto sin código destino claro → borrar
    # CONS101 no-cemento (placa cementicia + basecoat)
    ("28586690-53d7-4fec-af6c-4996bf39a8d4", "CONS101", "BAUKRAFT", 39588.94),   # basecoat weber
    ("22bd3e58-ccea-414e-9343-c343bf65e534", "CONS101", "EN SECO", 45358.28),    # placa volcanboard
    ("d4375bbe-c590-4123-92e7-def53af46ba6", "CONS101", "EN SECO", 50679.64),
    ("42ffaf51-2ef5-431c-a1aa-b057e59558b9", "CONS101", "EN SECO", 50679.64),
    ("840c3a53-3d13-4953-b944-772af35b2bfb", "CONS101", "EN SECO", 50679.64),
    ("0bb077ca-2d7d-420c-9e2a-af7d9ce972fc", "CONS101", "EN SECO", 50679.64),
    ("308393db-60cc-489f-89bf-7843caeef434", "CONS101", "EN SECO", 50679.64),
    # CONS118 varilla roscada Fischer (no es hierro aleteado)
    ("76bf4ab6-d614-4845-b18d-4daf4ce36753", "CONS118", "MADERERA LOBOS", 2815.42),
    ("1827fa86-e4ac-4610-be9b-b8e867944180", "CONS118", "MADERERA LOBOS", 2815.42),
    ("78d0fce6-6332-4c47-8427-f42d294d925f", "CONS118", "EN SECO", 3894.05),
    ("1b43ddfc-3b4b-485a-a43f-84a90a61ec60", "CONS118", "EN SECO", 3894.05),
    ("03070c6e-c985-4bfa-88f6-59e1143e746c", "CONS118", "EN SECO", 3894.05),
    ("3b34c201-7c19-4be3-a153-97cba4db0d1f", "CONS118", "EN SECO", 3894.05),
    # CH001 chapa entera 6m (off-base: material es por metro)
    ("4c00c80c-1c22-4629-bd5a-c5b26d56eee1", "CH001", "J.M. Landa", 80633.48),
    ("96485db5-5555-4fa1-9539-c353c66fca74", "CH001", "J.M. Landa", 80633.48),
    ("24e3bf57-12db-49ba-bec4-fa0f717aa31f", "CH001", "CAROSIO", 87617.41),
    ("47bccd48-2af6-4b9f-8a3a-e4e0c415cadb", "CH001", "CAROSIO", 87617.41),
    ("a898b2dd-3df5-464d-b87c-625a8c0e95b1", "CH001", "CAROSIO", 96817.24),
    ("9dba535f-0277-4c72-ab4d-60505d84e678", "CH001", "CAROSIO", 96817.24),
    ("b5114df0-6c46-4776-b909-df77b18aab41", "CH001", "CAROSIO", 96817.24),
    ("b4269548-34b3-48f3-bc05-aad3315243bf", "CH001", "CAROSIO", 96817.24),
    ("7a83b61a-d8ed-47d7-b2f7-daf18e8e678a", "CH001", "CAROSIO", 96817.24),
    ("bac21f06-ce17-4a6e-ac86-dc82d8c89696", "CH001", "CAROSIO", 96817.24),
    ("60445e2f-0365-43fb-bc13-de07d5d95551", "CH001", "CAROSIO", 96817.24),
]

# ── material_denominaciones (por codigo + denominacion exacta) ─────────────────
AL_REPUNTAR_CONS129 = [  # cemento blanco: alias válido, código equivocado
    ("CONS101", "cemento blanco cimsa x 25 kg"),
    ("CONS101", "cemento bco x 25 kg pinguino"),
]
AL_BORRAR = [  # productos distintos: no deben quedar en el pool
    ("CONS101", "placa cementicia volcanboard 8mm 1200 x 2400mm*"),
    ("CONS101", "basecoat saint gobain weber x 25kg"),
    ("CONS118", "varilla roscada fischer ftr 12 x 160"),
    ("CONS118", "fischer fijacion quimica varilla roscada ftr 12"),
    ("CONS118", "hierro upn 12"),
    ("CONS118", "hierro ipn 12"),
    ("CH001", "chapa acan polip x 6 ml"),
    ("CH001", "chapa aca polip x 6 mt"),
]

def get_ph(pid):
    r = sb.table("precios_historicos").select("*").eq("id", pid).execute()
    return r.data[0] if r.data else None

def get_alias(cod, den):
    r = sb.table("material_denominaciones").select("*").eq("codigo_material", cod).eq("denominacion", den).execute()
    return r.data or []

print(f"=== LIMPIEZA precios contaminados {STAMP} — {'APPLY' if APPLY else 'DRY-RUN'} ===\n")

# 1) Resolver y verificar precios_historicos
ph_repuntar, ph_borrar, ph_backup, problemas = [], [], [], []
for pid, cod_esp, prov_esp, precio_esp in PH_REPUNTAR_CONS129:
    row = get_ph(pid)
    if not row: problemas.append(f"PH {pid}: NO EXISTE (¿ya limpiado?)"); continue
    ok = row.get("codigo_material")==cod_esp and prov_esp.upper() in str(row.get("proveedor","")).upper() and abs((row.get("precio") or 0)-precio_esp)<1
    if not ok: problemas.append(f"PH {pid}: no coincide (cod={row.get('codigo_material')} prov={row.get('proveedor')} precio={row.get('precio')})"); continue
    ph_backup.append(row); ph_repuntar.append(pid)
for pid, cod_esp, prov_esp, precio_esp in PH_BORRAR:
    row = get_ph(pid)
    if not row: problemas.append(f"PH {pid}: NO EXISTE (¿ya limpiado?)"); continue
    ok = row.get("codigo_material")==cod_esp and prov_esp.upper() in str(row.get("proveedor","")).upper() and abs((row.get("precio") or 0)-precio_esp)<1
    if not ok: problemas.append(f"PH {pid}: no coincide (cod={row.get('codigo_material')} prov={row.get('proveedor')} precio={row.get('precio')})"); continue
    ph_backup.append(row); ph_borrar.append(pid)

# 2) Resolver y verificar aliases
al_repuntar, al_borrar, al_backup = [], [], []
for cod, den in AL_REPUNTAR_CONS129:
    filas = get_alias(cod, den)
    if len(filas)!=1: problemas.append(f"ALIAS repuntar '{den}' @ {cod}: {len(filas)} coincidencias (esperaba 1)"); continue
    al_backup.append(filas[0]); al_repuntar.append(filas[0]["id"])
for cod, den in AL_BORRAR:
    filas = get_alias(cod, den)
    if len(filas)!=1: problemas.append(f"ALIAS borrar '{den}' @ {cod}: {len(filas)} coincidencias (esperaba 1)"); continue
    al_backup.append(filas[0]); al_borrar.append(filas[0]["id"])

print(f"precios_historicos → re-apuntar a CONS129: {len(ph_repuntar)} | borrar: {len(ph_borrar)}")
print(f"material_denominaciones → re-apuntar a CONS129: {len(al_repuntar)} | borrar: {len(al_borrar)}")
if problemas:
    print("\n[!] AVISOS (se saltan, no se actúa sobre ellos):")
    for p in problemas: print("   -", p)

if not APPLY:
    print("\nDRY-RUN: no se escribió nada. Revisá y corré con --apply.")
    print("Detalle filas precios a re-apuntar/borrar:")
    for r in ph_backup:
        accion = "REPUNTAR→CONS129" if r["id"] in ph_repuntar else "BORRAR"
        print(f"   [{accion:16}] {r['id']} {str(r.get('proveedor'))[:20]:20} cod={r.get('codigo_material')} precio={r.get('precio')} cant={r.get('cantidad')}")
    for a in al_backup:
        accion = "REPUNTAR→CONS129" if a["id"] in al_repuntar else "BORRAR"
        print(f"   [{accion:16}] alias {a['id']} @ {a.get('codigo_material')} :: {a.get('denominacion')}")
    sys.exit(0)

# 3) Backups (antes de escribir)
with open(os.path.join(DATA, f"backup_precios_contaminados_{STAMP}.json"), "w", encoding="utf-8") as f:
    json.dump({"repuntar_a_CONS129": ph_repuntar, "borrar": ph_borrar, "filas": ph_backup}, f, ensure_ascii=False, indent=1, default=str)
with open(os.path.join(DATA, f"backup_aliases_envenenados_{STAMP}.json"), "w", encoding="utf-8") as f:
    json.dump({"repuntar_a_CONS129": al_repuntar, "borrar": al_borrar, "filas": al_backup}, f, ensure_ascii=False, indent=1, default=str)
print("\nBackups escritos.")

# 4) Ejecutar por IDs explícitos
for pid in ph_repuntar:
    sb.table("precios_historicos").update({"codigo_material": "CONS129"}).eq("id", pid).execute()
for pid in ph_borrar:
    sb.table("precios_historicos").delete().eq("id", pid).execute()
for aid in al_repuntar:
    sb.table("material_denominaciones").update({"codigo_material": "CONS129"}).eq("id", aid).execute()
for aid in al_borrar:
    sb.table("material_denominaciones").delete().eq("id", aid).execute()

print(f"APLICADO: PH repuntadas={len(ph_repuntar)} borradas={len(ph_borrar)} | aliases repuntados={len(al_repuntar)} borrados={len(al_borrar)}")
