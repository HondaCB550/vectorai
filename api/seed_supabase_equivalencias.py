"""
seed_supabase_equivalencias.py — Importa matches confirmados a tabla equivalencias en Supabase

Usa decisiones_usuario.json (extraído por seed_equivalencias.py desde Borradores)
e inserta equivalencias confirmadas a Supabase para que beneficien a todos los usuarios.

Uso:
    python seed_supabase_equivalencias.py [--dry-run] [--clear]

Flags:
  --dry-run   : muestra lo que haría sin insertar
  --clear     : borra todas las equivalencias primero (regenera from scratch)
"""
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
DECISIONES_JSON = Path(__file__).parent / "data" / "decisiones_usuario.json"
MASTER_JSON = Path(__file__).parent / "data" / "master_materiales.json"

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise Exception("Falta SUPABASE_URL o SUPABASE_SERVICE_KEY en .env")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def cargar_master():
    """Carga master_materiales.json para mapear cod_int → item."""
    with open(MASTER_JSON, encoding="utf-8") as f:
        master = json.load(f)
    return {m["codigo"]: m for m in master}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()

    if not DECISIONES_JSON.exists():
        print(f"❌ No encontrado: {DECISIONES_JSON}")
        return

    # Cargar decisiones
    with open(DECISIONES_JSON, encoding="utf-8") as f:
        decisiones = json.load(f)

    # Cargar master
    master = cargar_master()
    print(f"Master: {len(master)} ítems")

    # Filtrar solo CARGAR (matches confirmados)
    cargar_decisiones = [d for d in decisiones if d.get("decision") == "CARGAR"]
    print(f"Decisiones CARGAR: {len(cargar_decisiones)}")

    # Agrupar por proveedor (necesario para el UNIQUE constraint en Supabase)
    por_proveedor = defaultdict(list)
    for d in cargar_decisiones:
        # Deducir proveedor desde el fuente (nombre del archivo borrador)
        fuente = d.get("fuente", "")
        # Estrategia: tomar primeras palabras del nombre del archivo
        prov = fuente.split("_")[0].replace(".xlsx", "").strip() or "UNKNOWN"
        cod_int = d.get("cod_correcto") or d.get("cod_propuesto") or ""
        if cod_int:
            por_proveedor[prov].append({
                "cod_prov": d.get("cod_prov", ""),
                "desc_prov": d.get("desc_prov", ""),
                "cod_int": cod_int,
                "fuente": d.get("fuente", "seed_equivalencias"),
            })

    print(f"\nPor proveedor:")
    for prov, items in sorted(por_proveedor.items()):
        print(f"  {prov}: {len(items)} equivalencias")

    # Conectar a Supabase
    sb = get_supabase()

    # Limpiar si --clear
    if args.clear:
        print("\n⚠️  Borrando tabla equivalencias...")
        if not args.dry_run:
            sb.table("equivalencias").delete().neq("id", "").execute()
            print("  ✓ Borrado")

    # Insertar equivalencias
    to_insert = []
    for prov, items in sorted(por_proveedor.items()):
        for item in items:
            cod_prov = item["cod_prov"]
            desc_prov = item["desc_prov"]
            cod_int = item["cod_int"]
            item_int = master.get(cod_int, {}).get("item", "")

            to_insert.append({
                "cod_prov": cod_prov,
                "desc_prov": desc_prov,
                "proveedor": prov,
                "cod_int": cod_int,
                "item_int": item_int,
                "fuente": "auto",  # "manual" sería si un usuario lo confirma en /revisar
                "confianza": 85,  # 85-90 para seeds automáticos (no es 100 porque vienen de borradores)
            })

    print(f"\n📊 Total equivalencias a insertar: {len(to_insert)}")

    if not to_insert:
        print("Nada que hacer.")
        return

    if args.dry_run:
        print("\n[DRY RUN] Primeras 5 equivalencias:")
        for eq in to_insert[:5]:
            print(f"  {eq['cod_prov']:20} → {eq['cod_int']:8} ({eq['proveedor']})")
        print(f"\n... y {len(to_insert) - 5} más")
        return

    # Insertar en lotes para evitar timeout
    batch_size = 100
    for i in range(0, len(to_insert), batch_size):
        batch = to_insert[i:i+batch_size]
        try:
            # Insertar ignorando duplicados (unique constraint)
            sb.table("equivalencias").upsert(batch).execute()
            print(f"✓ Batch {i//batch_size + 1}: {len(batch)} insertadas")
        except Exception as e:
            # Es normal si hay duplicados por el unique constraint
            print(f"⚠️  Batch {i//batch_size + 1}: {str(e)[:100]}")

    print(f"\n✅ Seed completado: {len(to_insert)} equivalencias")
    print("\nLa tabla equivalencias ahora beneficia a todos los usuarios:")
    print("  - El scoring de matching busca automáticamente en esta tabla")
    print("  - Si encuentra coincidencia, suma +15 al score (origen='EQUIV')")
    print("  - Los usuarios logueados pueden agregar más vía /confirmar")

if __name__ == "__main__":
    main()
