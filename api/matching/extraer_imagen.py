"""extraer_imagen.py — extracción de ítems desde fotos de presupuestos (OCR/visión).

Dos motores, elegibles por variable de entorno OCR_PROVIDER:
  - "claude" (default si hay ANTHROPIC_API_KEY): visión de Claude con salida
    estructurada — entiende la estructura de la tabla directamente, ideal para
    fotos de presupuestos con columnas.
  - "google" (si hay GOOGLE_VISION_API_KEY): OCR de Google Cloud Vision
    (DOCUMENT_TEXT_DETECTION) → el texto pasa por los mismos parsers de línea
    que usan los PDFs (extraer_regex / extraer_lineas).

Devuelve el mismo dict que extraer_pdf_texto.extraer():
  {fecha_presupuesto, iva_detectado, suma_lineas, n_items, metodo_extraccion, items}
"""
import base64
import json
import os

MAGIC_MEDIA = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG", "image/png"),
    (b"RIFF", "image/webp"),
    (b"GIF8", "image/gif"),
]

PROMPT_EXTRACCION = """Esta es la foto de un presupuesto/cotización de un proveedor de materiales de construcción en Argentina.

Extraé TODOS los ítems de la tabla de productos. Para cada ítem:
- cod: código del proveedor (columna ITEM/REF/CÓDIGO); "" si no hay
- desc: descripción completa del producto, tal como está escrita
- cant: cantidad (número)
- pu: PRECIO UNITARIO (número). ¡No confundir con el total de línea!
- total: importe total de la línea (número). Si no hay columna de total, calculalo como pu × cant.

Cuidado con el formato de números argentino: "1.234,56" = 1234.56 y "12,50" = 12.5.
Si una columna dice PRECIO y otra TOTAL/IMPORTE, la de menor valor por fila es el unitario.
No incluyas subtotales, notas del proveedor, condiciones de pago ni líneas de flete/envío como ítems... salvo que sean claramente un producto.

Además:
- fecha: fecha del presupuesto en formato YYYY-MM-DD ("" si no aparece)
- total_declarado: el TOTAL general declarado al pie del documento (0 si no aparece)
- observacion_iva: qué dice el documento sobre IVA ("" si nada)"""

SCHEMA_EXTRACCION = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cod": {"type": "string"},
                    "desc": {"type": "string"},
                    "cant": {"type": "number"},
                    "pu": {"type": "number"},
                    "total": {"type": "number"},
                },
                "required": ["cod", "desc", "cant", "pu", "total"],
                "additionalProperties": False,
            },
        },
        "fecha": {"type": "string"},
        "total_declarado": {"type": "number"},
        "observacion_iva": {"type": "string"},
    },
    "required": ["items", "fecha", "total_declarado", "observacion_iva"],
    "additionalProperties": False,
}


def _media_type(content: bytes, filename: str = "") -> str | None:
    for magic, mt in MAGIC_MEDIA:
        if content.startswith(magic):
            return mt
    fn = (filename or "").lower()
    if fn.endswith((".jpg", ".jpeg", ".jfif")):
        return "image/jpeg"
    if fn.endswith(".png"):
        return "image/png"
    if fn.endswith(".webp"):
        return "image/webp"
    return None


def ocr_disponible() -> str | None:
    """Devuelve el motor configurado ('claude'|'google') o None si no hay ninguno."""
    proveedor = (os.environ.get("OCR_PROVIDER") or "").strip().lower()
    if proveedor == "google" and os.environ.get("GOOGLE_VISION_API_KEY"):
        return "google"
    if proveedor == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    # auto: preferir claude (entiende la estructura de tabla, no solo el texto)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    if os.environ.get("GOOGLE_VISION_API_KEY"):
        return "google"
    return None


def _iva_por_total(items: list[dict], total_declarado: float) -> str:
    suma = sum(it.get("total") or 0 for it in items)
    if total_declarado and suma:
        if abs(suma - total_declarado) < max(1, 0.001 * total_declarado):
            return "PRECIOS C/IVA INCLUIDO"
        if abs(suma * 1.21 - total_declarado) < max(5, 0.001 * total_declarado):
            return "PRECIOS S/IVA + 21%"
        if abs(suma * 1.105 - total_declarado) < max(5, 0.001 * total_declarado):
            return "PRECIOS S/IVA + 10,5%"
    return "ASUMIDO 1,105"


def _extraer_claude(content: bytes, media_type: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    b64 = base64.standard_b64encode(content).decode("utf-8")
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=16000,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA_EXTRACCION}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": PROMPT_EXTRACCION},
            ],
        }],
    )
    if response.stop_reason == "refusal":
        raise ValueError("El modelo no pudo procesar esta imagen.")
    texto = next(b.text for b in response.content if b.type == "text")
    data = json.loads(texto)

    items = [
        {"cod": (it.get("cod") or "").strip(), "desc": (it.get("desc") or "").strip(),
         "cant": float(it.get("cant") or 1), "pu": float(it.get("pu") or 0),
         "total": float(it.get("total") or 0)}
        for it in data.get("items", [])
        if (it.get("desc") or "").strip() and float(it.get("pu") or 0) > 0
    ]
    return {
        "fecha_presupuesto": (data.get("fecha") or "").strip() or None,
        "iva_detectado": _iva_por_total(items, float(data.get("total_declarado") or 0)),
        "suma_lineas": round(sum(it["total"] for it in items), 2),
        "n_items": len(items),
        "metodo_extraccion": "vision_claude",
        "items": items,
    }


def _extraer_google(content: bytes) -> dict:
    import requests
    from extraer_pdf_texto import extraer_lineas, extraer_regex

    key = os.environ["GOOGLE_VISION_API_KEY"]
    b64 = base64.standard_b64encode(content).decode("utf-8")
    resp = requests.post(
        f"https://vision.googleapis.com/v1/images:annotate?key={key}",
        json={"requests": [{
            "image": {"content": b64},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }]},
        timeout=60,
    )
    resp.raise_for_status()
    r0 = (resp.json().get("responses") or [{}])[0]
    if "error" in r0:
        raise ValueError(f"Google Vision: {r0['error'].get('message', 'error desconocido')}")
    texto = (r0.get("fullTextAnnotation") or {}).get("text", "")
    if not texto.strip():
        raise ValueError("Google Vision no encontró texto legible en la imagen.")

    items = extraer_regex(texto) or extraer_lineas(texto)
    return {
        "fecha_presupuesto": None,
        "iva_detectado": "ASUMIDO 1,105",
        "suma_lineas": round(sum(it.get("total") or 0 for it in items), 2),
        "n_items": len(items),
        "metodo_extraccion": "ocr_google",
        "items": items,
    }


def extraer_imagen(content: bytes, filename: str = "") -> dict:
    """Extrae ítems de una foto de presupuesto. Lanza ValueError con mensaje
    accionable si no hay motor configurado o la imagen no se puede procesar."""
    media_type = _media_type(content, filename)
    if not media_type:
        raise ValueError("Formato de imagen no soportado (usar JPG, PNG o WebP).")
    if media_type == "image/gif":
        raise ValueError("GIF no soportado — convertí la imagen a JPG o PNG.")

    motor = ocr_disponible()
    if motor == "claude":
        return _extraer_claude(content, media_type)
    if motor == "google":
        return _extraer_google(content)
    raise ValueError(
        "El procesamiento de fotos no está habilitado en este servidor "
        "(falta ANTHROPIC_API_KEY o GOOGLE_VISION_API_KEY)."
    )
