# -*- coding: utf-8 -*-
"""Aplica el curado de los materiales dispersos (22-07-2026).

Regla: precios_historicos solo debe contener precios de matches que el matcher
ACTUAL aceptaría automáticamente (score >= 85). Las filas dispersas son
anteriores a la guarda numérica, la de dominios de marca y la de calificadores,
así que quedaron adentro precios de productos que no son el material.

Según el veredicto de reclasificar_dispersos_2026-07-22.py:

  ERRADO con sugerido >= 85  → se REASIGNA el código (el precio es válido, está
                               colgado del material equivocado)
  ERRADO con sugerido < 85   → a pendientes: se saca de precios_historicos y se
  BASURA                       le quita el código al item
  DUDOSO                     → se saca de precios_historicos (nunca debió entrar
                               solo) y el item queda para revisión humana
  OK                         → no se toca

Todo se hace por listas de IDs explícitas — nunca con un UPDATE/DELETE por
predicado amplio. Backup previo en data/backup_*_2026-07-22.json.

Correr:  cd api && python aplicar_curado_dispersos_2026-07-22.py [--aplicar]
"""
import os, sys, json
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")
UMBRAL_AUTO = 85.0


def cargar():
    with open(os.path.join(DATA, "reclasificacion_dispersos_2026-07-22.json"), encoding="utf-8") as f:
        return json.load(f)


def plan(recla):
    """Arma el plan sin tocar nada. Devuelve (reasignar, a_pendientes, resumen)."""
    reasignar, a_pendientes = [], []
    for o in recla:
        v = o["veredicto"]
        if v == "OK":
            continue
        if v == "ERRADO" and o["codigo_sugerido"] and o["score"] >= UMBRAL_AUTO:
            reasignar.append(o)
        else:
            a_pendientes.append(o)
    return reasignar, a_pendientes


def mapear_precios(recla):
    """precios_historicos afectados, por (codigo_material, precio redondeado).

    precios_historicos no guarda texto_original, así que el vínculo con el item
    se arma por código + precio. Se listan los IDs y se reportan las
    ambigüedades para que ninguna fila se toque a ciegas.
    """
    codigos = sorted({o["codigo_actual"] for o in recla if o["veredicto"] != "OK"})
    filas = []
    for i in range(0, len(codigos), 50):
        r = sb.table("precios_historicos").select("*").in_("codigo_material", codigos[i:i + 50]).execute()
        filas.extend(r.data or [])
    idx = defaultdict(list)
    for f in filas:
        if f.get("precio") is None:
            continue
        idx[(f["codigo_material"], round(float(f["precio"]), 2))].append(f)
    return idx


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv
    recla = cargar()
    reasignar, a_pendientes = plan(recla)
    idx = mapear_precios(recla)

    print(f"items a REASIGNAR:    {len(reasignar)}")
    print(f"items a PENDIENTES:   {len(a_pendientes)}")
    print(f"claves de precio indexadas: {len(idx)}\n")

    ph_reasignar: dict[str, str] = {}     # id precio_historico -> codigo nuevo
    ph_borrar: set[str] = set()
    huerfanos = []

    for o in reasignar:
        clave = (o["codigo_actual"], round(float(o["precio"]), 2))
        for f in idx.get(clave, []):
            ph_reasignar[f["id"]] = o["codigo_sugerido"]
        if clave not in idx:
            huerfanos.append(("reasignar", o))

    for o in a_pendientes:
        clave = (o["codigo_actual"], round(float(o["precio"]), 2))
        for f in idx.get(clave, []):
            ph_borrar.add(f["id"])
        if clave not in idx:
            huerfanos.append(("pendiente", o))

    # Un precio que también corresponde a un item sano no se toca.
    seguros = set()
    for o in recla:
        if o["veredicto"] == "OK":
            for f in idx.get((o["codigo_actual"], round(float(o["precio"]), 2)), []):
                seguros.add(f["id"])
    colision = (set(ph_reasignar) | ph_borrar) & seguros
    for cid in colision:
        ph_reasignar.pop(cid, None)
        ph_borrar.discard(cid)

    print(f"precios_historicos a REASIGNAR: {len(ph_reasignar)}")
    print(f"precios_historicos a BORRAR:    {len(ph_borrar)}")
    print(f"protegidos por colision con un item sano: {len(colision)}")
    print(f"items sin fila de precio (nada que hacer): {len(huerfanos)}\n")

    resumen = {
        "generado": "2026-07-22",
        "umbral_auto": UMBRAL_AUTO,
        "items_reasignar": [{"item_id": o["item_id"], "de": o["codigo_actual"],
                             "a": o["codigo_sugerido"], "score": o["score"],
                             "texto": o["texto_original"]} for o in reasignar],
        "items_pendientes": [{"item_id": o["item_id"], "de": o["codigo_actual"],
                              "veredicto": o["veredicto"], "score": o["score"],
                              "texto": o["texto_original"]} for o in a_pendientes],
        "ph_reasignar": ph_reasignar,
        "ph_borrar": sorted(ph_borrar),
        "ph_protegidos": sorted(colision),
    }
    ruta = os.path.join(DATA, "plan_curado_dispersos_2026-07-22.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    print(f"plan -> {ruta}")

    if not aplicar:
        print("\n(simulacion — correr con --aplicar)")
        raise SystemExit(0)

    # ── Aplicar, siempre por IDs explícitos ──────────────────────────────────
    n = 0
    por_codigo = defaultdict(list)
    for ph_id, cod in ph_reasignar.items():
        por_codigo[cod].append(ph_id)
    for cod, ids in por_codigo.items():
        for i in range(0, len(ids), 50):
            sb.table("precios_historicos").update({"codigo_material": cod}) \
              .in_("id", ids[i:i + 50]).execute()
            n += len(ids[i:i + 50])
    print(f"precios_historicos reasignados: {n}")

    ids_borrar = sorted(ph_borrar)
    for i in range(0, len(ids_borrar), 50):
        sb.table("precios_historicos").delete().in_("id", ids_borrar[i:i + 50]).execute()
    print(f"precios_historicos borrados: {len(ids_borrar)}")

    por_codigo_item = defaultdict(list)
    for o in reasignar:
        por_codigo_item[o["codigo_sugerido"]].append(o["item_id"])
    for cod, ids in por_codigo_item.items():
        for i in range(0, len(ids), 50):
            sb.table("presupuesto_items").update({"codigo_material": cod}) \
              .in_("id", ids[i:i + 50]).execute()
    print(f"presupuesto_items reasignados: {sum(len(v) for v in por_codigo_item.values())}")

    ids_pend = [o["item_id"] for o in a_pendientes if o["item_id"]]
    for i in range(0, len(ids_pend), 50):
        sb.table("presupuesto_items").update({"codigo_material": None}) \
          .in_("id", ids_pend[i:i + 50]).execute()
    print(f"presupuesto_items mandados a pendientes: {len(ids_pend)}")
    print("\nListo. El knowledge cache tiene TTL de 5 min.")
