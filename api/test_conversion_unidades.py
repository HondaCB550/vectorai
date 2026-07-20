# -*- coding: utf-8 -*-
"""Regresión de _convertir_unidad — reglas de Pablo 20-07-2026:
  - tornillos T00x → canónico POR UNIDAD (dividir packs/cajas a $/unidad)
  - chapas       → canónico POR METRO LINEAL (chapa entera ÷ largo)
Detectado armando el Índice: precios_historicos mezclaba $/unidad con $/caja
(tornillos) y $/metro con $/chapa entera (chapas).

Correr:  cd api && python -m pytest test_conversion_unidades.py -q
   (o):  cd api && python test_conversion_unidades.py
"""
import main

# Inyecta el cache de conversiones que en prod viene de conversion_unidades.
main._conv_extra = {
    "T002": {"unidad_comercial": "un", "factor": 10000, "unidad_base": "UN"},
    "T004": {"unidad_comercial": "un", "factor": 8000,  "unidad_base": "UN"},
    "CH001": {"unidad_comercial": "ml", "factor": 1, "unidad_base": "ML"},
    "CH019": {"unidad_comercial": "ml", "factor": 1, "unidad_base": "ML"},
    "INS100": {"unidad_comercial": "m", "factor": 100, "unidad_base": "rollo 100m"},
}


def conv(codigo, desc, unidad, pu, cant=1.0):
    return main._convertir_unidad(codigo, desc, unidad, pu, cant)


# ── Tornillos: todo a precio por unidad ───────────────────────────────────────
def test_tornillo_pack_100_a_unidad():
    pu, cant, u, nota, amb = conv("T002", "TORN T1 PTA MECHA x 100 un.", "", 1313.15, 1)
    assert abs(pu - 13.1315) < 1e-3 and u == "UN" and not amb, (pu, u, nota)

def test_tornillo_caja_10000_a_unidad():
    pu, cant, u, nota, amb = conv("T002", "CAJA T1 MECHA - 8 X 9/16 X 10.000", "", 262477.99, 3)
    assert abs(pu - 26.247799) < 1e-3 and u == "UN" and not amb, (pu, u, nota)

def test_tornillo_ya_por_unidad_se_deja():
    pu, cant, u, nota, amb = conv("T004", "TORNILLO T1 MECHA 10X3/4", "UN", 23.28, 11728)
    assert pu == 23.28 and u == "UN" and not amb, (pu, u, nota)


# ── Chapas: todo a precio por metro lineal ────────────────────────────────────
def test_chapa_entera_6m_a_metro():
    pu, cant, u, nota, amb = conv("CH001", "CHAPA ACAN POLIP X 6 ML", "", 96817.24, 8)
    assert abs(pu - 16136.206) < 1e-2 and u == "ML" and abs(cant - 48) < 1e-6 and not amb, (pu, cant, u, nota)

def test_chapa_ya_por_metro_x1_se_deja():
    pu, cant, u, nota, amb = conv("CH019", "CHAPA CINCALUM C25 ACAN X 1,00 MTS", "", 12892.91, 233)
    assert pu == 12892.91 and u == "ML" and not amb, (pu, u, nota)

def test_chapa_por_metro_marcador_xm():
    pu, cant, u, nota, amb = conv("CH019", "CHAPA C25 ACANALADA CINCALUM x m", "", 15029.17, 233)
    assert pu == 15029.17 and u == "ML" and not amb, (pu, u, nota)

def test_chapa_galvanizada_6mts_a_metro():
    pu, cant, u, nota, amb = conv("CH001", "SINUSOIDAL GALVANIZADA C-25 X 6.00 MTS", "", 90000.0, 2)
    assert abs(pu - 15000.0) < 1e-6 and u == "ML" and not amb, (pu, u, nota)


# ── El modo 'm' (caños/cables → tira/rollo) sigue intacto ──────────────────────
def test_modo_m_cano_por_metro_a_rollo():
    pu, cant, u, nota, amb = conv("INS100", "CABLE 2,5MM X METRO", "ML", 500.0, 100)
    assert abs(pu - 50000.0) < 1e-6 and u == "rollo 100m" and not amb, (pu, u, nota)


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
