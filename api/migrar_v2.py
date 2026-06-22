"""
Migración v2: carga materiales_validados + material_denominaciones desde master_materiales.json
"""
import json
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("ERROR: Faltan SUPABASE_URL y/o SUPABASE_SERVICE_KEY en .env")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

with open("data/master_materiales.json", encoding="utf-8") as f:
    materiales = json.load(f)

print(f"{len(materiales)} materiales en master_materiales.json")

# ── Paso 1: insertar materiales_validados ──────────────────────────────────────
# Deduplicar por código (mantener último registro)
materiales_dedup = {}
for mat in materiales:
    codigo = (mat.get("codigo") or "").strip()
    if codigo:
        materiales_dedup[codigo] = mat
materiales = list(materiales_dedup.values())
print(f"  Despues de dedup: {len(materiales)} materiales")

batch_mat = []
for mat in materiales:
    codigo = (mat.get("codigo") or "").strip()
    if not codigo:
        continue

    unidad = (mat.get("unidad") or "UNIDAD").strip()
    marca  = (mat.get("marca") or "").strip()

    batch_mat.append({
        "codigo": codigo,
        "categoria": (mat.get("rubro") or "").strip(),
        "denominacion_principal": (mat.get("item") or "").strip(),
        "descripcion": (mat.get("detalle") or "").strip(),
        "unidades_posibles": [{"unidad": unidad, "descripcion": "unidad base", "equivalencia": 1}],
        "marcas_disponibles": [marca] if marca else [],
        "validado_por": "migracion_inicial",
    })

BATCH = 100
for i in range(0, len(batch_mat), BATCH):
    sb.table("materiales_validados").upsert(batch_mat[i:i+BATCH]).execute()
    print(f"  materiales_validados: {min(i+BATCH, len(batch_mat))}/{len(batch_mat)}")

print(f"OK {len(batch_mat)} materiales insertados")

# ── Paso 2: insertar material_denominaciones ────────────────────────────────────
# Por cada material cargamos hasta 2 aliases: item y detalle (si son distintos)
batch_den = []
seen = set()

for mat in materiales:
    codigo = (mat.get("codigo") or "").strip()
    if not codigo:
        continue

    textos = []
    item   = (mat.get("item") or "").strip()
    detalle = (mat.get("detalle") or "").strip()

    if item:
        textos.append((item.lower(), "migracion_item"))
    if detalle and detalle.lower() != item.lower():
        textos.append((detalle.lower(), "migracion_detalle"))

    for texto, origen in textos:
        key = f"{codigo}|{texto}"
        if key in seen or not texto:
            continue
        seen.add(key)
        batch_den.append({
            "codigo_material": codigo,
            "denominacion": texto,
            "origen": origen,
            "confianza": 90,
            "frecuencia_encontrada": 1,
        })

for i in range(0, len(batch_den), BATCH):
    sb.table("material_denominaciones").upsert(
        batch_den[i:i+BATCH],
        on_conflict="codigo_material,denominacion"
    ).execute()
    print(f"  material_denominaciones: {min(i+BATCH, len(batch_den))}/{len(batch_den)}")

print(f"OK {len(batch_den)} aliases insertados")
print("Migracion completa")
print("Verificar: SELECT COUNT(*) FROM materiales_validados;")
print("Verificar: SELECT COUNT(*) FROM material_denominaciones;")
