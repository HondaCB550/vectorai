"""
Migración: carga Equivalencias del Excel de Cotizaciones → material_denominaciones en Supabase.
Convierte las 811 decisiones históricas confirmadas en aliases de texto.
"""
import os
import openpyxl
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
EXCEL_PATH   = r"C:\Pablo\Cotizaciones\Carga de Precios Presupuestos\Base de Presupuestos_2026_macro.xlsm"

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("ERROR: Faltan SUPABASE_URL y/o SUPABASE_KEY en .env")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Leer Equivalencias ────────────────────────────────────────────────────────
print(f"Leyendo {EXCEL_PATH} ...")
wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
ws = wb["Equivalencias"]
rows = list(ws.iter_rows(values_only=True))
print(f"  {len(rows)-1} filas (sin header)")

# Columnas: proveedor, cod_proveedor, descripcion_proveedor, cod_interno, ...
HEADER = rows[0]
IDX_PROV  = 0  # proveedor
IDX_DESC  = 2  # descripcion_proveedor
IDX_COD   = 3  # cod_interno

# ── Cargar codigos validos en Supabase ────────────────────────────────────────
print("Cargando codigos validos de materiales_validados ...")
res = sb.table("materiales_validados").select("codigo").execute()
codigos_validos = {r["codigo"] for r in (res.data or [])}
print(f"  {len(codigos_validos)} codigos validos")

# ── Construir batch de aliases ────────────────────────────────────────────────
batch = []
omitidos = 0
seen = set()

for row in rows[1:]:
    cod_int  = str(row[IDX_COD]  or "").strip()
    desc_prov = str(row[IDX_DESC] or "").strip()
    proveedor = str(row[IDX_PROV] or "").strip()

    if not cod_int or not desc_prov:
        omitidos += 1
        continue

    if cod_int not in codigos_validos:
        print(f"  SKIP: codigo '{cod_int}' no existe en materiales_validados")
        omitidos += 1
        continue

    desc_norm = desc_prov.lower().strip()
    key = f"{cod_int}|{desc_norm}"
    if key in seen:
        continue
    seen.add(key)

    origen = f"equivalencias_{proveedor.lower().replace(' ', '_')}" if proveedor else "equivalencias_historico"

    batch.append({
        "codigo_material":      cod_int,
        "denominacion":         desc_norm,
        "origen":               origen,
        "confianza":            95,
        "frecuencia_encontrada": 1,
    })

print(f"\nAliases a insertar: {len(batch)}  (omitidos: {omitidos})")

# ── Insertar en lotes ─────────────────────────────────────────────────────────
BATCH = 100
insertados = 0
errores = 0

for i in range(0, len(batch), BATCH):
    chunk = batch[i:i+BATCH]
    try:
        sb.table("material_denominaciones").upsert(
            chunk,
            on_conflict="codigo_material,denominacion"
        ).execute()
        insertados += len(chunk)
        print(f"  {min(i+BATCH, len(batch))}/{len(batch)} aliases insertados")
    except Exception as e:
        print(f"  ERROR en lote {i}-{i+BATCH}: {e}")
        errores += len(chunk)

print(f"\nOK: {insertados} aliases insertados/actualizados ({errores} errores)")
print("Verificar: SELECT COUNT(*) FROM material_denominaciones;")
