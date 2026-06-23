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

RE_PRECIO = re.compile(r"^[\d,]+\.\d{2}$|^[\d.]+,\d{2}$")

# Artículo de PDF: "H ORMIGON" → "HORMIGON", "F IBRAKRETE" → "FIBRAKRETE"
RE_SPLIT_WORD = re.compile(r'\b([A-Z]) ([A-Z]{3,})\b')


def _fix_split_words(s: str) -> str:
    """Repara artefactos de PDF donde una letra queda separada del resto de la palabra."""
    return RE_SPLIT_WORD.sub(r'\1\2', s)


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
        valores = [str(r[col]).strip() if col < len(r) and r[col] else "" for r in datos]
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
        def get(idx):
            if idx is None or idx >= len(row):
                return None
            return str(row[idx]).strip() if row[idx] else None

        desc = get(cols["desc"])
        pu_raw = get(cols["pu"])

        if not desc or not pu_raw or not _es_numero(pu_raw):
            continue
        if len(desc) < 3:
            continue

        try:
            pu = parse_num(pu_raw)
        except ValueError:
            continue

        if pu <= 0:
            continue

        cant_raw = get(cols["cant"])
        total_raw = get(cols["total"])
        cod_raw = get(cols["cod"])

        try:
            cant = parse_num(cant_raw) if cant_raw and _es_numero(cant_raw) else 1.0
        except ValueError:
            cant = 1.0

        try:
            total = parse_num(total_raw) if total_raw and _es_numero(total_raw) else round(pu * cant, 2)
        except ValueError:
            total = round(pu * cant, 2)

        items.append({
            "cod":   cod_raw or "",
            "desc":  _fix_split_words(desc),
            "cant":  cant,
            "pu":    pu,
            "total": total,
        })

    return items


def extraer_tablas(pdf_path: str) -> list[dict]:
    """Método 1: extracción por tablas estructuradas (pdfplumber.extract_tables)."""
    items = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tabla in (page.extract_tables() or []):
                found = _parsear_tabla_generica(tabla)
                items.extend(found)
    return items


# ── Extracción por regex (fallback proveedores conocidos) ─────────────────────

def extraer_regex(texto: str) -> list[dict]:
    """Método 2: regex para Baukraft, Carosio y formato europeo (Sauce Solo)."""
    items = []
    for line in texto.splitlines():
        for patron, parser in [
            (RE_BAUKRAFT, "baukraft"),
            (RE_CAROSIO,  "carosio"),
            (RE_EUROPEO,  "europeo"),
        ]:
            m = patron.match(line)
            if not m:
                continue
            if parser == "baukraft":
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

    # Método 1: tablas estructuradas (genérico, funciona para cualquier proveedor)
    items = extraer_tablas(pdf_path)
    if items:
        metodo = "tablas"

    # Método 2: regex proveedores conocidos (fallback)
    if not items and all_text.strip():
        items = extraer_regex(all_text)
        if items:
            metodo = "regex"

    # Detectar IVA comparando suma de líneas vs total declarado en el PDF
    suma = sum(it["total"] for it in items)
    iva_detectado = "ASUMIDO 1,105"
    rx_total = re.search(r"TOTAL[\s\$]+([\d,]+\.\d+)", all_text)
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
