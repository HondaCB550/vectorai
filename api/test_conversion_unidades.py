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
    "T005": {"unidad_comercial": "un", "factor": 6000,  "unidad_base": "UN"},
    "CH001": {"unidad_comercial": "ml", "factor": 1, "unidad_base": "ML"},
    "CH019": {"unidad_comercial": "ml", "factor": 1, "unidad_base": "ML"},
    "INS100": {"unidad_comercial": "m", "factor": 100, "unidad_base": "rollo 100m"},
    "CONS104": {"unidad_comercial": "kg", "factor": 5,  "unidad_base": "KG"},
    "TER482": {"unidad_comercial": "kg", "factor": 25, "unidad_base": "KG"},
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


# ── T005: los 4 formatos reales de pack que trae el mismo material ────────────
# Caso testigo del curado 22-07-2026. Las cuatro cotizaciones son del MISMO
# tornillo en presentaciones distintas y entraban al histórico sin normalizar:
# la brecha entre la más cara y la más barata daba 1.003.075%.
def test_t005_caja_6000_sin_palabra_unidad():
    pu, cant, u, nota, amb = conv("T005", "CAJA ALAS C/ESTRIAS - 8 X 1,1/4 X 6.000", "", 348804.0, 1)
    assert abs(pu - 58.134) < 1e-3 and u == "UN" and not amb, (pu, u, nota)

def test_t005_pack_100_con_u():
    pu, cant, u, nota, amb = conv("T005", "TORN ALAS P/SUPERB. 8 x 1-1/4 x 100 u", "", 4265.0, 1)
    assert abs(pu - 42.65) < 1e-3 and u == "UN" and not amb, (pu, u, nota)

def test_t005_pack_100_desnudo_al_final():
    pu, cant, u, nota, amb = conv("T005", "ALAS CON ESTRIAS 8 X 1,1/4 X 100", "", 6260.0, 1)
    assert abs(pu - 62.60) < 1e-3 and u == "UN" and not amb, (pu, u, nota)

def test_t005_bolsa_100_entre_parentesis():
    pu, cant, u, nota, amb = conv("T005", 'TORNILLO ALAS 8X1 1/4" (BOLSA X 100)- TEL', "", 3310.0, 1)
    assert abs(pu - 33.10) < 1e-3 and u == "UN" and not amb, (pu, u, nota)


# ── Guardas: lo que NO es un pack de unidades ─────────────────────────────────
def test_no_confunde_bolsa_por_kilos():
    # "Bolsa X 25KG" es peso, no cantidad de unidades. Sin la guarda el regex
    # backtrackeaba y devolvía n=2 (los dos primeros dígitos de "25KG").
    assert main._detectar_pack("***Nueva Bolsa X 25KG*** CEMENTO AVELLANEDA") is None
    assert main._detectar_pack("CONSTRUCOR IMPERMEABLE BOLSA x 25 Kgs") is None

def test_no_confunde_cadena_de_medidas():
    # "229X114X50" son dimensiones pegadas: sin espacio antes de la x no es pack.
    assert main._detectar_pack("LADRILLO REF 229X114X50") is None
    assert main._detectar_pack("CUARZO X25") is None

def test_no_confunde_numero_no_redondo_al_final():
    # Un número suelto al final que no es múltiplo de 25 no cuenta como pack.
    assert main._detectar_pack("PERFIL PGC 70 x 0.94 x 6") is None


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


# ── Bolsas: todo a precio por kilo ────────────────────────────────────────────
# Agregado en el curado 22-07-2026: el maestro fija una presentación (PASTINA
# 5KG, BASECOAT 25KG) pero los proveedores cotizan envases de 1, 25 o 30 kg.
def test_pastina_5kg_a_kilo():
    pu, cant, u, nota, amb = conv("CONS104", "PASTINA WEBER CLASSIC X 5KG COLOR", "", 11312.22, 1)
    assert abs(pu - 2262.444) < 1e-3 and u == "KG" and abs(cant - 5) < 1e-9 and not amb, (pu, cant, u, nota)

def test_pastina_1kg_se_deja():
    pu, cant, u, nota, amb = conv("CONS104", "PASTINA X1KG", "", 2000.66, 3)
    assert pu == 2000.66 and u == "KG" and cant == 3 and not amb, (pu, u, nota)

def test_basecoat_30kg_usa_el_peso_del_texto_no_el_del_maestro():
    # El maestro dice 25KG pero este proveedor vende de 30: manda el texto.
    pu, cant, u, nota, amb = conv("TER482", "WEBER REV BASE COAT GRIS X 30 KG", "", 38325.0, 2)
    assert abs(pu - 1277.5) < 1e-3 and u == "KG" and abs(cant - 60) < 1e-9 and not amb, (pu, cant, u, nota)

def test_basecoat_sin_peso_es_ambiguo():
    # "BASE COAT GRANITEX" no aclara envase → no se inventa, va a revisar.
    pu, cant, u, nota, amb = conv("TER482", "BASE COAT GRANITEX", "", 15837.10, 1)
    assert pu == 15837.10 and amb, (pu, u, nota, amb)

def test_peso_en_toneladas():
    assert abs(main._detectar_peso("ARENA NECO BOLSON X 1.2TN") - 1200.0) < 1e-6

def test_no_confunde_medida_con_peso():
    # "50mm/0.90" y "22,8 MTS" no son pesos.
    assert main._detectar_peso("SUNCHO FLEJE 50mm/0.90 X 50MTS") is None
    assert main._detectar_peso("CINTA FLEX 22,8 MTS") is None


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
