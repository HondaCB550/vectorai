"""
WhatsApp Cloud API — webhook receiver y sender para VECTORai.

Flujo:
  1. Usuario manda PDF(s) por WhatsApp
  2. Primer PDF → acumulamos en sesión, pedimos el siguiente
  3. Segundo PDF (o más) → procesamos todos juntos → mandamos resumen comparativo
  4. Usuario puede mandar "listo" para forzar el análisis con los PDFs acumulados

Sesiones en memoria con TTL de 30 minutos (limpieza lazy).
"""
import os
import time
import hmac
import hashlib
import tempfile
import requests
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse

# ── Config desde env ───────────────────────────────────────────────────────────
WA_TOKEN        = os.environ.get("WHATSAPP_TOKEN", "")          # token temporal del panel
WA_PHONE_ID     = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "") # ID del número de prueba
WA_APP_SECRET   = os.environ.get("WHATSAPP_APP_SECRET", "")     # para verificar firma
WA_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "vectorai-webhook-2026")

GRAPH_API = "https://graph.facebook.com/v19.0"

# ── Sesiones en memoria ────────────────────────────────────────────────────────
# { phone: {"pdfs": [(nombre, bytes), ...], "ts": float} }
_sesiones: dict[str, dict] = {}
SESSION_TTL = 30 * 60  # 30 minutos

def _limpiar_sesiones_viejas():
    ahora = time.time()
    viejas = [k for k, v in _sesiones.items() if ahora - v["ts"] > SESSION_TTL]
    for k in viejas:
        del _sesiones[k]

def _sesion(phone: str) -> dict:
    _limpiar_sesiones_viejas()
    if phone not in _sesiones:
        _sesiones[phone] = {"pdfs": [], "ts": time.time()}
    return _sesiones[phone]

def _resetear_sesion(phone: str):
    _sesiones.pop(phone, None)


# ── Router ─────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


# ── GET /whatsapp/webhook — verificación de Meta ──────────────────────────────
@router.get("/webhook", response_class=PlainTextResponse)
async def verificar_webhook(
    hub_mode: Optional[str]         = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str]    = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == WA_VERIFY_TOKEN:
        return hub_challenge or ""
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


