#!/usr/bin/env python3
"""Extraer ítems de PDFs con texto (Baukraft, Carosio, y cualquier PDF con tabla).

Estrategia de extracción (en orden de prioridad):
  1. extract_tables() de pdfplumber → detecta tablas con bordes explícitos.
     Funciona para cualquier proveedor que genere PDFs con tabla estructurada.
  2. Patrones regex por proveedor conocido (Baukraft, Carosio) → fallback.
  3. Para PDFs escaneados (sin texto extraíble) → usar visión directa con la
     herramienta Read sobre el JPG/PNG, no este script.

Uso:
    python extraer_pdf_texto.py <archivo.pdf>
    → imprime JSON con {fecha, iva_detectado, suma_lineas, n_items,
                        items: [{cod, desc, cant, pu, total}]}
"""
import sys
import json
import re
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    print("Falta pdfplumber. pip install pdfplumber --break-system-packages", file=sys.stderr)
    sys.exit(1)

# Patrones de fecha
RE_FECHA = [
    re.compile(r"Fecha\s*[:.]?\s*(\d{1,2})/(\d{1,2})/(\d{4})"),
    re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})"),
]

# ── Patrones regex para proveedores conocidos ──────────────────────────────────

# Baukraft: "1- 03140423 BANDA ACUSTICA TECNO 100MM X 25MTS 5.00 17,605.50 88,027.50"
RE_BAUKRAFT = re.compile(
    r"^\s*\d+[-.]?\s*(\S+)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$"
)
# Carosio: "1 BARB0141 BANDA ACUSTICA HIDRAULICA 100MM 35824.10 5.00 ML 179,120.50"
RE_CAROSIO = re.compile(
    r"^\s*\d+\s+(\S+)\s+(.+?)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+\S+\s+([\d,]+\.\d+)\s*$"
)
# Sauce Solo / formato europeo: "023-0005-30 6 TUBO DE ALCANTARILLA 0.30 x 1.2 Mts. 39.818,20 238.909,20"
RE_EUROPEO = re.compile(
    r"^\s*(\S+)\s+(\d+)\s+(.+?)\s+((?:\d{1,3}\.)*\d{1,3},\d{2})\s+((?:\d{1,3}\.)*\d{1,3},\d{2})\s*$"
)

# EN SECO / GRUPO MMC (formato 2026):
# "[BARBI9ZPBZD2T] FLEJE PARA CRUZ DE SAN ANDRES 50MM E0,94 X 50 MTS 9,00 Unidades 73.429,98 $ 660.869,78"
# Números europeos; el código entre corchetes puede faltar en alguna línea.
RE_ENSECO = re.compile(
    r"^\s*(?:\[([A-Z0-9]+)\]\s+)?(\S.+?)\s+"
    r"((?:\d{1,3}\.)*\d{1,3},\d{2})\s+(?:Unidades?|ML|MTS?|M2|M3|KG|UN)\s+"
    r"((?:\d{1,3}\.)*\d{1,3},\d{2})\s+\$\s*((?:\d{1,3}\.)*\d{1,3},\d{2})\s*$",
    re.I,
)

RE_PRECIO = re.compile(r"^[\d,]+\.\d{2}$|^[\d.]+,\d{2}$")

# Artículo de PDF: "H ORMIGON" → "HORMIGON", "F IBRAKRETE" → "FIBRAKRETE"
RE_SPLIT_WORD = re.compile(r'\b([A-Z]) ([A-Z]{3,})\b')

# Código entre corchetes al inicio de descripción: "[BARBI9ZPBZD2T] FLEJE PARA..."
RE_BRACKET_COD = re.compile(r'^\[([A-Z0-9\s]+)\]\s*(.+)$', re.DOTALL)

