# -*- coding: utf-8 -*-
"""Re-arbitra los matches de los materiales dispersos con el matcher ACTUAL.

Las filas dispersas se matchearon antes de que existieran la guarda numérica
generalizada, la de dominios de marca incompatibles y la de calificadores
excluyentes. Las guardas se agregaron, pero los datos viejos quedaron.

En vez de clasificar 167 ítems a ojo, se vuelve a pasar cada texto_original por
_match_v2 y se compara con el código que tiene asignado hoy:

  OK        el matcher actual le sigue dando ese código con score >= 85
  DUDOSO    se lo sigue dando pero por debajo del umbral automático
  ERRADO    el matcher actual le daría OTRO código, o ninguno
  BASURA    el texto no da para matchear nada (truncado, sin palabras reales)

Solo lee. Escribe el veredicto en data/reclasificacion_dispersos_2026-07-22.json
para revisarlo antes de aplicar nada.

Correr:  cd api && python reclasificar_dispersos_2026-07-22.py
"""
import os, json, re
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
import main
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")

# Un texto sin ninguna palabra real de 3+ letras no da para matchear (mismo
# criterio que el filtro de basura del pool de aliases).
_RE_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}")


def es_basura(texto: str) -> bool:
    t = (texto or "").strip()
    if len(t) < 6 or not _RE_PALABRA.search(t):
        return True
    # Línea cruda de PDF que se coló entera como descripción
    return t.count("$") >= 2


def main_():
    with open(os.path.join(DATA, "backup_codigos_dispersos_2026-07-22.json"), encoding="utf-8") as f:
        dispersos = json.load(f)
    with open(os.path.join(DATA, "backup_items_dispersos_2026-07-22.json"), encoding="utf-8") as f:
        items = json.load(f)["datos"]

    maestro = main._cargar_materiales_dict(sb, "codigo,denominacion_principal,descripcion")
    dens = main._get_denominaciones()
    print(f"corpus de aliases: {len(dens)}   maestro: {len(maestro)}")
    print(f"items a rearbitrar: {len(items)}  (codigos dispersos: {len(dispersos)})\n")

    out = []
    for it in items:
        cod_actual = it.get("codigo_material")
        texto = it.get("texto_original") or ""
        if not cod_actual:
            continue

        if es_basura(texto):
            veredicto, cod_nuevo, score = "BASURA", None, 0.0
        else:
            ms = main._match_v2(texto, dens, top_n=3) or []
            top = ms[0] if ms else None
            cod_nuevo = top["codigo_material"] if top else None
            score = float(top.get("score") or 0) if top else 0.0
            if cod_nuevo == cod_actual and score >= 85:
                veredicto = "OK"
            elif cod_nuevo == cod_actual:
                veredicto = "DUDOSO"
            else:
                veredicto = "ERRADO"

        m_act = maestro.get(cod_actual) or {}
        m_new = maestro.get(cod_nuevo) or {}
        out.append({
            "item_id": it.get("id"),
            "presupuesto_id": it.get("presupuesto_id"),
            "texto_original": texto,
            "precio": it.get("precio"),
            "cantidad": it.get("cantidad"),
            "codigo_actual": cod_actual,
            "maestro_actual": f"{m_act.get('denominacion_principal','?')} | {m_act.get('descripcion','')}",
            "veredicto": veredicto,
            "codigo_sugerido": cod_nuevo,
            "maestro_sugerido": f"{m_new.get('denominacion_principal','?')} | {m_new.get('descripcion','')}" if cod_nuevo else None,
            "score": round(score, 1),
        })

    ruta = os.path.join(DATA, "reclasificacion_dispersos_2026-07-22.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    from collections import Counter
    c = Counter(o["veredicto"] for o in out)
    print("VEREDICTOS:", dict(c))
    print(f"\n-> {ruta}\n")

    for v in ("BASURA", "ERRADO", "DUDOSO"):
        filas = [o for o in out if o["veredicto"] == v]
        if not filas:
            continue
        print(f"\n===== {v} ({len(filas)}) =====")
        for o in sorted(filas, key=lambda x: x["codigo_actual"]):
            sug = f" -> {o['codigo_sugerido']} ({o['score']})" if o["codigo_sugerido"] else " -> (ninguno)"
            print(f"  [{o['codigo_actual']:9}] {o['texto_original'][:52]:52}{sug}")


if __name__ == "__main__":
    main_()
