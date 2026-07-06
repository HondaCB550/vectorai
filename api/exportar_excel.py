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

NUM_FMT = '"$" #,##0'


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
    subtitulo: str = None,
) -> bytes:
    """
    Genera un Excel comparativo y devuelve los bytes del archivo.
    """
    titulo = titulo or f"VectorAI — Comparativa {datetime.now().strftime('%Y-%m-%d')}"
    fecha  = datetime.now().strftime("%d/%m/%Y")
    subtitulo = subtitulo or f"Generado el {fecha} · Precios sin IVA · VectorAI"

    wb = Workbook()
    ws = wb.active
    ws.title = "Comparativa"

    # Columnas: Rubro(oculto) | Material | Cant. | Unidad | prov1..N | Mejor precio | Ahorro
    n_prov     = len(proveedores)
    col_rubro  = 1
    col_mat    = 2
    col_cant   = 3
    col_unidad = 4
    col_prov0  = 5
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
    c = ws.cell(2, 1, subtitulo)
    c.fill  = _fill(COLOR_HEADER)
    c.font  = _font(color="BFC8E6", size=9, italic=True)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=2)
    ws.row_dimensions[2].height = 18

    # ── Fila 3: vacía ─────────────────────────────────────────────────────────
    ws.row_dimensions[3].height = 6

    # ── Fila 4: encabezados de columnas ───────────────────────────────────────
    headers = ["Rubro", "Material", "Cant.", "Unidad"] + proveedores + ["Mejor precio", "Ahorro s/IVA"]
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
        cant    = row.get("cant", 1) or 1
        unidad  = row.get("unidad", "")
        precios = row.get("precios", {})
        mejor   = row.get("mejor_proveedor", "")
        ahorro  = row.get("ahorro", 0) or 0

        precios_vals = {p: precios[p]["precio_sin_iva"] * cant for p in proveedores if p in precios}
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

        c = ws.cell(current_row, col_cant, cant if cant != 1 else "")
        c.font = _font(size=9)
        c.alignment = Alignment(horizontal="center", vertical="center")

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
    ws.column_dimensions[get_column_letter(col_rubro)].width  = 0.5
    ws.column_dimensions[get_column_letter(col_mat)].width    = 42
    ws.column_dimensions[get_column_letter(col_cant)].width   = 7
    ws.column_dimensions[get_column_letter(col_unidad)].width = 9
    for i in range(n_prov):
        ws.column_dimensions[get_column_letter(col_prov0 + i)].width = 18
    ws.column_dimensions[get_column_letter(col_mejor)].width  = 18
    ws.column_dimensions[get_column_letter(col_ahorro)].width = 16

    # ── Hojas de compras: una por proveedor con sus ítems ganadores ──────────
    _agregar_hojas_compras(wb, comparativo, proveedores, subtitulo)

    # ── Exportar a bytes ──────────────────────────────────────────────────────
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


_INVALIDOS_HOJA = set('[]:*?/\\')


def _nombre_hoja(nombre: str) -> str:
    limpio = "".join(ch for ch in (nombre or "") if ch not in _INVALIDOS_HOJA).strip()
    return (f"Pedido {limpio}")[:31] or "Pedido"


def _agregar_hojas_compras(wb, comparativo: list[dict], proveedores: list[str], subtitulo: str = None):
    """Listado de compras: una hoja por proveedor con SOLO los materiales donde
    ese proveedor tiene el mejor precio — el pedido listo para mandarle."""
    for prov in proveedores:
        filas = [r for r in comparativo
                 if r.get("mejor_proveedor") == prov and prov in r.get("precios", {})]
        if not filas:
            continue
        ws = wb.create_sheet(_nombre_hoja(prov))

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
        c = ws.cell(1, 1, f"Pedido — {prov}")
        c.fill = _fill(COLOR_HEADER)
        c.font = _font(bold=True, color=COLOR_TEXTO_W, size=14)
        c.alignment = Alignment(vertical="center", horizontal="left", indent=2)
        ws.row_dimensions[1].height = 26

        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=5)
        c = ws.cell(2, 1, ((subtitulo + " · ") if subtitulo else "") +
                    "Solo ítems donde este proveedor tiene el mejor precio")
        c.font = _font(size=8, italic=True, color="666666")

        headers = ["Material", "Cant.", "Unidad", "Precio unit.", "Subtotal"]
        for j, h in enumerate(headers, start=1):
            c = ws.cell(4, j, h)
            c.font = _font(bold=True, size=9)
            c.fill = _fill(COLOR_SUBHDR)
            c.alignment = Alignment(horizontal="left" if j == 1 else "right")

        fila = 5
        total = 0.0
        for r in sorted(filas, key=lambda x: (x.get("rubro") or "", x.get("material") or "")):
            precio = r["precios"][prov]["precio_sin_iva"]
            cant = r.get("cant") or r["precios"][prov].get("cant") or 1
            subtotal = round(precio * cant, 2)
            total += subtotal
            ws.cell(fila, 1, r.get("material", "")).font = _font(size=9)
            for j, (val, fmt) in enumerate([(cant, None), (r.get("unidad", ""), None),
                                            (precio, NUM_FMT), (subtotal, NUM_FMT)], start=2):
                c = ws.cell(fila, j, val)
                c.font = _font(size=9)
                c.alignment = Alignment(horizontal="right")
                if fmt:
                    c.number_format = fmt
            fila += 1

        fila += 1
        ws.cell(fila, 1, f"TOTAL PEDIDO ({len(filas)} ítems)").font = _font(bold=True, size=10)
        for j in range(1, 5):
            ws.cell(fila, j).fill = _fill(COLOR_MEJOR)
        c = ws.cell(fila, 5, round(total, 2))
        c.number_format = NUM_FMT
        c.font = _font(bold=True, size=10)
        c.fill = _fill(COLOR_MEJOR)
        c.alignment = Alignment(horizontal="right")

        ws.column_dimensions["A"].width = 46
        for col, w in (("B", 8), ("C", 9), ("D", 14), ("E", 14)):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = "A5"
