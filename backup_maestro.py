#!/usr/bin/env python3
"""Backup del catálogo curado (el moat) y de los datos de negocio.

**El plan Free de Supabase NO hace backups automáticos.** Hasta que el proyecto
pase a Pro, este script es el único respaldo que existe, así que cubre dos
grupos:

- CATÁLOGO: lo que se cura a mano y sería carísimo de reconstruir (el maestro,
  los aliases del flywheel, la normalización del matching) más
  `precios_historicos`, que se alimenta solo pero no se puede volver a generar
  sin los PDFs originales.
- NEGOCIO: los datos de los usuarios y la facturación. `facturacion_eventos` es
  el registro de altas y bajas de plan: si se pierde, no hay forma de
  reconstruir quién pagó qué.

Antes del 22-07-2026 solo respaldaba el catálogo, y `precios_historicos` iba
detrás de un flag que el workflow nunca pasaba.

⚠ **PII**: `perfiles` incluye mail, nombre, empresa y localidad. Los JSON de
este backup no pueden terminar en un lugar público — hoy van como artifact de
GitHub Actions, que hereda los permisos del repo. Si el repo se hace público,
sacar `perfiles` de TABLAS_NEGOCIO o cifrar el artifact primero.

Necesita SUPABASE_SERVICE_KEY (la anon no lee estas tablas). Correr con las
variables de Railway inyectadas:

    railway run python backup_maestro.py                  # backups/YYYY-MM-DD/, todo
    railway run python backup_maestro.py --solo-catalogo  # sin datos de usuarios
    railway run python backup_maestro.py --out /ruta      # otro destino
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

# El moat: curado a mano, carísimo de reconstruir.
TABLAS_CATALOGO = [
    "materiales_validados",
    "material_denominaciones",
    "sinonimos",
    "grupos_marcas",
    "conversion_unidades",
    "materiales_pendientes",   # la cola de curado, es trabajo acumulado
    # Se alimenta solo desde los análisis, pero sin los PDFs originales no se
    # puede regenerar. Estaba detrás de --con-precios y el workflow nunca lo
    # pasaba: era el agujero más grande del backup.
    "precios_historicos",
]

# Datos de usuarios y facturación. Sin backup de Supabase (plan Free), esto es
# lo único que hay. Ver la nota de PII en el docstring.
TABLAS_NEGOCIO = [
    "perfiles",
    "facturacion_eventos",
    "comparativas",
    "presupuestos",
    "presupuesto_items",
    "obras",
    "proveedores",
    "proveedores_usuario",
    "equivalencias",
    "terminaciones_conceptos",
    "terminaciones_concepto_items",
    "terminaciones_recordadas",
    "extracciones_dudosas",
]

TABLAS = list(TABLAS_CATALOGO)
if "--solo-catalogo" not in sys.argv:
    TABLAS += TABLAS_NEGOCIO
# --con-precios ya no hace nada: precios_historicos entra siempre. Se acepta
# para no romper invocaciones viejas.

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
fallidas = []
total = 0
for tabla in TABLAS:
    try:
        filas = leer_todo(tabla)
    except Exception as e:
        print(f"  ERROR leyendo {tabla}: {e}")
        resumen[tabla] = f"ERROR: {e}"
        fallidas.append(tabla)
        continue
    ruta = os.path.join(carpeta, f"{tabla}.json")
    with open(ruta, "w", encoding="utf-8") as out:
        json.dump(filas, out, ensure_ascii=False, indent=2, default=str)
    resumen[tabla] = len(filas)
    total += len(filas)
    print(f"  {tabla:<28} {len(filas):>6} filas -> {ruta}")

with open(os.path.join(carpeta, "_resumen.json"), "w", encoding="utf-8") as out:
    json.dump({
        "fecha": date.today().isoformat(),
        "tablas": resumen,
        "total_filas": total,
        "fallidas": fallidas,
        "completo": not fallidas,
    }, out, ensure_ascii=False, indent=2)

if fallidas:
    # Salir con error: un backup parcial que reporta éxito es peor que no
    # tenerlo, porque nadie se entera hasta que hay que restaurar. El workflow
    # falla y avisa.
    print(f"\nBACKUP INCOMPLETO: fallaron {len(fallidas)} tablas -> {', '.join(fallidas)}")
    print(f"Se guardaron {total} filas de las demás en {carpeta}")
    sys.exit(1)

print(f"\nBackup completo: {total} filas de {len(TABLAS)} tablas en {carpeta}")
