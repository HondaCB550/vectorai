"""
exportar_pdf.py — Genera un PDF comparativo de presupuestos VectorAI.
Devuelve bytes del .pdf, listo para enviar como respuesta HTTP.
"""
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

COLOR_HEADER  = colors.HexColor("#263150")
COLOR_SUBHDR  = colors.HexColor("#EDF0F5")
COLOR_MEJOR   = colors.HexColor("#C6F6D5")
COLOR_RUBRO   = colors.HexColor("#E8EDF5")
COLOR_BLANCO  = colors.white
COLOR_TEXTO_W = colors.white
COLOR_VERDE   = colors.HexColor("#1A804A")

COLORES_PROV = [
    colors.HexColor("#3373C2"),
    colors.HexColor("#D45C00"),
    colors.HexColor("#2EA15E"),
    colors.HexColor("#993399"),
    colors.HexColor("#BF2626"),
    colors.HexColor("#4D99B3"),
]

def _fmt(v: float) -> str:
    return f"$ {int(round(v)):,}".replace(",", ".")


def generar_pdf_comparativo(
    comparativo: list[dict],
    proveedores: list[str],
    titulo: str = None,
) -> bytes:
    titulo = titulo or f"VectorAI — Comparativa {datetime.now().strftime('%Y-%m-%d')}"
    fecha  = datetime.now().strftime("%d/%m/%Y")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    st_titulo = ParagraphStyle("titulo", fontSize=16, fontName="Helvetica-Bold",
                                textColor=COLOR_TEXTO_W, spaceAfter=0)
    st_sub    = ParagraphStyle("sub", fontSize=8, fontName="Helvetica",
                                textColor=colors.HexColor("#BFC8E6"), spaceAfter=0)
    st_mat    = ParagraphStyle("mat", fontSize=7.5, fontName="Helvetica",
                                leading=10, textColor=colors.HexColor("#1a1a2e"))
    st_rubro  = ParagraphStyle("rub", fontSize=7.5, fontName="Helvetica-Bold",
                                textColor=colors.HexColor("#3A5080"))
    st_num    = ParagraphStyle("num", fontSize=7.5, fontName="Helvetica",
                                alignment=TA_RIGHT)
    st_mejor  = ParagraphStyle("mej", fontSize=7.5, fontName="Helvetica-Bold",
                                textColor=COLOR_VERDE, alignment=TA_CENTER)
    st_hdr    = ParagraphStyle("hdr", fontSize=8, fontName="Helvetica-Bold",
                                textColor=COLOR_TEXTO_W, alignment=TA_CENTER)
    st_hdr_l  = ParagraphStyle("hdrl", fontSize=8, fontName="Helvetica-Bold",
                                textColor=colors.HexColor("#3A5080"), alignment=TA_LEFT)

    n_prov = len(proveedores)

    # ── Encabezado ──────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(titulo, st_titulo),
        Paragraph(f"Generado el {fecha} · Precios sin IVA · VectorAI", st_sub),
    ]]
    header_tbl = Table(header_data, colWidths=["60%", "40%"])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_HEADER),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (0, -1), 14),
        ("RIGHTPADDING",  (1, 0), (1, -1), 14),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))

    # ── Cabecera de columnas ─────────────────────────────────────────────────
    col_headers = [
        Paragraph("Material", st_hdr_l),
        Paragraph("Cant.", ParagraphStyle("c", fontSize=8, fontName="Helvetica-Bold",
                                          textColor=colors.HexColor("#3A5080"), alignment=TA_CENTER)),
    ]
    for i, p in enumerate(proveedores):
        col_headers.append(Paragraph(p, ParagraphStyle(
            f"ph{i}", fontSize=8, fontName="Helvetica-Bold",
            textColor=COLOR_TEXTO_W, alignment=TA_CENTER
        )))
    col_headers.append(Paragraph("Mejor", st_hdr_l))
    col_headers.append(Paragraph("Ahorro", ParagraphStyle(
        "ah", fontSize=8, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#3A5080"), alignment=TA_RIGHT
    )))

    # Anchos de columna — A4 portrait: 21cm - 3cm márgenes = 18cm útiles
    page_w = A4[0] - 3*cm
    prov_w = min(3.5*cm, (page_w - 5.5*cm - 2*cm) / max(n_prov, 1))
    col_widths = [5.5*cm, 1.4*cm] + [prov_w]*n_prov + [2.2*cm, 1.8*cm]

    # ── Filas de datos ───────────────────────────────────────────────────────
    table_data = [col_headers]
    table_styles = [
        # Encabezado
        ("BACKGROUND", (0, 0), (1, 0), COLOR_SUBHDR),
        ("BACKGROUND", (n_prov+2, 0), (-1, 0), COLOR_SUBHDR),
        ("LINEBELOW",  (0, 0), (-1, 0), 1, colors.HexColor("#B0B5BE")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("FONTSIZE",   (0, 0), (-1, -1), 7.5),
    ]
    for i, p in enumerate(proveedores):
        table_styles.append(("BACKGROUND", (2+i, 0), (2+i, 0), COLORES_PROV[i % len(COLORES_PROV)]))

    ultimo_rubro = None
    totales = {p: 0.0 for p in proveedores}
    row_idx = 1

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

        # Fila de rubro
        if rubro != ultimo_rubro:
            rubro_row = [Paragraph(rubro.upper(), st_rubro)] + [""] * (n_prov + 3)
            table_data.append(rubro_row)
            table_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), COLOR_RUBRO))
            table_styles.append(("SPAN", (0, row_idx), (-1, row_idx)))
            row_idx += 1
            ultimo_rubro = rubro

        # Fila de item
        cant_str = f"{int(cant)} {unidad}" if cant != 1 else unidad
        data_row = [
            Paragraph(mat, st_mat),
            Paragraph(cant_str, ParagraphStyle("cs", fontSize=7, alignment=TA_CENTER)),
        ]

        for i, prov in enumerate(proveedores):
            val = precios_vals.get(prov)
            is_mejor = (precio_min is not None and val is not None
                        and val == precio_min and len(precios_vals) > 1)
            if val is not None:
                totales[prov] += val
                cell = Paragraph(_fmt(val), ParagraphStyle(
                    f"v{i}", fontSize=7.5,
                    fontName="Helvetica-Bold" if is_mejor else "Helvetica",
                    textColor=COLOR_VERDE if is_mejor else colors.HexColor("#1a1a2e"),
                    alignment=TA_RIGHT
                ))
                if is_mejor:
                    table_styles.append(("BACKGROUND", (2+i, row_idx), (2+i, row_idx), COLOR_MEJOR))
            else:
                cell = Paragraph("—", ParagraphStyle("dash", fontSize=7.5,
                                  textColor=colors.HexColor("#CBD5E0"), alignment=TA_CENTER))
            data_row.append(cell)

        data_row.append(Paragraph(mejor or "", st_mejor))
        data_row.append(Paragraph(_fmt(ahorro) if ahorro else "", ParagraphStyle(
            "aho", fontSize=7.5, textColor=COLOR_VERDE, alignment=TA_RIGHT
        )))

        table_data.append(data_row)
        row_idx += 1

    # Fila de totales
    total_row = [Paragraph("TOTAL", ParagraphStyle("tot", fontSize=8,
                            fontName="Helvetica-Bold", textColor=colors.HexColor("#3A5080")))] + [""]
    for prov in proveedores:
        total_row.append(Paragraph(_fmt(totales[prov]), ParagraphStyle(
            "tv", fontSize=8, fontName="Helvetica-Bold", alignment=TA_RIGHT
        )))
    total_row += ["", ""]
    table_data.append(total_row)
    table_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), COLOR_SUBHDR))
    table_styles.append(("LINEABOVE", (0, row_idx), (-1, row_idx), 1, colors.HexColor("#B0B5BE")))

    main_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    main_table.setStyle(TableStyle(table_styles))

    story = [header_tbl, Spacer(1, 0.4*cm), main_table]
    doc.build(story)
    buf.seek(0)
    return buf.read()