# Sufijos de unidad después de un número: "9,00 Unidades" → "9,00"
RE_UNIDAD_SUFIJO = re.compile(r'^([\d.,]+)\s+(?:Unidades?|Mts?\.?|Kg\.?|m2|m3|ml|gl|lts?\.?|un\.?|pz\.?)\s*$', re.I)

# Notas de proveedor que no son ítems
RE_NOTA_PROVEEDOR = re.compile(
    r'producto bajo pedido|demora entre|solo para retiro|horario de retiro|'
    r'condici[oó]n de pago|validez del presupuesto|cotizaci[oó]n sujeta|'
    r'la responsabilidad|p[aá]gina\s*\d|aclaraciones',
    re.I
)


def _fix_split_words(s: str) -> str:
    """Repara artefactos de PDF donde una letra queda separada del resto de la palabra."""
    return RE_SPLIT_WORD.sub(r'\1\2', s)


def _limpiar_celda(s) -> str:
    """Limpia una celda de tabla:
    - Quita símbolos monetarios ($, pesos, etc.)
    - Convierte "9,00 Unidades" → "9,00"
    - Quita espacios y saltos de línea internos
    """
    if s is None:
        return ""
    s = str(s).strip()
    # Quitar símbolo $ y espacios antes del número
    s = re.sub(r'^\$\s*', '', s)
    s = re.sub(r'^ARS\s*', '', s, flags=re.I)
    # Limpiar saltos de línea internos (EN SECO tiene notas en segunda línea de la celda)
    # Tomar solo la primera línea si hay salto
    s = s.split('\n')[0].strip()
    # Quitar sufijo de unidad: "9,00 Unidades" → "9,00"
    m = RE_UNIDAD_SUFIJO.match(s)
    if m:
        s = m.group(1)
    return s


def _extraer_cod_desc(raw: str) -> tuple[str, str]:
    """Extrae código entre corchetes y descripción de celdas como '[BARBI9Z] FLEJE...'"""
    if not raw:
        return "", ""
    raw = raw.strip()
    # Tomar solo la primera línea (ignorar notas de proveedor en líneas siguientes)
    lineas = [l.strip() for l in raw.split('\n') if l.strip()]
    # Filtrar líneas que son notas del proveedor
    desc_lineas = [l for l in lineas if not RE_NOTA_PROVEEDOR.search(l)]
    if not desc_lineas:
        return "", ""
    primera = desc_lineas[0]
    m = RE_BRACKET_COD.match(primera)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", primera


def parse_num(s: str) -> float:
    """Parsea números en formato americano (12,892.91) y europeo (12.892,91)."""
    s = str(s).replace(" ", "").strip()
    if "," in s and "." in s:
        if s.rindex(",") > s.rindex("."):
            # Europeo: 39.818,20 → 39818.20
            s = s.replace(".", "").replace(",", ".")
        else:
            # Americano: 12,892.91 → 12892.91
            s = s.replace(",", "")
    elif "," in s:
        # Solo coma: si hay exactamente 1-2 dígitos al final → decimal europeo
        if re.search(r",\d{1,2}$", s):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    return float(s)


def _es_numero(s: str) -> bool:
    try:
        parse_num(s)
        return True
    except (ValueError, AttributeError):
        return False


def _es_precio(val: str | None) -> bool:
    if val is None:
        return False
    val = str(val).strip()
    return bool(RE_PRECIO.match(val)) and parse_num(val) > 10


# ── Extracción genérica por tablas ────────────────────────────────────────────