# ── POST /whatsapp/webhook — mensajes entrantes ────────────────────────────────
@router.post("/webhook")
async def recibir_mensaje(request: Request):
    # Verificar firma X-Hub-Signature-256
    if WA_APP_SECRET:
        sig_header = request.headers.get("X-Hub-Signature-256", "")
        raw_body   = await request.body()
        expected   = "sha256=" + hmac.new(
            WA_APP_SECRET.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig_header):
            raise HTTPException(status_code=401, detail="Firma inválida")
        body = __import__("json").loads(raw_body)
    else:
        body = await request.json()

    # Extraer mensaje
    try:
        entry   = body["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]
    except (KeyError, IndexError):
        return {"ok": True}  # ping de Meta sin mensajes

    # Ignorar status updates (delivered, read, etc.)
    if "statuses" in value and "messages" not in value:
        return {"ok": True}

    mensajes = value.get("messages", [])
    if not mensajes:
        return {"ok": True}

    msg   = mensajes[0]
    phone = msg.get("from", "")
    tipo  = msg.get("type", "")

    if tipo == "text":
        texto = (msg.get("text") or {}).get("body", "").strip().lower()
        await _manejar_texto(phone, texto)

    elif tipo == "document":
        doc = msg.get("document") or {}
        await _manejar_documento(phone, doc)

    elif tipo == "image":
        _enviar_mensaje(phone, "Necesito un PDF, no una imagen. Mandame el presupuesto en formato PDF.")

    else:
        _enviar_mensaje(phone, "Hola! Soy VECTORai. Mandame los PDFs de tus proveedores y comparo precios automáticamente.")

    return {"ok": True}


# ── Handlers ───────────────────────────────────────────────────────────────────
async def _manejar_texto(phone: str, texto: str):
    comandos_listo = {"listo", "analizar", "comparar", "ya", "ok", "procesar"}
    comandos_reset = {"reiniciar", "borrar", "reset", "nuevo", "empezar"}
    comandos_ayuda = {"hola", "ayuda", "help", "inicio", "start", "/start"}

    sesion = _sesion(phone)

    if texto in comandos_reset:
        _resetear_sesion(phone)
        _enviar_mensaje(phone, "Sesión reiniciada. Mandame los PDFs de tus proveedores cuando quieras.")
        return

    if texto in comandos_ayuda:
        _enviar_mensaje(
            phone,
            "Hola! Soy *VECTORai* 🏗️\n\n"
            "Comparo presupuestos de materiales de construcción automáticamente.\n\n"
            "*Cómo funciona:*\n"
            "1️⃣ Mandame el PDF de un proveedor\n"
            "2️⃣ Mandame el PDF de otro proveedor\n"
            "3️⃣ Te mando la comparativa con qué conviene comprar dónde\n\n"
            "Podés mandar hasta 5 PDFs antes de escribir *listo*."
        )
        return

    if texto in comandos_listo:
        if not sesion["pdfs"]:
            _enviar_mensaje(phone, "No tengo PDFs cargados. Mandame los presupuestos primero.")
            return
        if len(sesion["pdfs"]) == 1:
            _enviar_mensaje(phone, f"Solo tengo un PDF ({sesion['pdfs'][0][0]}). Mandame otro proveedor para poder comparar, o escribí *listo* si querés el análisis de uno solo.")
            # Procesamos igual con uno
        await _procesar_sesion(phone)
        return

    # Mensaje de texto sin comando reconocido
    if sesion["pdfs"]:
        n = len(sesion["pdfs"])
        nombres = ", ".join(p[0] for p in sesion["pdfs"])
        _enviar_mensaje(
            phone,
            f"Tengo {n} PDF(s) cargados: {nombres}\n\n"
            "Mandame otro PDF o escribí *listo* para ver la comparativa."
        )
    else:
        _enviar_mensaje(
            phone,
            "Mandame los PDFs de tus proveedores para comparar precios. "
            "Cuando los hayas mandado todos, escribí *listo*."
        )


async def _manejar_documento(phone: str, doc: dict):
    mime = doc.get("mime_type", "")
    if "pdf" not in mime.lower():
        _enviar_mensaje(phone, f"Solo proceso PDFs. El archivo que mandaste es {mime}.")
        return

    media_id  = doc.get("id", "")
    filename  = doc.get("filename") or f"presupuesto_{int(time.time())}.pdf"

    _enviar_mensaje(phone, f"Recibí *{filename}*. Descargando...")

    pdf_bytes = _descargar_media(media_id)
    if not pdf_bytes:
        _enviar_mensaje(phone, f"No pude descargar {filename}. ¿Podés reenviarlo?")
        return

    sesion = _sesion(phone)
    sesion["pdfs"].append((filename, pdf_bytes))
    sesion["ts"] = time.time()
    n = len(sesion["pdfs"])

    if n == 1:
        _enviar_mensaje(
            phone,
            f"✅ PDF 1 guardado: *{filename}*\n\n"
            "Mandame el PDF de otro proveedor, o escribí *listo* si solo tenés uno."
        )
    elif n < 5:
        nombres = "\n".join(f"  {i+1}. {p[0]}" for i, p in enumerate(sesion["pdfs"]))
        _enviar_mensaje(
            phone,
            f"✅ PDF {n} guardado: *{filename}*\n\n"
            f"PDFs cargados:\n{nombres}\n\n"
            "Mandame otro PDF o escribí *listo* para comparar."
        )
    else:
        # Con 5 PDFs procesamos automáticamente
        _enviar_mensaje(phone, f"✅ {filename} recibido. Tenés 5 PDFs — procesando automáticamente...")
        await _procesar_sesion(phone)


async def _procesar_sesion(phone: str):
    sesion = _sesion(phone)
    pdfs   = sesion["pdfs"]

    if not pdfs:
        return

    _enviar_mensaje(phone, f"⏳ Analizando {len(pdfs)} PDF(s)... Tardará unos segundos.")

    # Importar pipeline del main
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).parent))

    try:
        from main import (
            get_master, get_equiv, get_config,
            detectar_proveedor, extraer, matchear_item,
            precio_neto, _build_comparativo,
        )
    except ImportError as e:
        _enviar_mensaje(phone, f"Error interno al cargar el motor: {e}")
        _resetear_sesion(phone)
        return

    master = get_master()
    equiv  = get_equiv()

    resultados = {}
    errores    = []

    for filename, pdf_bytes in pdfs:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            proveedor = detectar_proveedor(filename) or P(filename).stem.upper()
            resultado = extraer(tmp_path)
            items     = resultado.get("items", [])

            if not items:
                errores.append(filename)
                continue

            matches   = []
            sin_match = []
            for item in items:
                desc = (item.get("desc") or "").strip()
                cod  = str(item.get("cod") or "").strip()
                pu   = float(item.get("pu") or 0)
                if not desc or pu <= 0:
                    continue

                top = matchear_item(desc, master, top_n=1, cod_prov=cod, equivalencias=equiv)
                if not top:
                    sin_match.append(desc)
                    continue

                score, mat, origen = top[0]
                accion = "OK" if score >= 75 else ("REVISAR" if score >= 60 else "SIN MATCH")
                entry = {
                    "cod_prov":       cod,
                    "desc_prov":      desc,
                    "cant":           float(item.get("cant") or 1),
                    "precio_con_iva": pu,
                    "precio_sin_iva": precio_neto(pu, proveedor),
                    "cod_int":        mat["codigo"],
                    "rubro":          mat.get("rubro", ""),
                    "item_int":       mat.get("item", ""),
                    "detalle_int":    mat.get("detalle", ""),
                    "unidad_int":     mat.get("unidad", ""),
                    "score":          round(score, 1),
                    "accion":         accion,
                    "origen":         origen,
                }
                if accion != "SIN MATCH":
                    matches.append(entry)
                else:
                    sin_match.append(desc)

            resultados[proveedor] = {
                "matches":   matches,
                "sin_match": sin_match,
                "n_total":   len(items),
            }
        except Exception as e:
            errores.append(f"{filename}: {e}")
        finally:
            try:
                __import__("os").unlink(tmp_path)
            except OSError:
                pass

    _resetear_sesion(phone)

    if not resultados:
        _enviar_mensaje(phone, "No pude procesar ningún PDF. " + ("; ".join(errores) if errores else "Verificá que sean presupuestos válidos."))
        return

    # Armar mensaje de respuesta
    texto = _formatear_comparativa(resultados, master)
    _enviar_mensaje(phone, texto)

    if errores:
        _enviar_mensaje(phone, f"⚠️ No pude procesar: {', '.join(errores)}")


