# -*- coding: utf-8 -*-
"""Reconstruye precios_historicos desde presupuesto_items (22-07-2026).

Las filas viejas (origen='legacy') no guardan el texto del proveedor, así que
no hay forma de saber qué presentación cotizaron ni de recalcular su conversión.
Se conservan, marcadas, y quedan FUERA del Índice.

Este script genera la capa limpia (origen='pipeline'): cada fila sale de un
presupuesto_item que sí conserva su texto_original, y ese texto se vuelve a
pasar por el matcher y por _convertir_unidad actuales. O sea que arrastra:
  - las guardas de matching agregadas después de que se cargaron esos datos
    (numérica, dominios de marca, calificadores excluyentes)
  - las conversiones de presentación (packs de tornillos, bolsas por kilo)

Solo entran los ítems que el matcher de hoy aceptaría automáticamente
(score >= 85) y cuya unidad no quede ambigua — la misma regla que aplica el
pipeline en vivo.

Correr:  cd api && python reconstruir_precios_2026-07-22.py [--aplicar]
"""
import os, sys, json
from collections import Counter
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
import main
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")
UMBRAL_AUTO = 85.0


def traer(tabla, cols="*"):
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


def construir():
    items = traer("presupuesto_items")
    presus = {p["id"]: p for p in traer("presupuestos")}
    dens = main._get_denominaciones()
    print(f"items: {len(items)}   presupuestos: {len(presus)}   aliases: {len(dens)}")

    filas, motivos, detalle = [], Counter(), []
    for it in items:
        texto = (it.get("texto_original") or "").strip()
        precio = it.get("precio")
        if not texto or not precio or float(precio) <= 0:
            motivos["sin_texto_o_precio"] += 1
            continue

        # top_n=3 como producción, NO 1: la ventana de candidatos de
        # fuzz_process.extract es top_n*3, y con 3 candidatos los aliases
        # largos con token_set crudo 100 (ej. "caño estructural … hierro
        # 12x12", conf 90) la llenan antes que los buenos; la guarda numérica
        # los capa después y no queda ningún automático. Con la ventana de 9
        # el resultado coincide con lo que haría /analizar-v2.
        ms = main._match_v2(texto, dens, top_n=3) or []
        if not ms:
            motivos["sin_match"] += 1
            continue
        top = ms[0]
        score = float(top.get("score") or 0)
        codigo = top["codigo_material"]
        if score < UMBRAL_AUTO:
            motivos["score_bajo"] += 1
            detalle.append({"texto": texto, "codigo": codigo, "score": round(score, 1),
                            "motivo": "score_bajo"})
            continue

        cant = it.get("cantidad") or 1
        pu, cant2, unidad, nota, ambigua = main._convertir_unidad(
            codigo, texto, it.get("unidad_raw") or "", float(precio), float(cant))
        if ambigua:
            motivos["unidad_ambigua"] += 1
            detalle.append({"texto": texto, "codigo": codigo, "score": round(score, 1),
                            "motivo": "unidad_ambigua"})
            continue

        pr = presus.get(it.get("presupuesto_id")) or {}
        filas.append({
            "proveedor":       pr.get("proveedor_detectado") or "SIN PROVEEDOR",
            "codigo_material": codigo,
            "unidad":          unidad,
            "precio":          round(float(pu), 4),
            "cantidad":        max(1, round(float(cant2))),
            "pdf_origen":      pr.get("nombre_archivo"),
            "conversion_aplicada": nota,
            "moneda":          "ARS",
            "texto_original":  texto,
            "origen":          "pipeline",
        })
        motivos["aceptado"] += 1

    return filas, motivos, detalle


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv
    filas, motivos, detalle = construir()

    print("\nRESULTADO:")
    for k, v in motivos.most_common():
        print(f"  {k:22} {v}")

    codigos = {f["codigo_material"] for f in filas}
    porcod = Counter(f["codigo_material"] for f in filas)
    prov_por_cod = {}
    for f in filas:
        prov_por_cod.setdefault(f["codigo_material"], set()).add(f["proveedor"])
    multi = [c for c, p in prov_por_cod.items() if len(p) >= 2]
    con_conv = sum(1 for f in filas if f["conversion_aplicada"])

    print(f"\nfilas a insertar:        {len(filas)}")
    print(f"materiales distintos:    {len(codigos)}")
    print(f"multi-proveedor (Indice): {len(multi)}")
    print(f"con conversion aplicada: {con_conv}")

    ruta = os.path.join(DATA, "reconstruccion_precios_2026-07-22.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"filas": filas, "descartes": detalle}, f, ensure_ascii=False, indent=1)
    print(f"\n-> {ruta}")

    if not aplicar:
        print("\n(simulacion — correr con --aplicar)")
        raise SystemExit(0)

    ya = sb.table("precios_historicos").select("id").eq("origen", "pipeline").execute().data or []
    if ya:
        print(f"\nYa hay {len(ya)} filas origen='pipeline'. Abortado para no duplicar.")
        print("Si es un re-run intencional, borrarlas antes por sus IDs.")
        raise SystemExit(1)

    for i in range(0, len(filas), 200):
        sb.table("precios_historicos").insert(filas[i:i + 200]).execute()
    print(f"\nInsertadas {len(filas)} filas origen='pipeline'.")