def _inferir_columnas(tabla: list[list]) -> dict | None:
    """Analiza la tabla e intenta inferir qué columna es código, descripción, precio.

    Devuelve dict con índices: {cod, desc, pu, cant, total} o None si no puede.
    """
    if len(tabla) < 3:
        return None

    n_cols = max(len(row) for row in tabla)
    if n_cols < 3:
        return None

    # Estadísticas por columna (excluyendo fila 0 = posible header)
    datos = tabla[1:]
    pct_num   = []  # % de celdas numéricas
    avg_len   = []  # largo promedio del texto
    avg_valor = []  # valor numérico promedio (para distinguir precios de cantidades)

    for col in range(n_cols):
        # _limpiar_celda antes de analizar (maneja "$", "Unidades", etc.)
        valores = [_limpiar_celda(r[col]) if col < len(r) and r[col] else "" for r in datos]
        valores = [v for v in valores if v]
        if not valores:
            pct_num.append(0); avg_len.append(0); avg_valor.append(0)
            continue
        nums = [parse_num(v) for v in valores if _es_numero(v)]
        pct_num.append(len(nums) / len(valores))
        avg_len.append(sum(len(v) for v in valores) / len(valores))
        avg_valor.append(sum(nums) / len(nums) if nums else 0)

    # Descripción: mayor avg_len entre columnas con pct_num < 0.3
    desc_idx = max(
        (i for i in range(n_cols) if pct_num[i] < 0.3),
        key=lambda i: avg_len[i],
        default=None
    )
    if desc_idx is None:
        return None

    # Columnas numéricas (pct_num > 0.5), excluyendo descripción
    num_cols = [i for i in range(n_cols) if i != desc_idx and pct_num[i] > 0.5]
    if len(num_cols) < 2:
        return None

    # Precio unitario: mayor avg_valor entre columnas numéricas
    pu_idx = max(num_cols, key=lambda i: avg_valor[i])

    # Total: segunda mayor avg_valor (si hay ≥3 cols numéricas, suele ser más grande que PU)
    total_idx = None
    remaining_num = [i for i in num_cols if i != pu_idx]
    if remaining_num:
        total_idx = max(remaining_num, key=lambda i: avg_valor[i])

    # Cantidad: si queda alguna columna numérica pequeña
    cant_idx = None
    leftover = [i for i in num_cols if i not in (pu_idx, total_idx)]
    if leftover:
        cant_idx = min(leftover, key=lambda i: avg_valor[i])

    # Código: columna corta alfanumérica antes de la descripción, o después
    cod_idx = None
    for i in range(n_cols):
        if i in (desc_idx, pu_idx, total_idx, cant_idx):
            continue
        sample = [str(r[i]).strip() for r in datos if i < len(r) and r[i]]
        if sample and all(len(v) <= 20 for v in sample):
            cod_idx = i
            break

    if desc_idx is None or pu_idx is None:
        return None

    return {"cod": cod_idx, "desc": desc_idx, "pu": pu_idx,
            "cant": cant_idx, "total": total_idx}


def _parsear_tabla_generica(tabla: list[list]) -> list[dict]:
    """Convierte una tabla de pdfplumber en lista de ítems."""
    if not tabla or len(tabla) < 2:
        return []

    cols = _inferir_columnas(tabla)
    if not cols:
        return []

    items = []
    for row in tabla[1:]:  # skip header
        def get_raw(idx):
            if idx is None or idx >= len(row):
                return None
            return str(row[idx]).strip() if row[idx] else None

        def get(idx):
            return _limpiar_celda(get_raw(idx))

        desc_raw = get_raw(cols["desc"])

        # Saltar filas que son notas del proveedor
        if desc_raw and RE_NOTA_PROVEEDOR.search(desc_raw):
            continue

        # Extraer código entre corchetes y descripción limpia
        cod_bracket, desc_clean = _extraer_cod_desc(desc_raw or "")

        pu_raw = get(cols["pu"])

        if not desc_clean or not pu_raw or not _es_numero(pu_raw):
            continue
        if len(desc_clean) < 3:
            continue

        try:
            pu = parse_num(pu_raw)
        except ValueError:
            continue

        if pu <= 0:
            continue

        cant_raw = get(cols["cant"])
        total_raw = get(cols["total"])
        # Código: preferir el del corchete, si no el de la columna dedicada
        cod_col = get(cols["cod"]) if cols.get("cod") is not None else None
        cod_final = cod_bracket or cod_col or ""

        try:
            cant = parse_num(cant_raw) if cant_raw and _es_numero(cant_raw) else 1.0
        except ValueError:
            cant = 1.0

        try:
            total = parse_num(total_raw) if total_raw and _es_numero(total_raw) else round(pu * cant, 2)
        except ValueError:
            total = round(pu * cant, 2)

        items.append({
            "cod":   cod_final,
            "desc":  _fix_split_words(desc_clean),
            "cant":  cant,
            "pu":    pu,
            "total": total,
        })

    return items