def _formatear_comparativa(resultados: dict, master: list) -> str:
    from main import _build_comparativo

    proveedores = list(resultados.keys())
    comparativo = _build_comparativo(resultados, master)

    # Solo items que aparecen en más de un proveedor (los comparables)
    comunes = [r for r in comparativo if r.get("en_varios")]
    ahorro_total = sum(r.get("ahorro", 0) for r in comunes)

    lineas = [f"📊 *Comparativa VECTORai*", f"Proveedores: {' vs '.join(proveedores)}", ""]

    # Stats por proveedor
    for prov, data in resultados.items():
        lineas.append(f"*{prov}*: {len(data['matches'])} ítems matcheados de {data['n_total']} totales")
    lineas.append("")

    if not comunes:
        lineas.append("No encontré ítems en común entre los proveedores para comparar.")
        lineas.append("Tip: los PDFs pueden tener formatos muy distintos o pocos ítems coincidentes.")
    else:
        lineas.append(f"*{len(comunes)} ítems comparables* | Ahorro potencial: *${ahorro_total:,.0f}*")
        lineas.append("")

        # Top 5 mayores ahorros
        top = sorted(comunes, key=lambda r: r.get("ahorro", 0), reverse=True)[:5]
        lineas.append("*Top diferencias de precio:*")
        for r in top:
            mejor = r.get("mejor_proveedor", "?")
            precios_str = " | ".join(
                f"{p}: ${v['precio_sin_iva']:,.0f}"
                for p, v in r["precios"].items()
            )
            lineas.append(f"• {r['material'][:45]}")
            lineas.append(f"  {precios_str} → conviene *{mejor}*")

        lineas.append("")
        lineas.append(f"Entrá a vectorai.com.ar para ver la tabla completa y exportar a Excel.")

    # Items sin match
    sin_todos = sum(len(d.get("sin_match", [])) for d in resultados.values())
    if sin_todos > 0:
        lineas.append(f"\n⚠️ {sin_todos} ítems sin match (no están en la base de materiales).")

    return "\n".join(lineas)


# ── Helpers Graph API ──────────────────────────────────────────────────────────
def _descargar_media(media_id: str) -> Optional[bytes]:
    """Descarga un archivo de media de Meta usando el media_id."""
    if not WA_TOKEN or not media_id:
        return None
    try:
        # Paso 1: obtener URL de descarga
        r = requests.get(
            f"{GRAPH_API}/{media_id}",
            headers={"Authorization": f"Bearer {WA_TOKEN}"},
            timeout=15,
        )
        r.raise_for_status()
        url = r.json().get("url")
        if not url:
            return None

        # Paso 2: descargar el archivo
        r2 = requests.get(
            url,
            headers={"Authorization": f"Bearer {WA_TOKEN}"},
            timeout=60,
        )
        r2.raise_for_status()
        return r2.content
    except Exception as e:
        print(f"[whatsapp] Error descargando media {media_id}: {e}")
        return None


def _enviar_mensaje(phone: str, texto: str) -> bool:
    """Envía un mensaje de texto por WhatsApp Cloud API."""
    if not WA_TOKEN or not WA_PHONE_ID:
        print(f"[whatsapp] WA_TOKEN o WA_PHONE_ID no configurados — mensaje no enviado a {phone}")
        return False
    try:
        r = requests.post(
            f"{GRAPH_API}/{WA_PHONE_ID}/messages",
            headers={
                "Authorization": f"Bearer {WA_TOKEN}",
                "Content-Type":  "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to":   phone,
                "type": "text",
                "text": {"body": texto, "preview_url": False},
            },
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[whatsapp] Error enviando mensaje a {phone}: {e}")
        return False
