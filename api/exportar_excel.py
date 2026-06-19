"""
exportar_excel.py — Genera un Excel comparativo de presupuestos VectorAI
Devuelve bytes del .xlsx, listo para enviar como respuesta HTTP.
"""
from io import BytesIO
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter

# Paleta
COLOR_HEADER   = "263150"   # azul oscuro
COLOR_SUBHDR   = "EDF0F5"   # gris claro
COLOR_MEJOR    = "C6F6D5"   # verde claro
COLOR_RUBRO    = "E8EDF5"   # azul muy claro
COLOR_BLANCO   = "FFFFFF"
COLOR_TEXTO_W  = "FFFFFF"

COLORES_PROV = [
    "3373C2",  # azul
    "D45C00",  # naranja
    "2EA15E",  # verde
    "993399",  # violeta
    "BF2626",  # rojo
    "4D99B3",  # celeste
]

NUM_FMT = '#,##0'


def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def _font(bold=False, color="000000", size=9, italic=False) -> Font:
    return Font(bold=bold, color=color, size=size, italic=italic)


def _border_bottom() -> Border:
    side = Side(style="medium", color="B0B5BE")
    return Border(bottom=side)


def generar_excel_comparativo(
    comparativo: list[dict],
    proveedores: list[str],
    titulo: str = None,
) -> bytes:
    """
    Genera un Excel comparativo y devuelve los bytes del archivo.
    """
    titulo = titulo or f"VectorAI — Comparativa {datetime.now().strftime('%Y-%m-%d')}"
    fecha  = datetime.now().strftime("%d/%m/%Y")

    wb = Workbook()
    ws = wb.active
    ws.title = "Comparativa"

    # Columnas: Rubro(oculto) | Material | Unidad | prov1..N | Mejor precio | Ahorro
    n_prov     = len(proveedores)
    col_rubro  = 1
    col_mat    = 2
    col_unidad = 3
    col_prov0  = 4
    col_mejor  = col_prov0 + n_prov
    col_ahorro = col_mejor + 1
    total_cols = col_ahorro

    # ── Fila 1: título ────────────────────────────────────────────────────────
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    c = ws.cell(1, 1, titulo)
    c.fill  = _fill(COLOR_HEADER)
    c.font  = _font(bold=True, color=COLOR_TEXTO_W, size=14)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=2)
    ws.row_dimensions[1].height = 36

    # ── Fila 2: subtítulo ─────────────────────────────────────────────────────
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
    c = ws.cell(2, 1, f"Generado el {fecha} · Precios sin IVA · VectorAI")
    c.fill  = _fill(COLOR_HEADER)
    c.font  = _font(color="BFC8E6", size=9, italic=True)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=2)
    ws.row_dimensions[2].height = 18

    # ── Fila 3: vacía ─────────────────────────────────────────────────────────
    ws.row_dimensions[3].height = 6

    # ── Fila 4: encabezados de columnas ───────────────────────────────────────
    headers = ["Rubro", "Material", "Unidad"] + proveedores + ["Mejor precio", "Ahorro s/IVA"]
    for col_idx, label in enumerate(headers, start=1):
        c = ws.cell(4, col_idx, label)
        c.alignment = Alignment(horizontal="center" if col_idx > 3 else "left",
                                vertical="center", indent=1 if col_idx <= 3 else 0)
        c.border = _border_bottom()
        if col_idx == col_rubro:
            c.fill = _fill(COLOR_SUBHDR)
            c.font = _font(bold=True, size=9)
        elif col_idx == col_mat:
            c.fill = _fill(COLOR_SUBHDR)
            c.font = _font(bold=True, size=9)
        elif col_idx == col_unidad:
            c.fill = _fill(COLOR_SUBHDR)
            c.font = _font(bold=True, size=9)
        elif col_idx < col_mejor:
            prov_i = col_idx - col_prov0
            c.fill = _fill(COLORES_PROV[prov_i % len(COLORES_PROV)])
            c.font = _font(bold=True, color=COLOR_TEXTO_W, size=9)
        else:
            c.fill = _fill(COLOR_SUBHDR)
            c.font = _font(bold=True, size=9)
    ws.row_dimensions[4].height = 20

    # Freeze rows 1-4 y columna Material
    ws.freeze_panes = "C5"

    # ── Filas de datos ────────────────────────────────────────────────────────
    current_row = 5
    ultimo_rubro = None
    totales = {p: 0.0 for p in proveedores}

    for row in comparativo:
        rubro   = row.get("rubro", "")
        mat     = row.get("material", "")
        unidad  = row.get("unidad", "")
        precios = row.get("precios", {})
        mejor   = row.get("mejor_proveedor", "")
        ahorro  = row.get("ahorro", 0) or 0

        precios_vals = {p: precios[p]["precio_sin_iva"] for p in proveedores if p in precios}
        precio_min = min(precios_vals.values()) if len(precios_vals) > 1 else None

        # Separador de rubro
        if rubro != ultimo_rubro:
            if ultimo_rubro is not None:
                current_row += 1  # fila vacía entre rubros
            for col in range(1, total_cols + 1):
                c = ws.cell(current_row, col)
                c.fill = _fill(COLOR_RUBRO)
                if col == col_mat:
                    c.value = rubro.upper()
                    c.font  = _font(bold=True, size=9, color="3A5080")
                    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws.row_dimensions[current_row].height = 16
            current_row += 1
            ultimo_rubro = rubro

        # Fila de datos
        ws.cell(current_row, col_rubro, "").fill = _fill(COLOR_BLANCO)

        c = ws.cell(current_row, col_mat, mat)
        c.font = _font(size=9)
        c.alignment = Alignment(horizontal="left", vertical="center", indent=2, wrap_text=True)

        c = ws.cell(current_row, col_unidad, unidad)
        c.font = _font(size=9)
        c.alignment = Alignment(horizontal="center", vertical="center")

        for i, prov in enumerate(proveedores):
            val = precios_vals.get(prov)
            col = col_prov0 + i
            is_mejor = (precio_min is not None and val is not None
                        and val == precio_min and len(precios_vals) > 1)
            if val is not None:
                totales[prov] += val
                c = ws.cell(current_row, col, val)
                c.number_format = NUM_FMT
            else:
                c = ws.cell(current_row, col, "—")
            c.font = _font(bold=is_mejor, size=9)
            c.alignment = Alignment(horizontal="right", vertical="center")
            if is_mejor:
                c.fill = _fill(COLOR_MEJOR)

        # Mejor proveedor
        c = ws.cell(current_row, col_mejor, mejor or "")
        c.font = _font(bold=bool(mejor), size=9,
                       color="1A804A" if mejor else "000000")
        c.alignment = Alignment(horizontal="center", vertical="center")

        # Ahorro
        if ahorro:
            c = ws.cell(current_row, col_ahorro, ahorro)
            c.number_format = NUM_FMT
            c.font = _font(size=9, color="1A804A")
        else:
            ws.cell(current_row, col_ahorro, "")
        ws.cell(current_row, col_ahorro).alignment = Alignment(
            horizontal="right", vertical="center")

        ws.row_dimensions[current_row].height = 15
        current_row += 1

    # ── Fila de totales ───────────────────────────────────────────────────────
    current_row += 1
    ws.cell(current_row, col_mat, "TOTAL (matches OK + REVISAR)").font = _font(bold=True, size=9)
    ws.cell(current_row, col_mat).fill = _fill(COLOR_SUBHDR)
    ws.cell(current_row, col_mat).alignment = Alignment(horizontal="left", indent=2)
    ws.cell(current_row, col_rubro).fill = _fill(COLOR_SUBHDR)
    ws.cell(current_row, col_unidad).fill = _fill(COLOR_SUBHDR)

    for i, prov in enumerate(proveedores):
        col = col_prov0 + i
        c = ws.cell(current_row, col, round(totales[prov], 2))
        c.number_format = NUM_FMT
        c.font = _font(bold=True, size=9)
        c.fill = _fill(COLOR_SUBHDR)
        c.alignment = Alignment(horizontal="right")

    ws.cell(current_row, col_mejor).fill = _fill(COLOR_SUBHDR)
    ws.cell(current_row, col_ahorro).fill = _fill(COLOR_SUBHDR)
    ws.row_dimensions[current_row].height = 18

    # ── Anchos de columna ─────────────────────────────────────────────────────
    ws.column_dimensions[get_column_letter(col_rubro)].width  = 0.5   # oculto visualmente
    ws.column_dimensions[get_column_letter(col_mat)].width    = 42
    ws.column_dimensions[get_column_letter(col_unidad)].width = 9
    for i in range(n_prov):
        ws.column_dimensions[get_column_letter(col_prov0 + i)].width = 18
    ws.column_dimensions[get_column_letter(col_mejor)].width  = 18
    ws.column_dimensions[get_column_letter(col_ahorro)].width = 16

    # ── Exportar a bytes ──────────────────────────────────────────────────────
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
