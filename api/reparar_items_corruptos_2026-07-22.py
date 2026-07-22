# -*- coding: utf-8 -*-
"""Repara dos corrupciones de presupuesto_items detectadas en el curado (22-07-2026).

BUG A — total de línea guardado como precio unitario.
  Algunos PDFs dejaron DOS filas para el mismo ítem: una con el precio unitario
  correcto y otra donde se leyó la columna de total. La segunda cumple exacto
  precio_malo == precio_bueno * cantidad / 1.105 (el factor de IVA). Verificado
  al centavo en TOSCA, VARILLA 6, MALLA 6 y otros. Esas filas se ELIMINAN: son
  la misma cotización leída mal, no un precio distinto.

BUG B — cantidades fraccionarias de la corrección manual del 13-07.
  Los ítems de Insuma quedaron con cantidad 0.01 / 0.025 / 0.0125 y el precio
  escalado ×100 para conservar el total de línea. _convertir_unidad recibe así
  un precio que ya está a escala de caja y lo vuelve a dividir por el pack.
  Se normalizan a precio = precio*cantidad (el precio real del pack) y
  cantidad = 1. Validación cruzada: T003 queda en $16,15/u contra $16,46/u del
  otro proveedor, y T004 en $18,47/u contra $17,48/u.

Solo toca filas por ID explícito. Backup previo en
data/backup_items_dispersos_2026-07-22.json (y el de precios_historicos).

Correr:  cd api && python reparar_items_corruptos_2026-07-22.py [--aplicar]
"""
import os, sys, json
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")
IVA = 1.105
TOL = 0.005          # 0,5% de tolerancia en la comparación


def traer_items():
    filas, off = [], 0
    while True:
        r = sb.table("presupuesto_items").select("*").range(off, off + 999).execute()
        if not r.data:
            break
        filas.extend(r.data)
        off += 1000
        if len(r.data) < 1000:
            break
    return filas


def detectar_bug_a(items):
    """Filas donde el precio es el TOTAL de otra fila del mismo texto."""
    # La misma lectura rota suele truncar tambien la descripcion
    # ("MALLA 6 15x15" -> "MALLA 6 15x"), asi que el par no se encuentra por
    # texto exacto: se agrupan por cantidad y se exige que un texto sea prefijo
    # del otro (sin espacios, >=8 caracteres).
    def norm(t: str) -> str:
        return "".join((t or "").lower().split())

    por_cant = defaultdict(list)
    for it in items:
        if it.get("texto_original") and it.get("precio") and it.get("cantidad"):
            por_cant[float(it["cantidad"])].append(it)

    malas = []
    for _, grupo in por_cant.items():
        if len(grupo) < 2:
            continue
        for cand in grupo:
            pc = float(cand["precio"])
            nc = norm(cand["texto_original"])
            for otro in grupo:
                if otro["id"] == cand["id"]:
                    continue
                po, co = float(otro["precio"]), float(otro["cantidad"])
                if po <= 0 or co <= 0 or pc <= po:
                    continue
                no = norm(otro["texto_original"])
                corto, largo = (nc, no) if len(nc) <= len(no) else (no, nc)
                if len(corto) < 8 or not largo.startswith(corto):
                    continue
                esperado = po * co / IVA
                if esperado > 0 and abs(pc - esperado) / esperado < TOL:
                    malas.append({
                        "id": cand["id"], "texto": cand["texto_original"],
                        "texto_par": otro["texto_original"],
                        "precio_malo": pc, "precio_bueno": po, "cantidad": co,
                        "esperado": round(esperado, 2),
                        "codigo": cand.get("codigo_material"),
                    })
                    break
    return malas


def detectar_bug_b(items):
    """Ítems con cantidad fraccionaria (<1) — resto de la corrección del 13-07."""
    out = []
    for it in items:
        c = it.get("cantidad")
        p = it.get("precio")
        if c is None or p is None:
            continue
        c, p = float(c), float(p)
        if 0 < c < 1:
            out.append({
                "id": it["id"], "texto": it["texto_original"],
                "codigo": it.get("codigo_material"),
                "precio_viejo": p, "cantidad_vieja": c,
                "precio_nuevo": round(p * c, 4), "cantidad_nueva": 1,
            })
    return out


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv
    items = traer_items()
    print(f"presupuesto_items: {len(items)}\n")

    bug_a = detectar_bug_a(items)
    bug_b = detectar_bug_b(items)

    print(f"=== BUG A — total leido como precio unitario ({len(bug_a)}) ===")
    for m in sorted(bug_a, key=lambda x: -x["precio_malo"]):
        print(f"  [{str(m['codigo']):8}] ${m['precio_malo']:>14,.2f}  =  "
              f"${m['precio_bueno']:>10,.2f} x {m['cantidad']:g} / 1.105   {m['texto'][:34]}")

    print(f"\n=== BUG B — cantidad fraccionaria ({len(bug_b)}) ===")
    for m in bug_b:
        print(f"  [{str(m['codigo']):8}] ${m['precio_viejo']:>12,.2f} x {m['cantidad_vieja']:g}"
              f"  ->  ${m['precio_nuevo']:>10,.2f} x 1   {m['texto'][:34]}")

    ruta = os.path.join(DATA, "reparacion_items_2026-07-22.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"bug_a_eliminar": bug_a, "bug_b_normalizar": bug_b}, f,
                  ensure_ascii=False, indent=1)
    print(f"\n-> {ruta}")

    if not aplicar:
        print("\n(simulacion — correr con --aplicar)")
        raise SystemExit(0)

    ids_a = [m["id"] for m in bug_a]
    for i in range(0, len(ids_a), 50):
        sb.table("presupuesto_items").delete().in_("id", ids_a[i:i + 50]).execute()
    print(f"\nBUG A: {len(ids_a)} items eliminados.")

    for m in bug_b:
        sb.table("presupuesto_items").update({
            "precio": m["precio_nuevo"], "cantidad": m["cantidad_nueva"],
        }).eq("id", m["id"]).execute()
    print(f"BUG B: {len(bug_b)} items normalizados.")