def extraer_tablas(pdf_path: str) -> list[dict]:
    """Método 1: extracción por tablas con bordes explícitos (pdfplumber default)."""
    items = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tabla in (page.extract_tables() or []):
                found = _parsear_tabla_generica(tabla)
                items.extend(found)
    return items


def extraer_tablas_texto(pdf_path: str) -> list[dict]:
    """Método 1b: tablas detectadas por alineación de texto (sin bordes explícitos).

    Cubre PDFs exportados desde Excel, ERP o software que no dibuja cuadrículas.
    Típico en Molber, JMA Perfiles, Maderera Lobos, etc.
    """
    items = []
    settings = {
        "vertical_strategy":   "text",
        "horizontal_strategy": "text",
        "snap_tolerance":       3,
        "join_tolerance":       3,
        "min_words_vertical":   3,
        "min_words_horizontal": 1,
        "intersection_tolerance": 3,
    }
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                tablas = page.extract_tables(settings) or []
                for tabla in tablas:
                    found = _parsear_tabla_generica(tabla)
                    items.extend(found)
            except Exception:
                continue
    return items


# Precio al final de línea: "12.345,67" o "12,345.67" o "1234.67" o "1234,67"
RE_PRECIO_EOL = re.compile(
    r'(?:(?:\d{1,3}[.]\d{3})+[,]\d{2}|'   # europeo con miles: 12.345,67
    r'(?:\d{1,3}[,]\d{3})+[.]\d{2}|'       # americano con miles: 12,345.67
    r'\d+[.]\d{2}|'                          # solo punto decimal: 1234.67
    r'\d+[,]\d{2})$'                         # solo coma decimal: 1234,67
)

# Token numérico genérico (cantidad, código numérico, etc.)
RE_NUM_TOKEN = re.compile(r'^\d[\d.,]*\d$|^\d+$')


def _parsear_linea_libre(line: str) -> dict | None:
    """Intenta extraer un ítem de una línea de texto libre.

    Lógica: los últimos tokens de la línea que sean numéricos son precio/cantidad/total.
    Todo lo anterior es la descripción.
    Mínimo: descripción de 4+ chars + 1 precio > 10.
    """
    tokens = line.strip().split()
    if len(tokens) < 2:
        return None

    # Recolectar tokens numéricos del final hacia atrás
    trailing = []
    i = len(tokens) - 1
    while i >= 0 and RE_NUM_TOKEN.match(tokens[i]):
        try:
            v = parse_num(tokens[i])
            trailing.insert(0, v)
            i -= 1
        except (ValueError, AttributeError):
            break

    if not trailing:
        return None

    # Al menos un valor > 10 (descarta líneas que solo tienen cantidades pequeñas)
    if max(trailing) < 10:
        return None

    # Descripción: tokens antes del grupo numérico trailing
    desc_tokens = tokens[:i + 1]
    if not desc_tokens:
        return None
    desc = " ".join(desc_tokens)
    # Filtrar líneas muy cortas o que son solo números/códigos
    if len(desc) < 4 or re.fullmatch(r'[\d\-/\.]+', desc):
        return None
    # Descartar si la descripción es solo una letra o número de ítem
    if len(desc_tokens) == 1 and len(desc) <= 3:
        return None

    # Asignar cant / pu / total según cuántos trailing numbers hay
    if len(trailing) == 1:
        pu   = trailing[0]
        cant = 1.0
    elif len(trailing) == 2:
        # Dos valores: si el primero parece cantidad (< 500, entero o medio entero), es cant
        a, b = trailing
        if a < 500 and (a == int(a) or a % 0.5 == 0) and b > a:
            cant, pu = a, b
        else:
            cant, pu = 1.0, max(a, b)  # tomar el mayor como precio
    else:
        # Tres o más: primer pequeño = cant, el del medio = pu, último = total
        a, b, c = trailing[0], trailing[1], trailing[-1]
        if a < 500 and (a == int(a) or a % 0.5 == 0):
            cant, pu = a, b
        else:
            cant, pu = 1.0, b

    if pu <= 0:
        return None

    return {
        "cod":   "",
        "desc":  _fix_split_words(desc),
        "cant":  cant,
        "pu":    pu,
        "total": round(pu * cant, 2),
    }


