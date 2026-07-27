# -*- coding: utf-8 -*-
"""Pre-clasifica la cola de materiales_pendientes para el curado conversacional.

Flujo nuevo (pedido de Pablo 24-07-2026): en vez del Excel, Claude lee la cola,
la agrupa y la pre-clasifica con el matcher REAL (_match_v2 con todas las
guardas), y presenta tandas en el chat para decisión rápida. El humano decide
SIEMPRE — la lección del 05-07 sigue vigente: el curado nunca es automático,
la pre-clasificación solo ordena la conversación.

Bandas:
  A_fuerte   top-1 >= 85 (el matcher de hoy lo aceptaría automático)
  B_dudoso   top-1 60-84 con candidatos para elegir
  C_sin      top-1 < 60 — o material nuevo o basura

Solo lectura. Escribe data/analisis_pendientes_2026-07-24.json.

Correr:  cd api && python analizar_pendientes_2026-07-24.py
"""
import os, sys, json
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
import main
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")


def traer_pendientes():
    filas, off = [], 0
    while True:
        r = (sb.table("materiales_pendientes").select("*")
             .eq("estado", "PENDIENTE").range(off, off + 999).execute())
        if not r.data:
            break
        filas.extend(r.data)
        off += 1000
        if len(r.data) < 1000:
            break
    return filas


if __name__ == "__main__":
    pend = traer_pendientes()
    mat = main._cargar_materiales_dict(sb, "codigo,denominacion_principal,descripcion")
    dens = main._get_denominaciones()
    print(f"pendientes: {len(pend)}   maestro: {len(mat)}   aliases: {len(dens)}")

    # Dedup por texto normalizado — el mismo texto de varios proveedores/PDFs
    # es UNA decisión.
    grupos = defaultdict(list)
    for p in pend:
        t = (p.get("descripcion_original") or "").strip()
        if t:
            grupos[t.lower()].append(p)
    print(f"textos unicos: {len(grupos)}")

    out = []
    for texto_lower, filas in grupos.items():
        texto = filas[0]["descripcion_original"].strip()
        ms = main._match_v2(texto, dens, top_n=3) or []
        cands = []
        for m in ms[:3]:
            c = m["codigo_material"]
            mm = mat.get(c) or {}
            cands.append({
                "codigo": c,
                "maestro": f"{mm.get('denominacion_principal','?')} | {mm.get('descripcion') or ''}".strip(" |"),
                "score": m["score"], "nivel": m["nivel"],
            })
        top = cands[0] if cands else None
        if top and top["score"] >= 85:
            banda = "A_fuerte"
        elif top and top["score"] >= 60:
            banda = "B_dudoso"
        else:
            banda = "C_sin"
        precios = sorted({round(float(f["precio_visto"]), 2) for f in filas
                          if f.get("precio_visto")})
        out.append({
            "texto": texto,
            "ids": [f["id"] for f in filas],
            "n_filas": len(filas),
            "proveedores": sorted({f.get("proveedor") or "?" for f in filas}),
            "precios_vistos": precios[:4],
            "banda": banda,
            "candidatos": cands,
        })

    out.sort(key=lambda x: (x["banda"], -(x["candidatos"][0]["score"] if x["candidatos"] else 0)))
    ruta = os.path.join(DATA, "analisis_pendientes_2026-07-24.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    from collections import Counter
    c = Counter(o["banda"] for o in out)
    print(f"\nBANDAS (textos unicos): {dict(c)}")
    print(f"-> {ruta}")
