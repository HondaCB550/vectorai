# -*- coding: utf-8 -*-
"""Regresión de matching: los productos que contaminaron precios_historicos
(detectado 20-07-2026 armando el Índice) NO deben volver a rutear al código
equivocado.

Origen del bug: aliases `usuario_*` confirmados a mano rutearon productos
distintos a códigos de material pesado —
  - "CEMENTO BLANCO …"      → CONS101 (cemento gris)   [debía ser CONS129]
  - "PLACA CEMENTICIA …"    → CONS101                  [no es cemento]
  - "BASECOAT WEBER …"      → CONS101                  [es revoque]
  - "VARILLA ROSCADA FTR 12"→ CONS118 (hierro Ø12)     [es varilla Fischer]
Se limpiaron por ID (backup_aliases_envenenados_2026-07-20.json). Este test
fija el comportamiento correcto con el set de aliases ya saneado, así una
re-confirmación equivocada o una regresión del matcher se detecta antes del deploy.

Los casos de chapa (CH001) y tornillos (T00x) son de BASE DE UNIDAD, no de
matching — se tratan aparte (conversion_unidades / revisión dedicada).

Correr:  cd api && python -m pytest test_matching_contaminacion.py -q
   (o):  cd api && python test_matching_contaminacion.py
"""
import main


def _den(codigo, texto):
    """Construye un alias enriquecido como lo hace _get_denominaciones()."""
    norm = main._prep_v2(texto)
    return {
        "codigo_material": codigo,
        "denominacion": texto,
        "denominacion_norm": norm,
        "nums": main.extract_nums(norm),
        "confianza": 85,
    }


# Set de aliases SANEADO (representa el estado de material_denominaciones post-limpieza)
DENOMINACIONES = [
    # CONS101 — cemento gris común
    _den("CONS101", "cemento"),
    _den("CONS101", "cemento loma negra x 25 kg"),
    _den("CONS101", "cemento avellaneda x 25kg"),
    # CONS129 — cemento blanco (destino correcto)
    _den("CONS129", "cemento blanco"),
    _den("CONS129", "cemento blanco x 25kg"),
    _den("CONS129", "cemento blanco cimsa x 25 kg"),
    _den("CONS129", "cemento bco x 25 kg pinguino"),
    # CONS118 — hierro aleteado Ø12
    _den("CONS118", "hierro aleteado"),
    _den("CONS118", "diametro 12"),
    _den("CONS118", "hierro adn 12mm"),
    _den("CONS118", "hierro gerdau 12 mm"),
    # Decoys de otros diámetros / familias
    _den("CONS136", "hierro aleteado diametro 8"),
    _den("CONS101", "cemento albañileria x 25 kg"),
]


def _mejor(texto):
    r = main._match_v2(texto, DENOMINACIONES, top_n=3)
    return r[0] if r else None


def _codigos_automaticos(texto):
    return {m["codigo_material"] for m in main._match_v2(texto, DENOMINACIONES, top_n=5)
            if m["nivel"] == "automatico"}


def test_cemento_blanco_cimsa_va_a_CONS129_no_CONS101():
    m = _mejor("CEMENTO BLANCO CIMSA X 25 KG")
    assert m is not None and m["codigo_material"] == "CONS129", m


def test_cemento_blanco_pinguino_va_a_CONS129():
    m = _mejor("CEMENTO BCO X 25 KG PINGUINO")
    assert m is not None and m["codigo_material"] == "CONS129", m


def test_cemento_gris_sigue_yendo_a_CONS101():
    m = _mejor("CEMENTO LOMA NEGRA X 25 KG")
    assert m is not None and m["codigo_material"] == "CONS101", m


def test_varilla_roscada_fischer_no_matchea_hierro_aleteado():
    # No debe entrar solo (automático) a CONS118 — no es hierro aleteado.
    assert "CONS118" not in _codigos_automaticos("VARILLA ROSCADA FISCHER FTR 12 X 160")


