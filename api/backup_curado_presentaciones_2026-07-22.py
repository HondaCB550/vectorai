# -*- coding: utf-8 -*-
"""Backup previo al curado de presentaciones y unidades (22-07-2026).

Guarda en api/data/:
  - backup_precios_historicos_2026-07-22.json   (tabla completa)
  - backup_items_dispersos_2026-07-22.json      (presupuesto_items de los 65 dispersos)
  - backup_conversion_unidades_2026-07-22.json  (estado previo de las conversiones)

Correr:  cd api && python backup_curado_presentaciones_2026-07-22.py
"""
import os, json, datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA, exist_ok=True)
HOY = "2026-07-22"


def traer_todo(tabla: str, cols: str = "*") -> list[dict]:
    filas, off = [], 0
    while True:
        r = sb.table(tabla).select(cols).range(off, off + 999).execute()
        if not r.data:
            break
        filas.extend(r.data)
        off += 1000
        if len(r.data) < 1000:
            break
    return filas


def guardar(nombre: str, filas: list[dict]) -> str:
    ruta = os.path.join(DATA, f"backup_{nombre}_{HOY}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({
            "tomado": datetime.datetime.now().isoformat(timespec="seconds"),
            "motivo": "curado de presentaciones y unidades - CURADO_PENDIENTE.md",
            "filas": len(filas),
            "datos": filas,
        }, f, ensure_ascii=False, indent=1)
    print(f"  {ruta}  ({len(filas)} filas)")
    return ruta


if __name__ == "__main__":
    print("Backup del curado 22-07-2026:")
    ph = traer_todo("precios_historicos")
    guardar("precios_historicos", ph)

    # Códigos dispersos: >=2 proveedores y max > 3x min (mismo criterio del doc)
    from collections import defaultdict
    agg = defaultdict(lambda: {"mn": None, "mx": None, "prov": set()})
    for f in ph:
        p = f.get("precio")
        if not p or p <= 0:
            continue
        a = agg[f["codigo_material"]]
        a["mn"] = p if a["mn"] is None else min(a["mn"], p)
        a["mx"] = p if a["mx"] is None else max(a["mx"], p)
        a["prov"].add(f.get("proveedor"))
    dispersos = sorted(c for c, a in agg.items()
                       if c and len(a["prov"]) >= 2 and a["mx"] > 3 * a["mn"])
    print(f"  codigos dispersos detectados: {len(dispersos)}")

    items = []
    for i in range(0, len(dispersos), 50):
        lote = dispersos[i:i + 50]
        r = sb.table("presupuesto_items").select("*").in_("codigo_material", lote).execute()
        items.extend(r.data or [])
    guardar("items_dispersos", items)

    guardar("conversion_unidades", traer_todo("conversion_unidades"))

    with open(os.path.join(DATA, f"backup_codigos_dispersos_{HOY}.json"), "w", encoding="utf-8") as f:
        json.dump(dispersos, f, ensure_ascii=False, indent=1)
    print("\nListo.")
