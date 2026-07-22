# -*- coding: utf-8 -*-
"""Alta de conversiones del curado de presentaciones (22-07-2026).

Cada factor sale del texto real del proveedor y está verificado contra el
precio del mismo material que ya venía en la unidad canónica:

  T005  un/6000  TEL ALAS 8*1 1/4. Cotizado por caja de 6.000, cajas de 100 y
                 bolsas de 100. Normalizado: $58,1 / $42,7 / $62,6 / $33,1 → 1,9x.
                 Era el material Nº1 en dispersión (ratio 10.032x).
  TER114 un/100  EIFS ARANDELA. "ARANDELA EPS X 100" $3.453 ÷ 100 = $34,5,
                 que cierra contra los $30,96 del que ya viene por unidad.
  CONS104 kg/5   PASTINA. "X 5KG" $11.312 ÷ 5 = $2.262 contra "X1KG" $2.001 → 1,13x.
  TER482  kg/25  BASECOAT. Envases de 25 y 30 kg mezclados; el modo kg usa el
                 peso del texto, así el de 30 kg deja de parecer más caro.

NO se carga T011 (HEX 14*1/2 MAX): tiene un precio de $9.824 que es a todas
luces una caja, pero el material no tiene ninguna fila en presupuesto_items y
no hay texto del proveedor de donde sacar el factor. No se inventa.

Correr:  cd api && python cargar_conversiones_2026-07-22.py [--aplicar]
Sin --aplicar solo muestra lo que haría.
"""
import os, sys, json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

FILAS = [
    {"codigo_material": "T005",   "unidad_comercial": "un", "factor": 6000,
     "unidad_base": "UN", "descripcion": "caja de 6.000 / packs de 100", "activo": True},
    {"codigo_material": "TER114", "unidad_comercial": "un", "factor": 100,
     "unidad_base": "UN", "descripcion": "bolsa de 100 arandelas EIFS", "activo": True},
    {"codigo_material": "CONS104", "unidad_comercial": "kg", "factor": 5,
     "unidad_base": "KG", "descripcion": "bolsa de 5 kg (hay de 1 kg)", "activo": True},
    {"codigo_material": "TER482", "unidad_comercial": "kg", "factor": 25,
     "unidad_base": "KG", "descripcion": "bolsa de 25 kg (hay de 30 kg)", "activo": True},
]

if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv
    codigos = [f["codigo_material"] for f in FILAS]

    previo = sb.table("conversion_unidades").select("*").in_("codigo_material", codigos).execute().data or []
    print(f"Filas ya existentes para estos codigos: {len(previo)}")
    for p in previo:
        print(f"  YA EXISTE {p['codigo_material']}: {p['unidad_comercial']}/{p['factor']} activo={p.get('activo')}")
    if previo:
        print("\nAbortado: hay filas previas. Revisar a mano antes de insertar.")
        raise SystemExit(1)

    for f in FILAS:
        print(f"  + {f['codigo_material']:8} {f['unidad_comercial']}/{f['factor']:<6} {f['descripcion']}")

    if not aplicar:
        print("\n(simulacion — correr con --aplicar para insertar)")
        raise SystemExit(0)

    r = sb.table("conversion_unidades").insert(FILAS).execute()
    print(f"\nInsertadas {len(r.data or [])} filas.")
    for d in (r.data or []):
        print(f"  {d['codigo_material']}  id={d.get('id')}")
    print("\nOjo: el knowledge cache tiene TTL de 5 min.")
