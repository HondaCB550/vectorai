#!/usr/bin/env python3
"""Descarga los archivos con extracción dudosa (formato nuevo) a la compu local.

Los archivos que el motor no pudo leer quedan en el bucket 'dudosos' de
Supabase + una fila en extracciones_dudosas (estado='pendiente'). Este script
los baja a C:\\Pablo\\Cotizaciones\\Para cargar\\Dudosos\\ y marca las filas
como 'descargado'. Después: analizar el formato, armar el parser en
api/matching/extraer_pdf_texto.py y marcar la fila como 'resuelto'.

Necesita la SUPABASE_SERVICE_KEY (no está en api/.env local, vive en Railway).
La forma simple es correrlo con las variables inyectadas por Railway:

    cd C:\\Pablo\\presupuestor
    railway run python descargar_dudosos.py            # baja pendientes y los marca descargados
    railway run python descargar_dudosos.py --listar   # solo muestra qué hay, sin bajar nada
"""
import os
import re
import sys

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), "api", ".env"))

DESTINO = r"C:\Pablo\Cotizaciones\Para cargar\Dudosos"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SERVICE_KEY:
    print("Falta SUPABASE_SERVICE_KEY (la anon key no puede leer extracciones_dudosas).")
    print("Corré el script con las variables de Railway:")
    print("  cd C:\\Pablo\\presupuestor && railway run python descargar_dudosos.py")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SERVICE_KEY)
solo_listar = "--listar" in sys.argv

filas = (
    sb.table("extracciones_dudosas")
    .select("id, created_at, archivo, proveedor, tipo_fuente, metodo_extraccion, "
            "motivo, n_items, n_consistentes, storage_path, estado")
    .in_("estado", ["pendiente"] if not solo_listar else ["pendiente", "descargado"])
    .order("created_at", desc=True)
    .execute()
).data or []

if not filas:
    print("No hay extracciones dudosas pendientes.")
    sys.exit(0)

print(f"{len(filas)} extracciones dudosas:")
os.makedirs(DESTINO, exist_ok=True)
bajados = 0

for f in filas:
    fecha = (f.get("created_at") or "")[:10]
    print(f"  [{fecha}] {f['archivo']}  proveedor={f.get('proveedor') or '?'}  "
          f"motivo={f['motivo']}  items={f['n_items']} (consistentes {f['n_consistentes']})  "
          f"metodo={f.get('metodo_extraccion') or '-'}  estado={f['estado']}")
    if solo_listar or not f.get("storage_path"):
        continue
    try:
        contenido = sb.storage.from_("dudosos").download(f["storage_path"])
        seguro = re.sub(r"[^A-Za-z0-9 _.\-()]+", "_", f["archivo"] or "archivo")
        destino = os.path.join(DESTINO, f"{fecha}_{seguro}")
        with open(destino, "wb") as out:
            out.write(contenido)
        sb.table("extracciones_dudosas").update({"estado": "descargado"}).eq("id", f["id"]).execute()
        bajados += 1
        print(f"      -> {destino}")
    except Exception as e:
        print(f"      ERROR descargando: {e}")

if not solo_listar:
    print(f"\n{bajados} archivos descargados en {DESTINO}")
    print("Cuando el parser nuevo esté deployado, marcá las filas como resueltas:")
    print("  update extracciones_dudosas set estado='resuelto' where estado='descargado';")
