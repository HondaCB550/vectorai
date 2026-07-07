"""Tests de regresión de los parsers de extracción (extraer_regex).

Cada parser se prueba con líneas REALES tomadas de los PDFs de los proveedores.
Correr con:  cd api && python -m pytest test_extraccion_parsers.py -q
(o sin pytest:  python test_extraccion_parsers.py)

Si un cambio en los regex rompe un formato, esto lo detecta antes del deploy.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "matching"))
from extraer_pdf_texto import extraer_regex, extraer_lineas, _es_documento_sin_precios  # noqa: E402


def _uno(texto):
    items = extraer_regex(texto)
    assert len(items) == 1, f"esperaba 1 item, extraje {len(items)}: {items!r} de {texto!r}"
    return items[0]


def _consistente(it):
    assert it["pu"] > 0, f"pu invalido: {it}"
    assert abs(it["pu"] * it["cant"] - it["total"]) <= max(1.0, 0.01 * it["total"]), \
        f"pu*cant != total: {it}"


# ── Carosio ERP "Presupuesto centro" (sanitarios) ─────────────────────────────

def test_carosio_presu_basico():
    it = _uno("SI00050 60-100020000 MTS TUBO DE 20 SIGAS 4301.28 4.00 ML 17,205.12")
    assert it["desc"] == "MTS TUBO DE 20 SIGAS"
    assert it["cant"] == 4.0 and it["pu"] == 4301.28 and it["total"] == 17205.12
    assert it["cod"] == "60-100020000"
    assert it.get("unidad") == "ML"
    _consistente(it)


def test_carosio_presu_linea_corrupta_no_matchea():
    # Texto interleaveado del ERP: no debe producir item
    items = extraer_regex(
        "DUKE0039 C AM04 CAMARA CDE HINSAPECSCICONO PVCM GRÚISS DOLORES PIN41A236M.73AR3.00 U 123,710.18")
    assert items == []


# ── Casa Alfonsín ──────────────────────────────────────────────────────────────

def test_alfonsin_con_codigo_y_descuento():
    it = _uno("4,00 240019 TUBO 20MM P/GAS VANTEC+ . 5668,75 - 6,00% 5328,63 21314,50")
    assert it["desc"].startswith("TUBO 20MM P/GAS VANTEC+")
    assert it["cant"] == 4.0 and it["pu"] == 5328.63 and it["total"] == 21314.50
    assert it["cod"] == "240019"
    _consistente(it)


def test_alfonsin_sin_codigo():
    it = _uno("1,00 ROWA TANGO SFL 20 599803,44 - 0,00% 599803,44 599803,44")
    assert it["desc"].startswith("ROWA TANGO")
    assert it["cod"] == ""
    _consistente(it)


def test_alfonsin_codigo_alfanumerico_descuento_pegado():
    it = _uno("3,00 ZALCPV10 KIT CAMARA INSPECCION 3. 2 65849,14 -20,00% 52679,31 158037,94")
    assert it["cod"] == "ZALCPV10"
    assert it["cant"] == 3.0 and it["pu"] == 52679.31
    _consistente(it)


# ── Viejo Bueno (cantidad y código pegados) ────────────────────────────────────

def test_viejobueno_cant_codigo_pegados():
    it = _uno("1 1.00411110001 BIODIGESTOR RP 600 LTS 520014 ROTOPLAS 888,516.39 10.00 10.00 719,698.27 719,698.28")
    assert it["cant"] == 1.0 and it["pu"] == 719698.27
    assert "BIODIGESTOR" in it["desc"]
    assert it["cod"] == "411110001"
    _consistente(it)


def test_viejobueno_cantidad_mayor():
    it = _uno("3 16.00161710000 CAÑO PN20 MAGNUM 20 X 4 MTS ACQUA SYSTEM 8,106.58 10.00 10.00 6,566.33 105,061.31")
    assert it["cant"] == 16.0
    _consistente(it)


# ── Maderera Lobos (bonif -10,00 sin %, importe unitario ya bonificado) ───────

def test_madlobos_basico():
    it = _uno("9,00 PERFIL FLEJE CRUZ DE S.ANDRES 50MM ESP 0.52 (rollo x 50 mts) 42.667,85 -10,00 38.401,06 345.609,54")
    assert it["desc"].startswith("PERFIL FLEJE CRUZ")
    assert it["cant"] == 9.0 and it["pu"] == 38401.06 and it["total"] == 345609.54
    _consistente(it)


def test_madlobos_cantidad_con_miles():
    it = _uno("3.200,00 ARANDELAS PLASTICAS CON TAPA EIFS (bolsa x 2500) 26,43 -10,00 23,78 76.104,58")
    assert it["cant"] == 3200.0 and it["pu"] == 23.78
    _consistente(it)


def test_madlobos_oferta():
    it = _uno("8,00 TEL-HEX T1 10X3/4 S/ARA X 4000 OFERTA 187.928,57 -10,00 169.135,71 1.353.085,68")
    assert "TEL-HEX" in it["desc"]
    assert it["cant"] == 8.0 and it["pu"] == 169135.71
    _consistente(it)


# ── Fagua (código EAN pegado a la descripción, precios con $) ─────────────────

def test_fagua_ean_pegado():
    it = _uno("8435223412558TAPA DE INSPECCION 60X60 ALUM PLAQUIA 1.00 $ 67,687.54 $ 67,687.54")
    assert it["desc"] == "TAPA DE INSPECCION 60X60 ALUM PLAQUIA"
    assert it["cod"] == "8435223412558"
    _consistente(it)


def test_fagua_codigo_corto():
    it = _uno("5570 TENSOR PARA CRUZ DE SAN ANDRES BARBIERI 18.00 $ 989.54 $ 17,811.72")
    assert it["desc"] == "TENSOR PARA CRUZ DE SAN ANDRES BARBIERI"
    assert it["cant"] == 18.0
    _consistente(it)


def test_fagua_linea_continuacion_no_matchea():
    assert extraer_regex("13.2m2 ISOVER") == []
    assert extraer_regex("READ10120") == []


# ── EN SECO / GRUPO MMC ────────────────────────────────────────────────────────

def test_enseco():
    it = _uno("[BARBI9ZPBZD2T] FLEJE PARA CRUZ DE SAN ANDRES 50MM E0,94 X 50 MTS 9,00 Unidades 73.429,98 $ 660.869,78")
    assert "FLEJE" in it["desc"]
    assert it["cant"] == 9.0 and it["pu"] == 73429.98
    _consistente(it)


# ── Baukraft ───────────────────────────────────────────────────────────────────

def test_baukraft():
    it = _uno("1- 03140423 BANDA ACUSTICA TECNO 100MM X 25MTS 5.00 17,605.50 88,027.50")
    assert "BANDA ACUSTICA" in it["desc"]
    assert it["cant"] == 5.0 and it["pu"] == 17605.50
    _consistente(it)


# ── Carosio corralón ───────────────────────────────────────────────────────────

def test_carosio_corralon():
    it = _uno("1 BARB0141 BANDA ACUSTICA HIDRAULICA 100MM 35824.10 5.00 ML 179,120.50")
    assert "BANDA ACUSTICA" in it["desc"]
    assert it["cant"] == 5.0 and it["pu"] == 35824.10
    _consistente(it)


# ── Sauce Solo / formato europeo ───────────────────────────────────────────────

def test_europeo():
    it = _uno("023-0005-30 6 TUBO DE ALCANTARILLA 0.30 x 1.2 Mts. 39.818,20 238.909,20")
    assert "ALCANTARILLA" in it["desc"]
    assert it["cant"] == 6.0 and it["pu"] == 39818.20
    _consistente(it)


# ── Heurístico de líneas ───────────────────────────────────────────────────────

def test_lineas_heuristico_precio_al_final():
    items = extraer_lineas("PLACA CEMENTICIA 6MM 1.20X2.40 3 15.500,00")
    assert len(items) == 1
    assert items[0]["cant"] == 3


def test_lineas_heuristico_ignora_texto_normal():
    assert extraer_lineas("Condición de pago: EFECTIVO OF / DEBITO OF") == []


# ── Documento sin precios por ítem (EN SECO/GRUPO MMC solo DESCRIPCIÓN+CANTIDAD) ─

def test_sin_precios_en_seco_detectado():
    texto = (
        "DESCRIPCIÓN CANTIDAD\n"
        "[BARBI9ZPBZD2T] FLEJE PARA CRUZ DE SAN ANDRES 50MM E0,94 X 50 MTS 9,00 Unidades\n"
        "[BARBID9YCM90B] CARTELA 200 X 200 X 1,29 MM PERFORADA 80,00 Unidades\n"
        "[FIJACOIWJWRIU] TORN. HEX. PM 10 X 3/4\" 32.400,00 Unidades\n"
        "[LPJULRSX44] PLACA OSB APA 11,1 MM 1,22 X 2,44 MTS 175,00 Unidades\n"
        "[BARBI557A3HY4] PERFIL SOLERA 35MM X 2,60 MTS 150,00 Unidades\n"
        "[BARBIR2VOCWSY] PERFIL MONTANTE 34MM X 2,60 MTS 426,00 Unidades\n"
        "Total $ 52.885.396,83\n"
    )
    assert _es_documento_sin_precios(texto) is True


def test_sin_precios_no_falsea_documento_con_precios():
    # Un presupuesto con precio por línea NO debe marcarse como sin precios
    texto = (
        "CANTIDAD DESCRIPCIÓN P.UNIT TOTAL\n"
        "9,00 FLEJE PARA CRUZ 4301,28 38711,52\n"
        "80,00 CARTELA PERFORADA 1200,00 96000,00\n"
    )
    assert _es_documento_sin_precios(texto) is False


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        try:
            fn()
            print(f"  ok  {nombre}")
        except AssertionError as e:
            fallos += 1
            print(f"FALLO  {nombre}: {e}")
    print(f"\n{fallos} fallos")
    sys.exit(1 if fallos else 0)
