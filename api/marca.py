"""
marca.py — Activos de marca VectorAI para los exports (PDF / Excel / imagen).
Isologo: 3 barras redondeadas navy/naranja, mismo dibujo que
frontend/components/Logo.tsx. Paleta según IDENTIDAD.md.
"""
from io import BytesIO
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# Paleta (hex sin # para openpyxl, tuplas RGB para PIL)
NAVY_HEX    = "1A2B4A"
NARANJA_HEX = "E87022"
GRIS_HEX    = "6B7280"
LINEA_HEX   = "E2E6EE"
NAVY    = (26, 43, 74)
NARANJA = (232, 112, 34)
GRIS    = (107, 114, 128)
LINEA   = (226, 230, 238)

# Barras del isotipo en viewBox 0-100 (x, y, w, h) — la tercera va naranja
BARRAS = [(18, 26, 64, 13), (30, 48, 40, 13), (40, 70, 20, 13)]


def fuente(size: int, bold: bool = False):
    try:
        return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def dibujar_isotipo(draw: ImageDraw.ImageDraw, x: float, y: float, tam: float):
    """Dibuja el isotipo (3 barras) en una caja tam×tam con origen (x, y)."""
    esc = tam / 100.0
    for i, (bx, by, bw, bh) in enumerate(BARRAS):
        color = NARANJA if i == 2 else NAVY
        draw.rounded_rectangle(
            [x + bx * esc, y + by * esc, x + (bx + bw) * esc, y + (by + bh) * esc],
            radius=(bh * esc) / 2, fill=color,
        )


def lockup_png(alto: int = 48) -> tuple[bytes, int, int]:
    """PNG transparente del isologo + wordmark 'Vectorai'.
    Devuelve (bytes, ancho_px, alto_px). Renderizar a 2-3x del tamaño final
    para que quede nítido al escalarlo."""
    f = fuente(int(alto * 0.62), bold=True)
    medidor = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = medidor.textbbox((0, 0), "Vectorai", font=f)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    gap = int(alto * 0.28)
    ancho = alto + gap + tw + 4
    img = Image.new("RGBA", (ancho, alto), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    dibujar_isotipo(d, 0, 0, alto)
    d.text((alto + gap, (alto - th) // 2 - bbox[1]), "Vectorai", font=f, fill=NAVY)
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), ancho, alto


def titulo_visible(titulo: str | None) -> str:
    """El encabezado ya lleva logo y fecha: el título no repite marca ni ISO-fecha."""
    t = (titulo or "").strip()
    if t.startswith("VectorAI — "):
        t = t[len("VectorAI — "):]
    if not t or t.startswith("Comparativa 2"):
        t = "Comparativa de presupuestos"
    return t


def meta_visible(subtitulo: str | None) -> str:
    """Línea de metadatos del encabezado; el wordmark ya dice Vectorai."""
    meta = subtitulo or f"Generado el {datetime.now().strftime('%d/%m/%Y')} · Precios sin IVA"
    for sufijo in (" · VectorAI beta", " · VectorAI"):
        if meta.endswith(sufijo):
            meta = meta[: -len(sufijo)]
    return meta
