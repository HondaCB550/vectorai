#!/usr/bin/env python3
"""Backup del catálogo maestro y del conocimiento curado a mano (el moat).

Respalda a JSON con timestamp las tablas que se editan a mano y cuya pérdida
sería cara de reconstruir: el maestro, sus aliases y las tablas de
normalización del matching. NO reemplaza el backup de la base entera de
Supabase (Point-in-Time Recovery del plan) — es una copia liviana,
versionable y auditable de lo que más cambia, para poder revisar diffs y
restaurar a mano si un lote de curado sale mal (ver CLAUDE.md → "Nunca
aprender aliases basura").

Necesita SUPABASE_SERVICE_KEY (la anon no lee estas tablas). Correr con las
variables de Railway inyectadas:

    railway run python backup_maestro.py                 # backups/YYYY-MM-DD/
    railway run python backup_maestro.py --con-precios   # incluye precios_historicos (grande)
    railway run python backup_maestro.py --out /ruta     # otro destino

Automatización sugerida: correrlo diario (cron / GitHub Action con secrets /
Railway cron) y versionar backups/ en el repo o subirlo a un bucket.
"""
import json
import os
import sys
from datetime import date

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), "api", ".env"))

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SERVICE_KEY:
    print("Falta SUPABASE_SERVICE_KEY (la anon key no puede leer estas tablas).")
    print("Corré el script con las variables de Railway:")
    print("  railway run python backup_maestro.py")
    sys.exit(1)

# Tablas curadas a mano que forman el moat. precios_historicos es opcional
# (crece sin techo) y solo se incluye con --con-precios.
TABLAS = [
    "materiales_validados",
    "material_denominaciones",
    "sinonimos",
    "grupos_marcas",
    "conversion_unidades",
]
if "--con-precios" in sys.argv:
    TABLAS.append("precios_historicos")

destino_base = "backups"
if "--out" in sys.argv:
    destino_base = sys.argv[sys.argv.index("--out") + 1]

sb = create_client(SUPABASE_URL, SERVICE_KEY)


def leer_todo(tabla: str) -> list[dict]:
    """Lee la tabla completa paginando de a 1000 (Supabase corta ahí; el
    maestro ya pasó ese tope — sin paginar se perderían filas)."""
    filas: list[dict] = []
    paso = 1000
    inicio = 0
    while True:
        lote = sb.table(tabla).select("*").range(inicio, inicio + paso - 1).execute().data or []
        filas.extend(lote)
        if len(lote) < paso:
            break
        inicio += paso
    return filas


carpeta = os.path.join(destino_base, date.today().isoformat())
os.makedirs(carpeta, exist_ok=True)

resumen = {}
total = 0
for tabla in TABLAS:
    try:
        filas = leer_todo(tabla)
    except Exception as e:
        print(f"  ERROR leyendo {tabla}: {e}")
        resumen[tabla] = f"ERROR: {e}"
        continue
    ruta = os.path.join(carpeta, f"{tabla}.json")
    with open(ruta, "w", encoding="utf-8") as out:
        json.dump(filas, out, ensure_ascii=False, indent=2, default=str)
    resumen[tabla] = len(filas)
    total += len(filas)
    print(f"  {tabla:<26} {len(filas):>6} filas -> {ruta}")

with open(os.path.join(carpeta, "_resumen.json"), "w", encoding="utf-8") as out:
    json.dump({"fecha": date.today().isoformat(), "tablas": resumen, "total_filas": total},
              out, ensure_ascii=False, indent=2)

print(f"\nBackup completo: {total} filas en {carpeta}")