def test_placa_cementicia_no_matchea_cemento_automatico():
    autos = _codigos_automaticos("PLACA CEMENTICIA VOLCANBOARD 8MM 1200 X 2400MM")
    assert "CONS101" not in autos and "CONS129" not in autos, autos


# ── Resistencia del MATCHER, no limpieza de datos ────────────────────────────
# Los tests de arriba corren sobre un set de aliases ya saneado: con datos
# limpios el matching acierta solo, así que pasaban incluso sin ninguna guarda
# en el matcher. No podían detectar el fallo que dicen cubrir, y se vio: la
# limpieza fue el 20-07, y el 22-07 se volvió a confirmar "cemento bco x 25 kg
# pinguino" contra CONS101 con score 100, con estos tests en verde.
#
# Los de acá abajo meten el alias contaminado A PROPÓSITO: fijan que aunque
# alguien vuelva a confirmar mal, el producto no pueda entrar AUTOMÁTICO al
# código equivocado. Sin la guarda de calificadores, fallan.

DENOMINACIONES_CONTAMINADAS = DENOMINACIONES + [
    # Lo que efectivamente había en la base el 22-07 (borrado por ID, ver
    # api/data/backup_matches_cemento_2026-07-22.json)
    _den("CONS101", "cemento bco x 25 kg pinguino"),
    _den("CONS101", "cemento blanco cimsa x 25 kg"),
]

# El maestro: la guarda de calificadores valida el texto del proveedor contra
# el nombre canónico del material, no contra el alias (que puede estar
# contaminado). En producción lo llena _get_denominaciones() al armar los
# sintéticos; acá se simulan los códigos que usan estos tests.
main._calif_material.update({
    "CONS101": main._calificadores_en("CEMENTO 25KG"),
    "CONS129": main._calificadores_en("CEMENTO BLANCO 25KG"),
    "CONS118": main._calificadores_en("HIERRO ALETEADO 12"),
    "CONS136": main._calificadores_en("HIERRO ALETEADO 8"),
})


def _automaticos_contaminado(texto):
    return {m["codigo_material"] for m in
            main._match_v2(texto, DENOMINACIONES_CONTAMINADAS, top_n=5)
            if m["nivel"] == "automatico"}


def test_blanco_no_entra_automatico_a_CONS101_aunque_el_alias_este_contaminado():
    # El caso real: el PDF decía "CEMENTO BCO X 25 KG PINGUINO", el precio
    # ($60.850) estaba bien extraído, y entró como cemento común a 7x el precio.
    assert "CONS101" not in _automaticos_contaminado("CEMENTO BCO X 25 KG PINGUINO")


def test_blanco_cimsa_no_entra_automatico_a_CONS101_con_alias_contaminado():
    assert "CONS101" not in _automaticos_contaminado("CEMENTO BLANCO CIMSA X 25 KG")


def test_refractario_no_entra_automatico_a_cemento_comun():
    # "FARA CEMENTO REFRACTARIO HUMEDO X 20KG" a $62.240 fue a CONS101.
    autos = _automaticos_contaminado("FARA CEMENTO REFRACTARIO HUMEDO X 20KG")
    assert "CONS101" not in autos and "CONS129" not in autos, autos


def test_cemento_comun_sigue_entrando_automatico_con_alias_contaminado():
    # La guarda no debe volverse un freno general: el cemento gris, que no
    # lleva calificador, tiene que seguir matcheando solo.
    m = _mejor("CEMENTO LOMA NEGRA X 25 KG")
    assert m is not None and m["codigo_material"] == "CONS101", m
    assert m["nivel"] == "automatico", m


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn(); print(f"  OK  {fn.__name__}")
        except AssertionError as e:
            fallos += 1; print(f"FALLA {fn.__name__}: {e}")
    print(f"\n{len(fns)-fallos}/{len(fns)} tests OK")
    raise SystemExit(1 if fallos else 0)