def extraer_lineas(texto: str) -> list[dict]:
    """Método 3: heurístico línea por línea para PDFs sin estructura tabular.

    Solo acepta líneas cuyo último token sea un precio bien formateado (RE_PRECIO_EOL),
    para evitar falsos positivos de líneas de texto normal con algún número.
    """
    items = []
    for line in texto.splitlines():
        line = line.strip()
        if not line:
            continue
        # El último token debe tener formato de precio (con coma o punto decimal)
        last_token = line.split()[-1]
        if not RE_PRECIO_EOL.match(last_token):
            continue
        parsed = _parsear_linea_libre(line)
        if parsed:
            items.append(parsed)
    return items


# ── Extracción por regex (fallback proveedores conocidos) ─────────────────────

def extraer_regex(texto: str) -> list[dict]:
    """Método 2: regex para Baukraft, Carosio y formato europeo (Sauce Solo)."""
    items = []
    for line in texto.splitlines():
        for patron, parser in [
            (RE_ENSECO,   "enseco"),
            (RE_BAUKRAFT, "baukraft"),
            (RE_CAROSIO,  "carosio"),
            (RE_EUROPEO,  "europeo"),
        ]:
            m = patron.match(line)
            if not m:
                continue
            if parser == "enseco":
                cod, desc, cant, pu, total = m.groups()
                items.append({
                    "cod": (cod or "").strip(), "desc": _fix_split_words(desc.strip()),
                    "cant": parse_num(cant), "pu": parse_num(pu), "total": parse_num(total),
                })
            elif parser == "baukraft":
                cod, desc, cant, pu, total = m.groups()
                items.append({
                    "cod": cod, "desc": _fix_split_words(desc.strip()),
                    "cant": float(cant), "pu": parse_num(pu), "total": parse_num(total),
                })
            elif parser == "carosio":
                cod, desc, pu, cant, total = m.groups()
                items.append({
                    "cod": cod, "desc": _fix_split_words(desc.strip()),
                    "cant": parse_num(cant), "pu": parse_num(pu), "total": parse_num(total),
                })
            else:  # europeo
                cod, cant, desc, pu, total = m.groups()
                items.append({
                    "cod": cod, "desc": _fix_split_words(desc.strip()),
                    "cant": float(cant), "pu": parse_num(pu), "total": parse_num(total),
                })
            break
    return items


# ── Calidad de extracción (para elegir entre métodos) ─────────────────────────

def _desc_es_codigo(desc: str) -> bool:
    """True si la 'descripción' parece en realidad un código de proveedor.

    Un código (ej. '023-0005-30', '002-0009-CI-ACA') no tiene ninguna palabra
    alfabética de 4+ letras. Una descripción real casi siempre tiene una
    (TUBO, CHAPA, ARENA, HIERRO, CEMENTO, MALLA, etc.).
    """
    d = (desc or "").strip()
    if not d:
        return True
    return not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}", d)


