"""
exportar_imagen.py — Genera una imagen JPG comparativa para compartir por WhatsApp/redes.
Devuelve bytes del .jpg, listo para enviar como respuesta HTTP.
Encabezado de marca (isologo + wordmark) desde marca.py.
"""
from io import BytesIO
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

import marca
from lista_compras import pedidos_por_proveedor, subtotal_fila

# Paleta
C_SUBHDR  = (237, 240, 245)
C_MEJOR   = (198, 246, 213)
C_RUBRO   = (232, 237, 245)
C_BLANCO  = (255, 255, 255)
C_TEXT    = (26, 26, 46)
C_GRAY    = (100, 116, 139)
C_VERDE   = (26, 128, 74)
C_BORDER  = (226, 232, 240)

COLORES_PROV = [
    (51, 115, 194),
    (212, 92, 0),
    (46, 161, 94),
    (153, 51, 153),
    (191, 38, 38),
    (77, 153, 179),
]

ROW_H     = 36
HDR_H     = 48
RUBRO_H   = 26
TITLE_H   = 100
PAD       = 16
COL_MAT   = 260
COL_CANT  = 80
COL_PROV  = 160
COL_MEJOR = 160
COL_AHORRO = 120


def _fmt(v: float) -> str:
    return f"$ {int(round(v)):,}".replace(",", ".")


def _get_font(size=13, bold=False):
    try:
        from PIL import ImageFont
        # Intentar fuente del sistema
        font_name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(font_name, size)
    except Exception:
        return ImageFont.load_default()


# Columnas de la lista de compras (más angosta que la comparativa: 5 fijas)
CC_MAT, CC_CANT, CC_UNID, CC_PU, CC_SUB = 300, 70, 80, 130, 140
CC_SECCION_H = 46   # alto del encabezado de cada proveedor
CC_GAP       = 22   # aire entre un proveedor y el siguiente


