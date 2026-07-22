# -*- coding: utf-8 -*-
"""Restaura los 8 aliases reasignados que el bug del chequeo de duplicados borro.

curar_aliases_dispersos_2026-07-22.py se corrio tres veces; en la segunda, el
chequeo de duplicados encontraba la fila YA reasignada en el destino (ella
misma) y la borraba. Este script reinserta las 8 filas en su codigo DESTINO
correcto, con el origen y confianza que tenian (documentados en el output del
diagnostico de esa sesion). Idempotente: si la fila ya existe, la saltea.

Correr:  cd api && python restaurar_reasignados_2026-07-22.py
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

FILAS = [
    {"codigo_material": "CONS118",  "denominacion": "hierro 12 mm",
     "origen": "usuario_corralon_nuevo_pilar_-_efectivo", "confianza": 80},
    {"codigo_material": "CONS118",  "denominacion": "hierro 12 mm acindar/bragado",
     "origen": "usuario_corralon_las_quintas", "confianza": 82},
    {"codigo_material": "CONS118",  "denominacion": "hierro 12.00 mm",
     "origen": "usuario_j.m._landa", "confianza": 80},
    {"codigo_material": "INSTS040", "denominacion": "codo mh 50x90 duratop",
     "origen": "usuario_el_galpon_-_sanitarios", "confianza": 80},
    {"codigo_material": "INSTS037", "denominacion": "codo mh 63x45 duratop",
     "origen": "usuario_el_galpon_-_sanitarios", "confianza": 80},
    {"codigo_material": "INSTS042", "denominacion": "codo mh 110x90 duratop",
     "origen": "usuario_el_galpon_-_sanitarios", "confianza": 80},
    {"codigo_material": "INSTS124", "denominacion": "08-332050000 union doble 50 acqua system",
     "origen": "usuario_carosio_sanitarios", "confianza": 80},
    {"codigo_material": "INSTS183", "denominacion": "flex.mallado a.inox. 1/2 x 30 latyn af2075 latyn",
     "origen": "borrador_borrador_viejo_bueno_13-14", "confianza": 90},
]

if __name__ == "__main__":
    for f in FILAS:
        ya = sb.table("material_denominaciones").select("id") \
               .eq("codigo_material", f["codigo_material"]) \
               .eq("denominacion", f["denominacion"]).execute().data
        if ya:
            print(f"  ya existe  {f['codigo_material']:9} {f['denominacion'][:44]}")
            continue
        sb.table("material_denominaciones").insert(f).execute()
        print(f"  insertado  {f['codigo_material']:9} {f['denominacion'][:44]}")
    print("\nListo. Cache TTL 5 min.")
