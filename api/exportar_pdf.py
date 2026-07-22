"""
exportar_pdf.py — Genera un PDF comparativo de presupuestos Vectorai.
Devuelve bytes del .pdf, listo para enviar como respuesta HTTP.

Diseño de marca: isologo (3 barras redondeadas navy/naranja, mismo dibujo que
frontend/components/Logo.tsx) + wordmark "Vectorai", encabezado blanco con
regla naranja. Con 4+ proveedores la página pasa a A4 apaisado.
"""
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                Spacer, Flowable, PageBreak)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from lista_compras import pedidos_por_proveedor, subtotal_fila

# Paleta de marca (Logo.tsx / IDENTIDAD.md)
COLOR_NAVY    = colors.HexColor("#1A2B4A")
COLOR_NARANJA = colors.HexColor("#E87022")
COLOR_GRIS    = colors.HexColor("#6B7280")
COLOR_LINEA   = colors.HexColor("#E2E6EE")

COLOR_SUBHDR  = colors.HexColor("#EDF0F5")
COLOR_MEJOR   = colors.HexColor("#C6F6D5")
COLOR_RUBRO   = colors.HexColor("#E8EDF5")
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

# Barras del isotipo en viewBox 0-100 (x, y, w, h) — y crece hacia abajo como en SVG
_ISO_BARRAS = [
    (18, 26, 64, 13, COLOR_NAVY),
    (30, 48, 40, 13, COLOR_NAVY),
    (40, 70, 20, 13, COLOR_NARANJA),
]


def _fmt(v: float) -> str:
    return f"$ {int(round(v)):,}".replace(",", ".")


class _HeaderVectorai(Flowable):
    """Encabezado de marca: isologo + wordmark, metadatos a la derecha,
    título y regla naranja. Fondo blanco."""

    ALTO = 60

    def __init__(self, ancho: float, titulo: str, meta: str):
        super().__init__()
        self.ancho  = ancho
        self.titulo = titulo
        self.meta   = meta

    def wrap(self, aw, ah):
        return self.ancho, self.ALTO

    def draw(self):
        c = self.canv
        # Isotipo (caja de 22pt, arriba a la izquierda)
        iso = 22.0
        esc = iso / 100.0
        iso_base = self.ALTO - iso
        for x, y, w, h, col in _ISO_BARRAS:
            c.setFillColor(col)
            c.roundRect(x * esc, iso_base + iso - (y + h) * esc,
                        w * esc, h * esc, (h * esc) / 2, fill=1, stroke=0)
        # Wordmark
        c.setFillColor(COLOR_NAVY)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(iso + 7, iso_base + 6, "Vectorai")
        # Metadatos a la derecha, alineados con el wordmark
        c.setFillColor(COLOR_GRIS)
        c.setFont("Helvetica", 8)
        c.drawRightString(self.ancho, iso_base + 8, self.meta)
        # Título
        c.setFillColor(COLOR_NAVY)
        c.setFont("Helvetica-Bold", 12.5)
        c.drawString(0, 12, self.titulo)
        # Regla: acento naranja + línea suave
        c.setFillColor(COLOR_NARANJA)
        c.rect(0, 0, 54, 2.4, fill=1, stroke=0)
        c.setFillColor(COLOR_LINEA)
        c.rect(54, 0.7, self.ancho - 54, 1, fill=1, stroke=0)


def _pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(COLOR_GRIS)
    canvas.drawString(doc.leftMargin, 0.85 * cm, "vectorai.com.ar")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.85 * cm,
                           f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