def generar_imagen_compras(
    comparativo: list[dict],
    proveedores: list[str] = None,
    titulo: str = None,
    subtitulo: str = None,
) -> bytes:
    """Lista de compras en JPG: los pedidos de todos los proveedores apilados
    en una sola imagen, para mandar por WhatsApp.

    A diferencia del PDF (una página por proveedor), acá va todo junto: un JPG
    es una sola imagen y partirlo en varias complicaría la descarga. Con muchos
    proveedores la imagen queda alta, que es el trade-off aceptado.

    `proveedores` se ignora (llega por simetría con generar_imagen_comparativo):
    quiénes entran y en qué orden lo decide pedidos_por_proveedor().
    """
    titulo_vis = marca.titulo_visible(titulo)
    meta       = marca.meta_visible(subtitulo)
    pedidos    = pedidos_por_proveedor(comparativo)

    total_w = PAD + CC_MAT + CC_CANT + CC_UNID + CC_PU + CC_SUB + PAD

    # Alto dinámico: por proveedor van encabezado + cabecera + una fila por
    # ítem + una por cada cambio de rubro + total, más el aire entre bloques.
    alto_bloques = 0
    for pedido in pedidos:
        rubros = len({(f.get("rubro") or "") for f in pedido["filas"]})
        alto_bloques += (CC_SECCION_H + HDR_H
                         + (len(pedido["filas"]) + rubros) * ROW_H
                         + ROW_H + CC_GAP)
    total_h = TITLE_H + 30 + max(alto_bloques, ROW_H) + PAD * 2

    img = Image.new("RGB", (total_w, total_h), C_BLANCO)
    d   = ImageDraw.Draw(img)

    f_title  = _get_font(18, bold=True)
    f_sub    = _get_font(11)
    f_bold   = _get_font(12, bold=True)
    f_normal = _get_font(12)
    f_rubro  = _get_font(10, bold=True)
    f_prov   = _get_font(14, bold=True)

    # ── Encabezado de marca (mismo que la comparativa) ───────────────────────
    iso = 26
    marca.dibujar_isotipo(d, PAD, 12, iso)
    f_marca = _get_font(17, bold=True)
    d.text((PAD + iso + 8, 12 + (iso - 17) // 2), "Vectorai", font=f_marca, fill=marca.NAVY)
    bbox = d.textbbox((0, 0), meta, font=f_sub)
    d.text((total_w - PAD - (bbox[2] - bbox[0]), 12 + (iso - 11) // 2), meta,
           font=f_sub, fill=marca.GRIS)
    d.text((PAD, 56), titulo_vis, font=f_title, fill=marca.NAVY)
    d.rectangle([(PAD, TITLE_H - 8), (PAD + 64, TITLE_H - 5)], fill=marca.NARANJA)
    d.rectangle([(PAD + 64, TITLE_H - 7), (total_w - PAD, TITLE_H - 6)], fill=marca.LINEA)

    y = TITLE_H

    if not pedidos:
        d.text((PAD, y + 10), "No hay ítems con proveedor ganador.", font=f_normal, fill=C_GRAY)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=92)
        buf.seek(0)
        return buf.read()

    gran_total = sum(p["total"] for p in pedidos)
    d.text((PAD, y + 6), f"Total de la compra: {_fmt(gran_total)}", font=f_bold, fill=marca.NAVY)
    y += 30

    def _der(texto, x_col, ancho, yy, font, color):
        """Texto alineado a la derecha dentro de la columna."""
        bb = d.textbbox((0, 0), texto, font=font)
        d.text((x_col + ancho - (bb[2] - bb[0]) - 6, yy), texto, font=font, fill=color)

    for pedido in pedidos:
        prov = pedido["proveedor"]

        # Encabezado del proveedor
        d.rectangle([(0, y), (total_w, y + CC_SECCION_H)], fill=C_RUBRO)
        d.text((PAD, y + 8), prov, font=f_prov, fill=marca.NAVY)
        d.text((PAD, y + 27), f"{pedido['n_items']} ítems · mejor precio",
               font=_get_font(10), fill=C_GRAY)
        _der(_fmt(pedido["total"]), 0, total_w - PAD, y + 14, f_prov, C_VERDE)
        y += CC_SECCION_H

        # Cabecera de columnas
        d.rectangle([(0, y), (total_w, y + HDR_H)], fill=C_SUBHDR)
        x = PAD
        d.text((x, y + 14), "Material", font=f_bold, fill=C_TEXT)
        x += CC_MAT
        _der("Cant.", x, CC_CANT, y + 14, f_bold, C_GRAY);   x += CC_CANT
        _der("Unidad", x, CC_UNID, y + 14, f_bold, C_GRAY);  x += CC_UNID
        _der("Precio unit.", x, CC_PU, y + 14, f_bold, C_GRAY); x += CC_PU
        _der("Subtotal", x, CC_SUB, y + 14, f_bold, C_GRAY)
        y += HDR_H

        ultimo_rubro = None
        for f in pedido["filas"]:
            rubro = f.get("rubro") or ""
            if rubro != ultimo_rubro:
                d.rectangle([(0, y), (total_w, y + ROW_H)], fill=C_RUBRO)
                d.text((PAD, y + 8), rubro.upper(), font=f_rubro, fill=(58, 80, 128))
                y += ROW_H
                ultimo_rubro = rubro

            precio, cant, subtotal = subtotal_fila(f, prov)
            d.line([(0, y), (total_w, y)], fill=C_BORDER, width=1)
            x = PAD
            # Recorte con puntos suspensivos: cortar en seco deja nombres como
            # "CLAVO ... PUNTA PARIS EXTRA LAR", que parece un dato incompleto
            # en vez de un texto recortado.
            mat = f.get("material") or ""
            if d.textbbox((0, 0), mat, font=f_normal)[2] > CC_MAT - 10:
                while (d.textbbox((0, 0), mat + "…", font=f_normal)[2] > CC_MAT - 10
                       and len(mat) > 4):
                    mat = mat[:-1]
                mat = mat.rstrip() + "…"
            d.text((x, y + 10), mat, font=f_normal, fill=C_TEXT)
            x += CC_MAT
            _der(f"{cant:g}", x, CC_CANT, y + 10, f_normal, C_TEXT);            x += CC_CANT
            _der(f.get("unidad") or "", x, CC_UNID, y + 10, f_normal, C_TEXT);  x += CC_UNID
            _der(_fmt(precio), x, CC_PU, y + 10, f_normal, C_TEXT);             x += CC_PU
            _der(_fmt(subtotal), x, CC_SUB, y + 10, f_bold, C_TEXT)
            y += ROW_H

        # Total del pedido
        d.rectangle([(0, y), (total_w, y + ROW_H)], fill=C_MEJOR)
        d.line([(0, y), (total_w, y)], fill=(176, 181, 190), width=2)
        d.text((PAD, y + 10), f"TOTAL PEDIDO ({pedido['n_items']} ítems)",
               font=f_bold, fill=(58, 80, 128))
        _der(_fmt(pedido["total"]), 0, total_w - PAD, y + 10, f_bold, C_VERDE)
        y += ROW_H + CC_GAP

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()


def generar_imagen_comparativo(
    comparativo: list[dict],
    proveedores: list[str],
    titulo: str = None,
    subtitulo: str = None,
) -> bytes:
    titulo_vis = marca.titulo_visible(titulo)
    meta       = marca.meta_visible(subtitulo)
    n_prov = len(proveedores)

    # Calcular dimensiones
    total_w = PAD + COL_MAT + COL_CANT + COL_PROV * n_prov + COL_MEJOR + COL_AHORRO + PAD

    # Contar filas (rubros + items)
    ultimo_rubro = None
    n_rows = 0
    for row in comparativo:
        if row.get("rubro", "") != ultimo_rubro:
            n_rows += 1
            ultimo_rubro = row.get("rubro", "")
        n_rows += 1
    n_rows += 1  # totales

    total_h = TITLE_H + HDR_H + n_rows * ROW_H + PAD * 2

    img = Image.new("RGB", (total_w, total_h), C_BLANCO)
    d   = ImageDraw.Draw(img)

    f_title  = _get_font(18, bold=True)
    f_sub    = _get_font(11)
    f_bold   = _get_font(12, bold=True)
    f_normal = _get_font(12)
    f_small  = _get_font(10)
    f_rubro  = _get_font(10, bold=True)

    # ── Encabezado de marca ──────────────────────────────────────────────────
    # Isologo + wordmark a la izquierda, metadatos a la derecha, título debajo,
    # regla naranja de acento. Fondo blanco.
    iso = 26
    marca.dibujar_isotipo(d, PAD, 12, iso)
    f_marca = _get_font(17, bold=True)
    d.text((PAD + iso + 8, 12 + (iso - 17) // 2), "Vectorai", font=f_marca, fill=marca.NAVY)
    bbox = d.textbbox((0, 0), meta, font=f_sub)
    d.text((total_w - PAD - (bbox[2] - bbox[0]), 12 + (iso - 11) // 2), meta,
           font=f_sub, fill=marca.GRIS)
    d.text((PAD, 56), titulo_vis, font=f_title, fill=marca.NAVY)
    d.rectangle([(PAD, TITLE_H - 8), (PAD + 64, TITLE_H - 5)], fill=marca.NARANJA)
    d.rectangle([(PAD + 64, TITLE_H - 7), (total_w - PAD, TITLE_H - 6)], fill=marca.LINEA)

    y = TITLE_H

    # ── Cabecera ─────────────────────────────────────────────────────────────
    d.rectangle([(0, y), (total_w, y + HDR_H)], fill=C_SUBHDR)
    x = PAD
    d.text((x, y + 14), "Material", font=f_bold, fill=C_TEXT)
    x += COL_MAT
    d.text((x + 4, y + 14), "Cant.", font=f_bold, fill=C_GRAY)
    x += COL_CANT

    for i, prov in enumerate(proveedores):
        col_bg = COLORES_PROV[i % len(COLORES_PROV)]
        d.rectangle([(x, y), (x + COL_PROV, y + HDR_H)], fill=col_bg)
        # Centrar texto, truncando con elipsis si no entra en la columna
        etiqueta = prov
        while etiqueta and d.textbbox((0, 0), etiqueta, font=f_bold)[2] > COL_PROV - 12:
            etiqueta = etiqueta[:-2].rstrip() + "…"
        bbox = d.textbbox((0, 0), etiqueta, font=f_bold)
        tw = bbox[2] - bbox[0]
        d.text((x + (COL_PROV - tw) // 2, y + 14), etiqueta, font=f_bold, fill=(255, 255, 255))
        x += COL_PROV

    d.text((x + 4, y + 14), "Mejor", font=f_bold, fill=C_TEXT)
    x += COL_MEJOR
    d.text((x + 4, y + 14), "Ahorro", font=f_bold, fill=C_GRAY)

    d.line([(0, y + HDR_H - 1), (total_w, y + HDR_H - 1)], fill=C_BORDER, width=2)
    y += HDR_H

    # ── Datos ────────────────────────────────────────────────────────────────
    ultimo_rubro = None
    totales = {p: 0.0 for p in proveedores}

    for row in comparativo:
        rubro   = row.get("rubro", "")
        mat     = row.get("material", "") or ""
        cant    = row.get("cant", 1) or 1
        unidad  = row.get("unidad", "")
        precios = row.get("precios", {})
        mejor   = row.get("mejor_proveedor", "")
        ahorro  = row.get("ahorro", 0) or 0

        precios_vals = {p: precios[p]["precio_sin_iva"] * cant for p in proveedores if p in precios}
        precio_min = min(precios_vals.values()) if len(precios_vals) > 1 else None

        # Fila de rubro
        if rubro != ultimo_rubro:
            d.rectangle([(0, y), (total_w, y + RUBRO_H)], fill=C_RUBRO)
            d.text((PAD, y + 6), rubro.upper(), font=f_rubro, fill=(58, 80, 128))
            y += RUBRO_H
            ultimo_rubro = rubro

        # Fila de item — fondo alternado sutil
        d.rectangle([(0, y), (total_w, y + ROW_H)], fill=C_BLANCO)
        d.line([(0, y + ROW_H - 1), (total_w, y + ROW_H - 1)], fill=C_BORDER, width=1)

        x = PAD
        # Material (truncar si es largo)
        mat_short = mat[:36] + "…" if len(mat) > 36 else mat
        d.text((x, y + 10), mat_short, font=f_normal, fill=C_TEXT)
        x += COL_MAT

        # Cantidad
        cant_str = f"{int(cant)} {unidad}" if cant != 1 else unidad
        d.text((x + 4, y + 10), cant_str, font=f_small, fill=C_GRAY)
        x += COL_CANT

        # Precios por proveedor
        for i, prov in enumerate(proveedores):
            val = precios_vals.get(prov)
            is_mejor = (precio_min is not None and val is not None
                        and val == precio_min and len(precios_vals) > 1)
            if is_mejor:
                d.rectangle([(x, y), (x + COL_PROV, y + ROW_H)], fill=C_MEJOR)
            if val is not None:
                totales[prov] += val
                txt = _fmt(val)
                color = C_VERDE if is_mejor else C_TEXT
                font  = f_bold if is_mejor else f_normal
            else:
                txt, color, font = "—", (203, 213, 225), f_normal
            bbox = d.textbbox((0, 0), txt, font=font)
            tw = bbox[2] - bbox[0]
            d.text((x + COL_PROV - tw - 6, y + 10), txt, font=font, fill=color)
            x += COL_PROV

        # Mejor proveedor
        if mejor:
            d.text((x + 4, y + 10), mejor, font=f_bold, fill=C_VERDE)
        x += COL_MEJOR

        # Ahorro
        if ahorro:
            bbox = d.textbbox((0, 0), _fmt(ahorro), font=f_small)
            tw = bbox[2] - bbox[0]
            d.text((x + COL_AHORRO - tw - 6, y + 10), _fmt(ahorro), font=f_small, fill=C_VERDE)

        y += ROW_H

    # ── Fila totales ──────────────────────────────────────────────────────────
    d.rectangle([(0, y), (total_w, y + ROW_H)], fill=C_SUBHDR)
    d.line([(0, y), (total_w, y)], fill=(176, 181, 190), width=2)
    x = PAD
    d.text((x, y + 10), "TOTAL", font=f_bold, fill=(58, 80, 128))
    x += COL_MAT + COL_CANT
    for prov in proveedores:
        txt = _fmt(totales[prov])
        bbox = d.textbbox((0, 0), txt, font=f_bold)
        tw = bbox[2] - bbox[0]
        d.text((x + COL_PROV - tw - 6, y + 10), txt, font=f_bold, fill=C_TEXT)
        x += COL_PROV

    # Convertir a JPG
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()