def _calidad(items: list[dict]) -> int:
    """Puntaje de calidad de una extracción, para elegir el método que mejor
    entendió la tabla. Premia dos señales independientes por ítem:

      1. Descripción real (no un código de proveedor).
      2. Precios consistentes: pu * cant ≈ total. Esto detecta cuando el parser
         confundió la columna de importe con la de precio unitario (un bug típico
         de _inferir_columnas, que toma como 'unitario' la columna de mayor valor
         = el importe). El regex por proveedor parsea bien y queda consistente.
    """
    puntaje = 0
    for it in items:
        if not _desc_es_codigo(it.get("desc", "")):
            puntaje += 1
        pu    = it.get("pu") or 0
        cant  = it.get("cant") or 0
        total = it.get("total") or 0
        if pu > 0 and cant > 0 and total > 0 and abs(pu * cant - total) <= max(1.0, 0.01 * total):
            puntaje += 1
    return puntaje


# ── Función principal ──────────────────────────────────────────────────────────

def extraer(pdf_path: str) -> dict:
    fecha = None
    items = []
    metodo = "desconocido"

    with pdfplumber.open(pdf_path) as pdf:
        all_text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    # Fecha
    for rx in RE_FECHA:
        m = rx.search(all_text)
        if m:
            d, mo, y = m.groups()
            try:
                fecha = datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass

    # Métodos 1 / 1b / 2: se evalúan los tres y se elige el de MEJOR CALIDAD
    # (más descripciones reales, no códigos). Antes ganaba el primero no vacío,
    # pero tablas_texto a veces parte la descripción en columnas y termina
    # tomando el código como descripción (rompía el formato Sauce y similares);
    # elegir por calidad hace que en ese caso gane el regex, que parsea bien.
    # En empate de (calidad, n_items) gana el método más prioritario por el
    # orden en que se agregan a la lista (bordes > texto > regex).
    candidatos: list[tuple[str, list[dict]]] = []

    items_bordes = extraer_tablas(pdf_path)
    if items_bordes:
        candidatos.append(("tablas_bordes", items_bordes))

    items_texto = extraer_tablas_texto(pdf_path)
    if items_texto:
        candidatos.append(("tablas_texto", items_texto))

    if all_text.strip():
        items_regex = extraer_regex(all_text)
        if items_regex:
            candidatos.append(("regex", items_regex))

    if candidatos:
        metodo, items = max(candidatos, key=lambda c: (_calidad(c[1]), len(c[1])))

    # Método 3: heurístico línea por línea (último recurso para texto plano)
    if not items and all_text.strip():
        items = extraer_lineas(all_text)
        if items:
            metodo = "lineas_heuristico"

    # Detectar IVA comparando suma de líneas vs total declarado en el PDF
    suma = sum(it["total"] for it in items)
    iva_detectado = "ASUMIDO 1,105"
    # Acepta formato americano (52,885,396.83) y europeo (52.885.396,83)
    rx_total = re.search(r"TOTAL[\s\$:]+([\d,]+\.\d{2}|[\d.]+,\d{2})", all_text, re.I)
    if rx_total:
        total_pdf = parse_num(rx_total.group(1))
        if abs(suma - total_pdf) < 1:
            iva_detectado = "PRECIOS C/IVA INCLUIDO"
        elif abs(suma * 1.21 - total_pdf) < 5:
            iva_detectado = "PRECIOS S/IVA + 21%"
        elif abs(suma * 1.105 - total_pdf) < 5:
            iva_detectado = "PRECIOS S/IVA + 10,5%"

    return {
        "fecha_presupuesto": fecha,
        "iva_detectado":     iva_detectado,
        "suma_lineas":       round(suma, 2),
        "n_items":           len(items),
        "metodo_extraccion": metodo,
        "items":             items,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    res = extraer(sys.argv[1])
    print(json.dumps(res, indent=2, ensure_ascii=False))