def generar_pdf_compras(
    comparativo: list[dict],
    proveedores: list[str] = None,
    titulo: str = None,
    subtitulo: str = None,
) -> bytes:
    """Lista de compras en PDF: el pedido de cada proveedor, uno por página.

    Una página por proveedor a propósito — el usuario imprime o reenvía la hoja
    del corralón que le corresponde sin mandarle lo que le cotizó la competencia.

    `proveedores` se ignora (llega por simetría con generar_pdf_comparativo):
    quiénes entran y en qué orden lo decide pedidos_por_proveedor().
    """
    from marca import titulo_visible as _tv, meta_visible as _mv
    titulo_visible = _tv(titulo)
    meta = _mv(subtitulo)

    pedidos = pedidos_por_proveedor(comparativo)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.2*cm, bottomMargin=1.5*cm,
        title=titulo or f"Vectorai — Lista de compras {datetime.now().strftime('%Y-%m-%d')}",
    )
    page_w = A4[0] - 3*cm

    st_mat   = ParagraphStyle("cmat", fontSize=8, fontName="Helvetica",
                              leading=10.5, textColor=colors.HexColor("#1a1a2e"))
    st_rubro = ParagraphStyle("crub", fontSize=7.5, fontName="Helvetica-Bold",
                              textColor=colors.HexColor("#3A5080"))
    st_num   = ParagraphStyle("cnum", fontSize=8, alignment=TA_RIGHT,
                              textColor=colors.HexColor("#1a1a2e"))
    st_cent  = ParagraphStyle("ccen", fontSize=8, alignment=TA_CENTER,
                              textColor=colors.HexColor("#1a1a2e"))
    st_hdr_l = ParagraphStyle("chdl", fontSize=8, fontName="Helvetica-Bold",
                              textColor=colors.HexColor("#3A5080"), alignment=TA_LEFT)
    st_hdr_r = ParagraphStyle("chdr", fontSize=8, fontName="Helvetica-Bold",
                              textColor=colors.HexColor("#3A5080"), alignment=TA_RIGHT)
    st_hdr_c = ParagraphStyle("chdc", fontSize=8, fontName="Helvetica-Bold",
                              textColor=colors.HexColor("#3A5080"), alignment=TA_CENTER)

    col_widths = [8.4*cm, 1.8*cm, 2.0*cm, 2.9*cm, 2.9*cm]

    story = [_HeaderVectorai(page_w, titulo_visible, meta), Spacer(1, 0.35*cm)]

    if not pedidos:
        story.append(Paragraph(
            "No hay ítems con proveedor ganador para armar la lista de compras.",
            ParagraphStyle("vacio", fontSize=9, textColor=COLOR_GRIS)))
        doc.build(story, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
        buf.seek(0)
        return buf.read()

    # Sin total de la compra completa: cada página se le manda a un proveedor, y
    # ver que su pedido es una fracción del total le revela cuánto se le compra
    # a la competencia. Ese número lo tiene el comprador en pantalla.
    for n, pedido in enumerate(pedidos):
        prov  = pedido["proveedor"]
        filas = pedido["filas"]

        if n > 0:
            story.append(PageBreak())
            story.append(_HeaderVectorai(page_w, titulo_visible, meta))
            story.append(Spacer(1, 0.35*cm))

        story.append(Paragraph(
            f"Pedido — {prov}",
            ParagraphStyle("pt", fontSize=11, fontName="Helvetica-Bold", textColor=COLOR_NAVY)))
        story.append(Paragraph(
            f"{pedido['n_items']} ítem{'s' if pedido['n_items'] != 1 else ''} · "
            f"solo los materiales donde tiene el mejor precio",
            ParagraphStyle("ps", fontSize=8, textColor=COLOR_GRIS)))
        story.append(Spacer(1, 0.22*cm))

        data = [[Paragraph("Material", st_hdr_l), Paragraph("Cant.", st_hdr_c),
                 Paragraph("Unidad", st_hdr_c), Paragraph("Precio unit.", st_hdr_r),
                 Paragraph("Subtotal", st_hdr_r)]]
        styles = [
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_SUBHDR),
            ("LINEBELOW",  (0, 0), (-1, 0), 1, colors.HexColor("#B0B5BE")),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ]

        ultimo_rubro = None
        idx = 1
        for f in filas:
            rubro = f.get("rubro") or ""
            if rubro != ultimo_rubro:
                data.append([Paragraph(rubro.upper(), st_rubro), "", "", "", ""])
                styles.append(("BACKGROUND", (0, idx), (-1, idx), COLOR_RUBRO))
                styles.append(("SPAN", (0, idx), (-1, idx)))
                idx += 1
                ultimo_rubro = rubro

            precio, cant, subtotal = subtotal_fila(f, prov)
            data.append([
                Paragraph(f.get("material") or "", st_mat),
                Paragraph(f"{cant:g}", st_cent),
                Paragraph(f.get("unidad") or "", st_cent),
                Paragraph(_fmt(precio), st_num),
                Paragraph(_fmt(subtotal), st_num),
            ])
            idx += 1

        data.append([
            Paragraph(f"TOTAL PEDIDO ({pedido['n_items']} ítems)",
                      ParagraphStyle("tp", fontSize=9, fontName="Helvetica-Bold",
                                     textColor=colors.HexColor("#3A5080"))),
            "", "", "",
            Paragraph(_fmt(pedido["total"]),
                      ParagraphStyle("tpv", fontSize=9, fontName="Helvetica-Bold",
                                     alignment=TA_RIGHT, textColor=COLOR_VERDE)),
        ])
        styles.append(("BACKGROUND", (0, idx), (-1, idx), COLOR_MEJOR))
        styles.append(("LINEABOVE",  (0, idx), (-1, idx), 1, colors.HexColor("#B0B5BE")))
        styles.append(("SPAN", (0, idx), (3, idx)))

        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle(styles))
        story.append(t)

    doc.build(story, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    buf.seek(0)
    return buf.read()


def generar_pdf_comparativo(
    comparativo: list[dict],
    proveedores: list[str],
    titulo: str = None,
    subtitulo: str = None,
) -> bytes:
    from marca import titulo_visible as _tv, meta_visible as _mv
    titulo_visible = _tv(titulo)
    meta = _mv(subtitulo)

    n_prov = len(proveedores)
    pagesize = landscape(A4) if n_prov >= 4 else A4

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=pagesize,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.2*cm, bottomMargin=1.5*cm,
        title=titulo or f"Vectorai — Comparativa {datetime.now().strftime('%Y-%m-%d')}",
    )

    st_mat    = ParagraphStyle("mat", fontSize=7.5, fontName="Helvetica",
                                leading=10, textColor=colors.HexColor("#1a1a2e"))
    st_rubro  = ParagraphStyle("rub", fontSize=7.5, fontName="Helvetica-Bold",
                                textColor=colors.HexColor("#3A5080"))
    st_mejor  = ParagraphStyle("mej", fontSize=7, fontName="Helvetica-Bold",
                                textColor=COLOR_VERDE, alignment=TA_CENTER, leading=9)
    st_hdr_l  = ParagraphStyle("hdrl", fontSize=8, fontName="Helvetica-Bold",
                                textColor=colors.HexColor("#3A5080"), alignment=TA_LEFT)

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

    # Anchos de columna — la suma cierra exacta contra el ancho útil de página.
    page_w  = pagesize[0] - 3*cm
    w_cant, w_mejor, w_ahorro = 1.4*cm, 2.4*cm, 1.9*cm
    fijas   = w_cant + w_mejor + w_ahorro
    prov_w  = min(3.2*cm, (page_w - 5.0*cm - fijas) / max(n_prov, 1))
    prov_w  = max(prov_w, 1.8*cm)
    w_mat   = page_w - fijas - prov_w * n_prov
    col_widths = [w_mat, w_cant] + [prov_w]*n_prov + [w_mejor, w_ahorro]

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

    story = [
        _HeaderVectorai(page_w, titulo_visible, meta),
        Spacer(1, 0.35*cm),
        main_table,
    ]
    doc.build(story, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    buf.seek(0)
    return buf.read()
