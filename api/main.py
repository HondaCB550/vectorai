"""
API FastAPI — Motor de análisis de presupuestos de construcción
Endpoints: /analizar, /confirmar, /sheets
"""
import sys
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from io import BytesIO
from pydantic import BaseModel
from supabase import create_client, Client as SupabaseClient

# ── Motor de matching (reutiliza scripts existentes) ──────────────────────────
API_DIR     = Path(__file__).parent
SCRIPTS_DIR = API_DIR / "matching"
DATA_DIR    = API_DIR / "data"

# Fallback a paths locales de desarrollo si no existen en el repo
if not SCRIPTS_DIR.exists():
    SCRIPTS_DIR = Path(__file__).parent.parent.parent / "Cotizaciones" / "Claude" / "skill_updates" / "scripts"
if not DATA_DIR.exists():
    DATA_DIR = Path(__file__).parent.parent.parent / "Cotizaciones" / "Claude"

sys.path.insert(0, str(SCRIPTS_DIR))

from detectar_proveedor import detectar_proveedor  # noqa: E402
from extraer_pdf_texto import extraer, _desc_es_codigo  # noqa: E402
from matching import matchear_item, extract_nums    # noqa: E402
from extraer_imagen import extraer_imagen, pdf_sin_texto, extraer_pdf_escaneado  # noqa: E402
from extraer_hoja import extraer_xlsx, extraer_csv  # noqa: E402

MASTER_JSON  = DATA_DIR / "master_materiales.json"
CONFIG_PATH  = DATA_DIR / "configuracion.json"

DECISIONES_JSON = DATA_DIR / "decisiones_usuario.json"

# Cache en memoria (recargamos solo si el archivo cambia)
_master_cache: list[dict] | None = None
_config_cache: dict | None = None
_equiv_cache: dict | None = None

def get_master() -> list[dict]:
    global _master_cache
    if _master_cache is None:
        with open(MASTER_JSON, encoding="utf-8") as f:
            _master_cache = json.load(f)
    return _master_cache

CARGAS_JSON = DATA_DIR / "cargas_realizadas.json"

def get_equiv() -> dict:
    """Equivalencias: Supabase primero (aprendizaje compartido), luego archivos locales (fallback)."""
    global _equiv_cache
    if _equiv_cache is None:
        _equiv_cache = {}

        # Fuente 1: Supabase (aprendizaje compartido de todos los usuarios)
        sb = get_supabase()
        if sb:
            try:
                res = sb.table("equivalencias").select("cod_prov,cod_int").execute()
                for row in (res.data or []):
                    cod_prov = (row.get("cod_prov") or "").strip()
                    cod_int = (row.get("cod_int") or "").strip()
                    if cod_prov and cod_int:
                        # Mapear ambas claves: por código de proveedor Y por descripción normalizada
                        _equiv_cache[cod_prov] = cod_int
                print(f"✓ Cargadas {len(res.data or [])} equivalencias desde Supabase")
            except Exception as e:
                print(f"⚠️ Error leyendo equivalencias de Supabase: {e}")

        # Fuente 2: Decisiones locales (fallback si Supabase no está disponible)
        if DECISIONES_JSON.exists():
            with open(DECISIONES_JSON, encoding="utf-8") as f:
                for d in json.load(f):
                    dec = d.get("decision", "")
                    if dec == "CARGAR":
                        cod = d.get("cod_correcto") or d.get("cod_propuesto")
                    elif dec == "CAMBIAR":
                        cod = d.get("cod_correcto")
                    else:
                        cod = None
                    desc = (d.get("desc_prov") or "").strip()
                    if desc and cod:
                        _equiv_cache[desc] = cod

        # Fuente 3: Cargas realizadas
        if CARGAS_JSON.exists():
            with open(CARGAS_JSON, encoding="utf-8") as f:
                for d in json.load(f):
                    desc = (d.get("desc_prov") or "").strip()
                    cod  = (d.get("cod_int") or "").strip()
                    if desc and cod:
                        _equiv_cache[desc] = cod

    return _equiv_cache

def get_config() -> dict:
    global _config_cache
    if _config_cache is None:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            _config_cache = json.load(f)
    return _config_cache

def factor_iva(proveedor: str) -> float:
    config = get_config()
    for p in config.get("proveedores", []):
        if p["nombre_canonico"] == proveedor:
            return float(p.get("factor_iva_default", 1.105))
    return 1.105

def descuento_proveedor(proveedor: str) -> float:
    """Descuento comercial configurado para el proveedor (0–100). 0 = sin descuento."""
    config = get_config()
    for p in config.get("proveedores", []):
        if p["nombre_canonico"] == proveedor:
            return float(p.get("descuento_default", 0))
    return 0.0

def precio_neto(pu: float, proveedor: str) -> float:
    """Precio neto = precio_pdf / factor_iva * (1 - descuento%). Siempre sin IVA."""
    fac  = factor_iva(proveedor)
    desc = descuento_proveedor(proveedor)
    return round(pu / fac * (1 - desc / 100), 2)

def config_proveedor(proveedor: str) -> dict:
    """Devuelve dict con iva_incluido y descuento_pct para mostrar en el frontend."""
    fac  = factor_iva(proveedor)
    desc = descuento_proveedor(proveedor)
    return {"iva_incluido": fac != 1.0, "factor_iva": fac, "descuento_pct": desc}


# ── Supabase ──────────────────────────────────────────────────────────────────
# Validación de token: el frontend envía el JWT de Supabase en Authorization
# La API verifica el plan del usuario para aplicar límites freemium.
# En producción usar supabase-py para verificar el JWT.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
MP_ACCESS_TOKEN = os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://vectorai.com.ar")

try:
    from supabase.client import ClientOptions as _SBOpts
except Exception:
    try:
        from supabase import ClientOptions as _SBOpts
    except Exception:
        _SBOpts = None

def get_supabase() -> SupabaseClient | None:
    if not (SUPABASE_URL and SUPABASE_SERVICE_KEY):
        return None
    # Timeout para que un Supabase colgado no cuelgue el request (agotaría el
    # threadpool). Fallback si la versión de la lib no soporta las opciones.
    if _SBOpts is not None:
        try:
            return create_client(
                SUPABASE_URL, SUPABASE_SERVICE_KEY,
                options=_SBOpts(postgrest_client_timeout=15, storage_client_timeout=15),
            )
        except Exception:
            pass
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── Límites de plan / anti-abuso ──────────────────────────────────────────────
# Plan free: 1 comparativa gratis DE POR VIDA (no se renueva), hasta 3
# proveedores con 5 hojas c/u. Todo configurable por env sin redeploy.
LIMITE_FREE           = int(os.environ.get("LIMITE_FREE", "1"))            # gratis de por vida
LIMITE_INICIAL_MES    = int(os.environ.get("LIMITE_INICIAL_MES", "6"))      # plan Inicial (basico), por mes
BONUS_INICIAL_1ER_MES = int(os.environ.get("BONUS_INICIAL_1ER_MES", "2"))   # +2 comparativas el primer mes
MAX_PROVEEDORES_FREE  = int(os.environ.get("MAX_PROVEEDORES_FREE", "3"))
MAX_HOJAS_PROV_FREE   = int(os.environ.get("MAX_HOJAS_PROV_FREE", "5"))
# Planes pagos: tope de seguridad por plan. Inicial 5 proveedores; Advance/Pro 10
# (licitaciones grandes). Más de 10 hojas por proveedor arriesga colapsar.
MAX_PROVEEDORES       = int(os.environ.get("MAX_PROVEEDORES", "5"))
MAX_PROVEEDORES_ADV   = int(os.environ.get("MAX_PROVEEDORES_ADV", "10"))
MAX_HOJAS_PROV        = int(os.environ.get("MAX_HOJAS_PROV", "10"))
MAX_ARCHIVOS_TOTAL    = int(os.environ.get("MAX_ARCHIVOS_TOTAL", "60"))
MAX_BYTES_ARCHIVO     = int(os.environ.get("MAX_MB_ARCHIVO", "20")) * 1024 * 1024

_ANONIMO = {"user_id": "anonimo", "plan": "free", "usos_hoy": 0, "limite": LIMITE_FREE}

# Emails con acceso al panel /admin (coma-separados en env, con fallback)
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "bontempopablo@gmail.com").split(",")
    if e.strip()
}


def require_admin(authorization: Optional[str]) -> str:
    """403 salvo que el token pertenezca a un email de ADMIN_EMAILS. Devuelve el email."""
    if not authorization:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})
    try:
        u = sb.auth.get_user(authorization.removeprefix("Bearer ").strip())
        email = (u.user.email or "").lower() if u.user else ""
    except Exception:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    if email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "mensaje": "Solo administradores."})
    return email

def get_user_plan(authorization: Optional[str]) -> dict:
    """Devuelve {'user_id': ..., 'plan': 'free'|'advance', 'usos_hoy': N, 'limite': N}.

    'usos_hoy' es el contador del MES en curso (nombre histórico de la clave;
    el esquema real de perfiles es usos_mes/limite_mes/mes_usos — las columnas
    usos_hoy/fecha_usos nunca existieron en la tabla y el select fallaba,
    degradando a TODOS los logueados a anónimo).

    Sin token → anónimo, plan free, límite 2 (no trackeado).
    Con token → verifica JWT, consulta perfiles, resetea contador si cambió el mes.
    """
    if not authorization:
        return dict(_ANONIMO)

    token = authorization.removeprefix("Bearer ").strip()
    sb = get_supabase()
    if not sb:
        return dict(_ANONIMO)

    try:
        user_resp = sb.auth.get_user(token)
        user_id = user_resp.user.id if user_resp.user else None
        if not user_id:
            return dict(_ANONIMO)

        mes = datetime.now().strftime("%Y-%m")
        # OJO: .single() LANZA excepción con 0 filas (PGRST116) en vez de devolver
        # data=None, así que el auto-create nunca corría y el usuario quedaba
        # degradado a anónimo. limit(1) devuelve lista (vacía si no hay perfil).
        perfil = sb.table("perfiles").select("plan,usos_mes,usos_total,mes_usos,plan_desde").eq("id", user_id).limit(1).execute()
        row = (perfil.data or [None])[0]
        if not row:
            # Crear perfil si el trigger no lo hizo (cuentas pre-trigger)
            sb.table("perfiles").insert({"id": user_id, "plan": "free", "usos_mes": 0, "usos_total": 0, "mes_usos": mes}).execute()
            return {"user_id": user_id, "plan": "free", "usos_hoy": 0, "limite": LIMITE_FREE}

        plan = row.get("plan") or "free"

        # Reset del contador MENSUAL al cambiar de mes (planes con tope por mes).
        usos_mes = row.get("usos_mes") or 0
        if (row.get("mes_usos") or "") != mes:
            sb.table("perfiles").update({"usos_mes": 0, "mes_usos": mes}).eq("id", user_id).execute()
            usos_mes = 0

        # El límite lo fija el plan (la columna limite_mes quedó congelada por
        # trigger en la BD).
        if plan in ("advance", "pro"):
            return {"user_id": user_id, "plan": plan, "usos_hoy": 0, "limite": 999}
        if plan == "basico":  # plan Inicial: tope mensual + bonus del primer mes
            limite = LIMITE_INICIAL_MES
            if str(row.get("plan_desde") or "")[:7] == mes:
                limite += BONUS_INICIAL_1ER_MES
            return {"user_id": user_id, "plan": plan, "usos_hoy": usos_mes, "limite": limite}
        # free: contador de por vida (usos_total), 1 gratis, no renueva
        return {"user_id": user_id, "plan": plan, "usos_hoy": row.get("usos_total") or 0, "limite": LIMITE_FREE}
    except Exception as e:
        print(f"get_user_plan error: {e}")
        return dict(_ANONIMO)


def _incrementar_uso(user_id: str, usos_actuales: int = 0):
    """Suma 1 al contador mensual y al total (lifetime) del usuario. Va por
    service key, así que el trigger de congelado no lo bloquea."""
    if user_id == "anonimo":
        return
    sb = get_supabase()
    if not sb:
        return
    try:
        cur = sb.table("perfiles").select("usos_mes,usos_total").eq("id", user_id).limit(1).execute()
        row = (cur.data or [{}])[0]
        sb.table("perfiles").update({
            "usos_mes":   (row.get("usos_mes") or 0) + 1,
            "usos_total": (row.get("usos_total") or 0) + 1,
            "mes_usos":   datetime.now().strftime("%Y-%m"),
        }).eq("id", user_id).execute()
    except Exception as e:
        print(f"_incrementar_uso error: {e}")


def _gate_analisis(user: dict):
    """Cierra el análisis a anónimos y aplica el límite mensual del plan ANTES de
    procesar (la extracción/visión cuesta plata; los anónimos no se trackean, así
    que sin exigir login el abuso es ilimitado)."""
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=401, detail={
            "error": "auth_requerida",
            "mensaje": "Iniciá sesión para analizar presupuestos."})
    if user["usos_hoy"] >= user["limite"]:
        plan = user["plan"]
        if plan == "basico":
            msg = (f"Alcanzaste tus {user['limite']} comparativas de este mes. "
                   "Se renuevan el mes que viene, o pasate a Advance para "
                   "comparaciones ilimitadas.")
        elif plan in ("advance", "pro"):
            msg = f"Alcanzaste el límite de tu plan ({user['limite']})."
        else:  # free
            msg = ("Ya usaste tu comparativa gratis. Pasate al plan Inicial o "
                   "Advance para seguir comparando.")
        raise HTTPException(status_code=402, detail={
            "error": "limite_alcanzado",
            "plan": plan, "limite": user["limite"], "mensaje": msg})


def _validar_archivos(files: list, cfgs: list, plan: str):
    """Topes anti-abuso/DoS por request: cantidad total, tamaño por archivo, y
    proveedores/hojas según plan (free: 3 proveedores × 5 hojas)."""
    n = len(files or [])
    if n == 0:
        raise HTTPException(status_code=400, detail={
            "error": "sin_archivos", "mensaje": "Subí al menos un archivo."})
    if n > MAX_ARCHIVOS_TOTAL:
        raise HTTPException(status_code=413, detail={
            "error": "demasiados_archivos",
            "mensaje": f"Máximo {MAX_ARCHIVOS_TOTAL} archivos por comparativa."})
    for f in files:
        sz = getattr(f, "size", None)
        if sz is not None and sz > MAX_BYTES_ARCHIVO:
            raise HTTPException(status_code=413, detail={
                "error": "archivo_grande",
                "mensaje": (f"'{f.filename}' supera el máximo de "
                            f"{MAX_BYTES_ARCHIVO // (1024 * 1024)} MB por archivo.")})

    es_pago = plan in ("basico", "advance", "pro")
    if plan in ("advance", "pro"):
        max_prov = MAX_PROVEEDORES_ADV
    elif plan == "basico":
        max_prov = MAX_PROVEEDORES
    else:
        max_prov = MAX_PROVEEDORES_FREE
    max_hojas = MAX_HOJAS_PROV if es_pago else MAX_HOJAS_PROV_FREE
    sugerir   = "" if es_pago else " Pasate al plan Inicial o Advance para comparar más."
    # Solo para el error de proveedores: al Inicial le sirve subir a Advance.
    sugerir_prov = (" Pasate al plan Advance para comparar hasta "
                    f"{MAX_PROVEEDORES_ADV} proveedores.") if plan == "basico" else sugerir

    conteo: dict = {}
    for idx in range(n):
        cfg = cfgs[idx] if idx < len(cfgs) else {}
        clave = cfg.get("bloque", idx)
        conteo[clave] = conteo.get(clave, 0) + 1
    if len(conteo) > max_prov:
        raise HTTPException(status_code=413 if es_pago else 402, detail={
            "error": "demasiados_proveedores",
            "mensaje": f"Tu plan permite hasta {max_prov} proveedores por comparativa.{sugerir_prov}"})
    for c in conteo.values():
        if c > max_hojas:
            raise HTTPException(status_code=413 if es_pago else 402, detail={
                "error": "demasiadas_hojas",
                "mensaje": f"Tu plan permite hasta {max_hojas} hojas por proveedor.{sugerir}"})


# ── Proveedores (catálogo global) ─────────────────────────────────────────────
_proveedores_cache: dict[str, str] = {}

def _get_proveedor_id(sb: SupabaseClient | None, nombre: str) -> str | None:
    """Devuelve el id del proveedor por nombre exacto; lo crea si no existe."""
    nombre = (nombre or "").strip()
    if not sb or not nombre:
        return None
    if nombre in _proveedores_cache:
        return _proveedores_cache[nombre]
    try:
        res = sb.table("proveedores").select("id").eq("nombre", nombre).execute()
        if res.data:
            pid = res.data[0]["id"]
        else:
            try:
                ins = sb.table("proveedores").insert({"nombre": nombre}).execute()
                pid = ins.data[0]["id"] if ins.data else None
            except Exception:
                # Otro request lo creó en paralelo (nombre es UNIQUE): releer
                res = sb.table("proveedores").select("id").eq("nombre", nombre).execute()
                pid = res.data[0]["id"] if res.data else None
        if pid:
            _proveedores_cache[nombre] = pid
        return pid
    except Exception as e:
        print(f"_get_proveedor_id('{nombre}') error: {e}")
        return None


# ── App FastAPI ───────────────────────────────────────────────────────────────
app = FastAPI(title="VectorAI API", version="0.1.0")

from whatsapp import router as whatsapp_router
app.include_router(whatsapp_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://vectorai.com.ar", "https://www.vectorai.com.ar"],
    allow_origin_regex=r"https://vectorai-[a-z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelos ───────────────────────────────────────────────────────────────────
class ConfirmarItem(BaseModel):
    cod_prov: str
    desc_prov: str
    cod_int: str          # código interno correcto (confirmado por el usuario)
    proveedor: str
    precio_sin_iva: float
    comparativa_id: str

class SheetsRequest(BaseModel):
    comparativa_id: str
    titulo: Optional[str] = None
    user_mail: Optional[str] = None
    solo_comunes: bool = False
    filtro_rubro: Optional[str] = None
    incluir_iva: bool = False
    descuento_pct: float = 0.0  # 0–100


# Cache en memoria (fallback si Supabase no está disponible)
_comparativas_cache: dict[str, dict] = {}
_MAX_COMPARATIVAS_CACHE = int(os.environ.get("MAX_COMPARATIVAS_CACHE", "200"))

def _cache_comparativa(cid: str, data: dict):
    """Guarda en el cache con tope FIFO para que no crezca sin límite en la
    instancia (leak lento en Railway)."""
    if cid not in _comparativas_cache and len(_comparativas_cache) >= _MAX_COMPARATIVAS_CACHE:
        _comparativas_cache.pop(next(iter(_comparativas_cache)), None)
    _comparativas_cache[cid] = data

def _calcular_ahorro_total(comparativo: list) -> float:
    """Suma todos los ahorros de la comparativa."""
    return round(sum(r.get("ahorro", 0) for r in comparativo), 2)

def _guardar_comparativa(comparativa_id: str, data: dict, user_id: str = "anonimo", titulo: str = ""):
    """Persiste en Supabase; fallback a memoria."""
    _cache_comparativa(comparativa_id, data)
    sb = get_supabase()
    if sb and user_id != "anonimo":
        try:
            comparativo = data.get("comparativo", [])
            n_comunes = len([r for r in comparativo if r.get("en_varios")])
            ahorro_total = _calcular_ahorro_total(comparativo)

            sb.table("comparativas").insert({
                "id": comparativa_id,
                "user_id": user_id,
                "titulo": titulo or f"Comparativa {__import__('datetime').datetime.now().strftime('%d/%m/%Y')}",
                "proveedores": data["proveedores"],
                "n_items": len(comparativo),
                "n_comunes": n_comunes,
                "ahorro_total": ahorro_total,
                "datos_json": data,
            }).execute()
        except Exception as e:
            print(f"Supabase insert error (usando cache memoria): {e}")

def _leer_comparativa(comparativa_id: str) -> dict | None:
    """Lee de memoria primero, luego Supabase.

    OJO: la tabla NO tiene columna `comparativo` — el contenido vive en
    `datos_json` (pedirla rompía el select y las descargas de comparativas
    viejas daban 404 después de cada redeploy, cuando la caché de memoria
    arranca vacía)."""
    if comparativa_id in _comparativas_cache:
        return _comparativas_cache[comparativa_id]
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("comparativas").select("datos_json,proveedores") \
                    .eq("id", comparativa_id).limit(1).execute()
            row = (res.data or [None])[0]
            if row:
                dj = row.get("datos_json") or {}
                data = {
                    "comparativo": dj.get("comparativo", []),
                    "proveedores": row.get("proveedores") or dj.get("proveedores", []),
                }
                if data["comparativo"]:
                    _cache_comparativa(comparativa_id, data)
                    return data
        except Exception as e:
            print(f"Supabase read error: {e}")
    return None


# ── /analizar ─────────────────────────────────────────────────────────────────
@app.post("/analizar")
async def analizar(
    files: list[UploadFile] = File(...),
    authorization: Optional[str] = Header(None),
):
    """
    Recibe 1 o más PDFs, devuelve items matcheados por proveedor.
    Plan free: máximo 2 PDFs (1 por proveedor).
    """
    user = get_user_plan(authorization)
    _gate_analisis(user)
    if len(files) > MAX_ARCHIVOS_TOTAL:
        raise HTTPException(status_code=413, detail={
            "error": "demasiados_archivos",
            "mensaje": f"Máximo {MAX_ARCHIVOS_TOTAL} archivos por comparativa."})

    master = get_master()
    equiv: dict = get_equiv()  # Equivalencias aprendidas de borradores confirmados

    resultados = {}
    errores = []

    for f in files:
        content = await f.read()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            proveedor = detectar_proveedor(f.filename or "") or Path(f.filename or "archivo").stem.upper()
            resultado = extraer(tmp_path)
            items = resultado.get("items", [])

            if not items:
                errores.append({"archivo": f.filename, "error": "No se encontraron ítems"})
                continue

            matches = []
            sin_match = []

            for item in items:
                desc = (item.get("desc") or "").strip()
                cod  = str(item.get("cod") or "").strip()
                pu   = float(item.get("pu") or 0)

                if not desc or pu <= 0:
                    continue

                top = matchear_item(desc, master, top_n=3, cod_prov=cod, equivalencias=equiv)
                if not top:
                    sin_match.append({"cod_prov": cod, "desc_prov": desc, "precio": precio_neto(pu, proveedor)})
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
                    "alternativas": [
                        {"cod": t[1]["codigo"], "desc": t[1].get("item",""), "score": round(t[0],1)}
                        for t in top[1:]
                    ],
                }

                if accion == "SIN MATCH":
                    sin_match.append(entry)
                else:
                    matches.append(entry)

            resultados[proveedor] = {
                "fecha": resultado.get("fecha"),
                "n_total": len(items),
                "matches": matches,
                "sin_match": sin_match,  # para Human in the Loop
                "iva_detectado": resultado.get("iva_detectado"),
            }

        except Exception as e:
            errores.append({"archivo": f.filename, "error": str(e)})
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    if not resultados:
        raise HTTPException(status_code=422, detail={"error": "sin_resultados", "errores": errores})

    # Armar comparativo (tabla pivot)
    comparativa = _build_comparativo(resultados, master)
    comparativa_id = str(uuid.uuid4())
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    _guardar_comparativa(
        comparativa_id,
        {
            "comparativo": comparativa,
            "proveedores": list(resultados.keys()),
        },
        user_id=user["user_id"],
        titulo=f"Análisis — {', '.join(resultados.keys())} ({fecha_hoy})"
    )

    # Registrar uso del día para usuarios logueados
    _incrementar_uso(user["user_id"], user["usos_hoy"])

    usos_restantes = None
    if user["plan"] == "free" and user["user_id"] != "anonimo":
        usos_restantes = max(0, user["limite"] - user["usos_hoy"] - 1)

    return {
        "comparativa_id": comparativa_id,
        "proveedores": list(resultados.keys()),
        "resultados": resultados,
        "comparativo": comparativa,
        "errores": errores,
        "plan": user["plan"],
        "usos_restantes": usos_restantes,
    }


def _build_comparativo(resultados: dict, master: list) -> list[dict]:
    """Tabla comparativa: filas = material, columnas = proveedor.

    Maneja unidades distintas: cada proveedor tiene su cantidad, y el ahorro se calcula
    usando la cantidad del mejor proveedor (para evitar comparar manzanas con naranjas).
    """
    master_dict = {m["codigo"]: m for m in master}
    proveedores = list(resultados.keys())

    # Agrupar precios por cod_int
    por_cod: dict[str, dict] = {}
    for prov, data in resultados.items():
        for m in data.get("matches", []):
            cod = m["cod_int"]
            if cod not in por_cod:
                mat = master_dict.get(cod, {})
                por_cod[cod] = {
                    "cod_int":  cod,
                    "rubro":    mat.get("rubro", ""),
                    "material": f"{mat.get('item', cod)} — {mat.get('detalle', '')}".rstrip(" —"),
                    "unidad":   mat.get("unidad", ""),
                    "precios":  {},
                }
            por_cod[cod]["precios"][prov] = {
                "precio_sin_iva": m["precio_sin_iva"],
                "score": m["score"],
                "origen": m["origen"],
                "cant": m.get("cant", 1),
            }

    # Calcular mejor precio y ahorro
    rows = []
    for cod, row in por_cod.items():
        precios_val = {p: row["precios"][p]["precio_sin_iva"] for p in row["precios"]}
        if precios_val:
            # Mejor proveedor = menor precio
            mejor_prov = min(precios_val, key=precios_val.get)
            row["mejor_proveedor"] = mejor_prov
            row["cant"] = row["precios"][mejor_prov]["cant"]  # Cantidad del mejor proveedor

            if len(precios_val) > 1:
                # Ahorro = (máx - mín) * cantidad_del_mejor_proveedor
                ahorro_unitario = max(precios_val.values()) - min(precios_val.values())
                row["ahorro"] = round(ahorro_unitario * row["cant"], 2)
            else:
                row["ahorro"] = 0
        row["en_varios"] = len(row["precios"]) > 1
        rows.append(row)

    # Ordenar: primero ítems en varios proveedores (los más útiles para comparar)
    rows.sort(key=lambda r: (-int(r["en_varios"]), r["rubro"], r["material"]))
    return rows


# ── /confirmar (Human in the Loop) ────────────────────────────────────────────
@app.post("/confirmar")
async def confirmar(
    item: ConfirmarItem,
    authorization: Optional[str] = Header(None),
):
    """
    Guarda una equivalencia confirmada manualmente por el usuario.
    Solo disponible en plan básico.
    """
    user = get_user_plan(authorization)
    if user["plan"] == "free":
        raise HTTPException(
            status_code=402,
            detail={"error": "plan_limit", "mensaje": "La revisión manual está disponible en el plan básico.", "upgrade": True}
        )

    # TODO: guardar en Supabase tabla 'equivalencias'
    # equiv = {cod_prov: cod_int, proveedor, precio, fecha, user_id}
    print(f"EQUIV confirmada: {item.cod_prov} → {item.cod_int} (por {user['user_id']})")

    return {"ok": True, "mensaje": "Equivalencia guardada. El sistema aprenderá de esta corrección."}


# ── /comparativas (Historial) ─────────────────────────────────────────────────
@app.get("/comparativas")
async def listar_comparativas(
    authorization: Optional[str] = Header(None),
):
    """
    Lista todas las comparativas guardadas del usuario autenticado.
    Anónimos devuelven lista vacía.
    """
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        return {"comparativas": []}

    sb = get_supabase()
    if not sb:
        return {"comparativas": []}

    try:
        res = sb.table("comparativas").select(
            "id,titulo,proveedores,n_items,n_comunes,ahorro_total,created_at,obra_id"
        ).eq("user_id", user["user_id"]).order("created_at", desc=True).execute()

        obras_map: dict[str, dict] = {}
        obra_ids = sorted({c["obra_id"] for c in (res.data or []) if c.get("obra_id")})
        if obra_ids:
            try:
                res_obras = sb.table("obras").select("id,nombre,localidad,provincia").in_("id", obra_ids).execute()
                obras_map = {o["id"]: o for o in (res_obras.data or [])}
            except Exception:
                pass

        comparativas = []
        for c in (res.data or []):
            comparativas.append({
                "id": c["id"],
                "titulo": c["titulo"],
                "proveedores": c["proveedores"],
                "n_items": c["n_items"],
                "n_comunes": c["n_comunes"],
                "ahorro_total": c["ahorro_total"],
                "fecha": c["created_at"],
                "obra": obras_map.get(c.get("obra_id") or "", None),
            })

        return {"comparativas": comparativas}
    except Exception as e:
        print(f"Error listando comparativas: {e}")
        return {"comparativas": []}


@app.get("/comparativas/{comparativa_id}")
async def recuperar_comparativa(
    comparativa_id: str,
    authorization: Optional[str] = Header(None),
):
    """
    Recupera una comparativa guardada específica.
    Solo el propietario (o admin) puede verla.
    """
    user = get_user_plan(authorization)
    sb = get_supabase()

    if sb:
        try:
            res = sb.table("comparativas").select("*").eq("id", comparativa_id).single().execute()
            if res.data:
                # Verificar que el usuario sea el propietario
                if res.data.get("user_id") != user["user_id"]:
                    raise HTTPException(status_code=403, detail={"error": "forbidden"})

                return {
                    "id": res.data["id"],
                    "titulo": res.data["titulo"],
                    "proveedores": res.data["proveedores"],
                    "n_items": res.data["n_items"],
                    "n_comunes": res.data["n_comunes"],
                    "ahorro_total": res.data["ahorro_total"],
                    "fecha": res.data["created_at"],
                    "comparativo": res.data.get("datos_json", {}).get("comparativo", []),
                    "resultados": res.data.get("datos_json", {}).get("resultados", {}),
                }
        except Exception as e:
            print(f"Error recuperando comparativa: {e}")

    raise HTTPException(
        status_code=404,
        detail={"error": "comparativa_no_encontrada",
                "mensaje": "La comparativa no existe o expiró."}
    )


@app.delete("/comparativas/{comparativa_id}")
async def eliminar_comparativa(
    comparativa_id: str,
    authorization: Optional[str] = Header(None),
):
    """
    Elimina una comparativa. Solo el propietario puede hacerlo.
    """
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})

    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_unavailable"})

    try:
        # Verificar propietario
        res = sb.table("comparativas").select("user_id").eq("id", comparativa_id).single().execute()
        if not res.data or res.data.get("user_id") != user["user_id"]:
            raise HTTPException(status_code=403, detail={"error": "forbidden"})

        # Eliminar
        sb.table("comparativas").delete().eq("id", comparativa_id).execute()

        # Limpiar cache
        _comparativas_cache.pop(comparativa_id, None)

        return {"ok": True, "mensaje": "Comparativa eliminada."}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error eliminando comparativa: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error"})


# ── /sheets ───────────────────────────────────────────────────────────────────
@app.post("/sheets")
async def generar_sheets(
    req: SheetsRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Genera un Google Sheet con la comparativa y devuelve la URL.
    """
    user = get_user_plan(authorization)

    cached = _leer_comparativa(req.comparativa_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail={"error": "comparativa_no_encontrada",
                    "mensaje": "La comparativa expiró o no existe. Volvé a subir los PDFs."}
        )

    from exportar_excel import generar_excel_comparativo
    fecha = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    titulo = req.titulo or f"VectorAI — Comparativa {fecha}"
    comparativo = _aplicar_filtros(cached["comparativo"], req)

    # Solo Excel: el export a Google Sheets se dio de baja (las service
    # accounts ya no tienen cuota de Drive y crear el sheet devuelve 403;
    # si se retoma, migrar sheets.py a OAuth del usuario).
    iva_label = "con IVA (10,5%)" if req.incluir_iva else "sin IVA"
    desc_label = f" · desc {req.descuento_pct:.0f}%" if req.descuento_pct else ""
    subtitulo = f"Generado el {fecha} · Precios {iva_label}{desc_label} · VectorAI"
    xlsx_bytes = generar_excel_comparativo(
        comparativo=comparativo,
        proveedores=cached["proveedores"],
        titulo=titulo,
        subtitulo=subtitulo,
    )
    filename = f"VectorAI_Comparativa_{fecha}.xlsx"
    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _aplicar_filtros(comparativo: list, req: SheetsRequest) -> list:
    import copy
    rows = comparativo
    if req.solo_comunes:
        rows = [r for r in rows if r.get("en_varios")]
    if req.filtro_rubro and req.filtro_rubro != "Todos":
        rows = [r for r in rows if r.get("rubro") == req.filtro_rubro]

    factor_iva = 1.105 if req.incluir_iva else 1.0
    factor_desc = 1.0 - (req.descuento_pct / 100.0) if req.descuento_pct else 1.0
    factor = round(factor_iva * factor_desc, 6)

    if factor == 1.0:
        return rows

    # Aplicar factor a una copia para no mutar el cache
    result = []
    for row in rows:
        r = copy.deepcopy(row)
        for prov_data in r.get("precios", {}).values():
            prov_data["precio_sin_iva"] = round(prov_data["precio_sin_iva"] * factor, 2)
        if r.get("ahorro"):
            r["ahorro"] = round(r["ahorro"] * factor, 2)
        result.append(r)
    return result


# ── /pdf ──────────────────────────────────────────────────────────────────────
@app.post("/pdf")
async def generar_pdf(
    req: SheetsRequest,
    authorization: Optional[str] = Header(None),
):
    cached = _leer_comparativa(req.comparativa_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail={"error": "comparativa_no_encontrada",
                    "mensaje": "La comparativa expiró o no existe. Volvé a subir los PDFs."}
        )
    from exportar_pdf import generar_pdf_comparativo
    fecha  = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    fecha_visible = __import__("datetime").datetime.now().strftime("%d/%m/%Y")
    titulo = req.titulo or f"VectorAI — Comparativa {fecha}"
    iva_label  = "con IVA (10,5%)" if req.incluir_iva else "sin IVA"
    desc_label = f" · desc {req.descuento_pct:.0f}%" if req.descuento_pct else ""
    subtitulo  = f"Generado el {fecha_visible} · Precios {iva_label}{desc_label}"
    comparativo = _aplicar_filtros(cached["comparativo"], req)
    pdf_bytes = generar_pdf_comparativo(
        comparativo=comparativo,
        proveedores=cached["proveedores"],
        titulo=titulo,
        subtitulo=subtitulo,
    )
    filename = f"VectorAI_Comparativa_{fecha}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── /imagen ───────────────────────────────────────────────────────────────────
@app.post("/imagen")
async def generar_imagen(
    req: SheetsRequest,
    authorization: Optional[str] = Header(None),
):
    cached = _leer_comparativa(req.comparativa_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail={"error": "comparativa_no_encontrada",
                    "mensaje": "La comparativa expiró o no existe. Volvé a subir los PDFs."}
        )
    from exportar_imagen import generar_imagen_comparativo
    fecha  = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    fecha_visible = __import__("datetime").datetime.now().strftime("%d/%m/%Y")
    titulo = req.titulo or f"VectorAI — Comparativa {fecha}"
    iva_label  = "con IVA (10,5%)" if req.incluir_iva else "sin IVA"
    desc_label = f" · desc {req.descuento_pct:.0f}%" if req.descuento_pct else ""
    subtitulo  = f"Generado el {fecha_visible} · Precios {iva_label}{desc_label}"
    comparativo = _aplicar_filtros(cached["comparativo"], req)
    jpg_bytes = generar_imagen_comparativo(
        comparativo=comparativo,
        proveedores=cached["proveedores"],
        titulo=titulo,
        subtitulo=subtitulo,
    )
    filename = f"VectorAI_Comparativa_{fecha}.jpg"
    return StreamingResponse(
        BytesIO(jpg_bytes),
        media_type="image/jpeg",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── MercadoPago ──────────────────────────────────────────────────────────────
class MPSuscripcionRequest(BaseModel):
    user_id: str
    email: str
    plan: str = "advance"  # 'basico' (Inicial) | 'advance'

@app.post("/mp/suscripcion")
async def crear_suscripcion(req: MPSuscripcionRequest):
    """
    Crea una suscripción recurrente en MercadoPago y devuelve la URL de pago.
    Usa Preapproval (débito automático mensual).
    """
    if not MP_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail={"error": "mp_no_configurado"})

    plan = req.plan if req.plan in ("basico", "advance") else "advance"
    monto = PRECIOS_PLAN.get(plan, 48000)
    nombre_plan = "Inicial" if plan == "basico" else "Advance"

    import mercadopago
    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

    preapproval_data = {
        "preapproval_plan_id": None,  # sin plan predefinido → ad-hoc
        "reason": f"VectorAI Plan {nombre_plan} — comparador de presupuestos",
        # El plan viaja en external_reference para que el webhook active el
        # correcto: "<user_id>:<plan>".
        "external_reference": f"{req.user_id}:{plan}",
        "payer_email": req.email,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": monto,
            "currency_id": "ARS",
        },
        "back_url": f"{FRONTEND_URL}/app/comparar?suscripcion=ok",
        "status": "pending",
    }

    result = sdk.preapproval().create(preapproval_data)
    if result["status"] not in (200, 201):
        raise HTTPException(status_code=502, detail={"error": "mp_error", "detalle": result.get("response")})

    return {
        "init_point": result["response"]["init_point"],
        "preapproval_id": result["response"]["id"],
    }


MP_WEBHOOK_SECRET = os.environ.get("MP_WEBHOOK_SECRET", "")

@app.post("/mp/webhook")
async def mp_webhook(request: Request):
    """
    Webhook de MercadoPago. Cuando una suscripción se activa o renueva,
    actualiza perfiles.plan = 'advance'.
    """
    # Verificación de firma de MercadoPago (fail-closed). MP firma un MANIFIESTO
    # "id:<data.id>;request-id:<x-request-id>;ts:<ts>;" con HMAC-SHA256 — NO el
    # body crudo. El secret debe ser EXACTAMENTE el configurado en el panel de MP
    # (Tus integraciones → Webhooks). El re-consultado a MP más abajo es la 2da
    # barrera (toma el user_id de la respuesta de MP, no del atacante).
    if not MP_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="webhook_no_configurado")
    import hmac, hashlib
    sig_partes: dict = {}
    for parte in request.headers.get("x-signature", "").split(","):
        if "=" in parte:
            k, v = parte.split("=", 1)
            sig_partes[k.strip()] = v.strip()
    ts = sig_partes.get("ts", "")
    v1 = sig_partes.get("v1", "")
    req_id = request.headers.get("x-request-id", "")
    raw_body = await request.body()
    try:
        body = json.loads(raw_body or b"{}")
    except Exception:
        body = {}
    # data.id: MP lo manda en el query (?data.id=...) y en el body. Si es
    # alfanumérico, MP lo pasa a minúsculas para el manifiesto.
    data_id = request.query_params.get("data.id") or str((body.get("data") or {}).get("id", ""))
    if data_id.isalnum():
        data_id = data_id.lower()
    manifest = f"id:{data_id};request-id:{req_id};ts:{ts};"
    expected = hmac.new(MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    if not (ts and v1 and hmac.compare_digest(expected, v1)):
        raise HTTPException(status_code=401, detail="firma_invalida")
    tipo = body.get("type", "")

    if tipo not in ("preapproval", "subscription_preapproval"):
        return {"ok": True}

    mp_id = body.get("data", {}).get("id")
    if not mp_id:
        return {"ok": True}

    if not MP_ACCESS_TOKEN:
        return {"ok": True}

    import mercadopago
    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
    result = sdk.preapproval().get(mp_id)
    if result["status"] != 200:
        return {"ok": True}

    preapproval = result["response"]
    estado = preapproval.get("status", "")
    ext = preapproval.get("external_reference", "") or ""
    # external_reference = "<user_id>:<plan>". Suscripciones viejas traen solo
    # el user_id → default advance.
    user_id, _, plan_comprado = ext.partition(":")
    if plan_comprado not in ("basico", "advance", "pro"):
        plan_comprado = "advance"

    if not user_id:
        return {"ok": True}

    # user_id sale de external_reference (lo arma /mp/suscripcion con el UUID de
    # Supabase). Si no es un UUID válido (ref legada/malformada o de una prueba),
    # no tiene sentido tocar perfiles: la columna id es uuid y un valor no-UUID
    # hace fallar el UPDATE con 500. Cortamos limpio con 200 para que MP no
    # reintente en loop.
    import uuid as _uuid
    try:
        _uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError):
        print(f"webhook: external_reference con user_id no-UUID, ignorado: {user_id!r}")
        return {"ok": True}

    sb = get_supabase()
    if not sb:
        return {"ok": True}

    if estado == "authorized":
        sb.table("perfiles").update({
            "plan": plan_comprado,
            "plan_desde": datetime.now().isoformat(),
        }).eq("id", user_id).execute()
        try:
            sb.table("facturacion_eventos").insert({
                "user_id": user_id, "evento": "alta", "plan": plan_comprado,
                "monto": PRECIOS_PLAN.get(plan_comprado, 0), "mp_id": str(mp_id),
            }).execute()
        except Exception as e:
            print(f"facturacion_eventos error: {e}")
        print(f"Plan {plan_comprado} activado: {user_id}")
    elif estado in ("cancelled", "paused"):
        sb.table("perfiles").update({"plan": "free"}).eq("id", user_id).execute()
        try:
            sb.table("facturacion_eventos").insert({
                "user_id": user_id, "evento": "baja", "plan": "free",
                "monto": 0, "mp_id": str(mp_id),
            }).execute()
        except Exception as e:
            print(f"facturacion_eventos error: {e}")
        print(f"Plan cancelado, vuelve a free: {user_id}")

    return {"ok": True}


# ── V2: Cache de denominaciones + sinónimos + grupos de marcas ────────────────
import time
from rapidfuzz import fuzz, process as fuzz_process
from matching import normalize, aplicar_sinonimos, SINONIMOS, MARCAS_EQUIVALENTES

_den_cache: list[dict] | None = None
_den_cache_ts: float = 0
_DEN_TTL = 300  # 5 minutos

# Cache de sinónimos y grupos de marcas cargados desde Supabase
_sin_extra: dict[str, str] = {}          # original → canonico (desde BD, extra al código)
_grupos_extra: list[frozenset] = []      # grupos de marcas equivalentes (desde BD)
_knowledge_cache_ts: float = 0
_conv_extra: dict[str, dict] = {}

# Marcadores de "precio por metro" en el texto o la unidad del ítem
_UNIDADES_METRO = {"ML", "M", "MT", "MTS", "METRO", "METROS"}
_RE_POR_METRO = re.compile(r"^\s*mts?\.?\s|\b(?:x|por)\s*(?:metro|ml|mt)\b", re.I)


def _convertir_unidad(codigo: str, desc: str, unidad_item: str, pu: float, cant: float):
    """Normaliza precio por metro → presentación del material (tira/rollo).

    Solo actúa con MARCADOR EXPLÍCITO de metro (unidad ML/MTS del documento o
    "MTS …"/"x metro" en la descripción) y si el material tiene conversión
    activa con unidad_comercial='m'. La conversión preserva el total de línea:
    pu×factor y cant÷factor.

    Devuelve (pu, cant, unidad_final, nota|None, ambigua). ambigua=True cuando
    el material se vende por presentación (tira/rollo) pero el texto no dice ni
    "por metro" ni la presentación completa — el precio no es confiable y el
    ítem debe ir a revisión en vez de entrar solo al histórico.
    """
    conv = _conv_extra.get(codigo)
    unidad_norm = (unidad_item or "").strip(". ").upper()
    if not conv or conv["unidad_comercial"] != "m":
        return pu, cant, unidad_norm or "UN", None, False

    factor = conv["factor"]
    d = (desc or "").lower()
    por_metro = unidad_norm in _UNIDADES_METRO or bool(_RE_POR_METRO.search(desc or ""))
    if por_metro:
        nota = f"normalizado a {conv['unidad_base']} (×{factor:g})"
        return round(pu * factor, 2), cant / factor, conv["unidad_base"], nota, False

    # ¿El texto menciona la presentación completa? ("x 4 mts", "20x4", "tira", "rollo")
    f = f"{factor:g}"
    presentacion = bool(re.search(rf"[x*]\s*{f}\s*m|\b{f}\s*m(?:t|ts|mts)?\b|x\s*{f}\b|tira|rollo|bobina", d))
    if presentacion:
        return pu, cant, conv["unidad_base"], None, False

    # Sin marcador de metro ni de presentación: unidad ambigua
    return pu, cant, unidad_norm or "UN", None, True


# ── Tipo de cambio para documentos cotizados en USD ───────────────────────────
# Algunos proveedores (JMA perfiles, importadores) cotizan en dólares. Para que
# la comparativa y precios_historicos queden siempre en ARS, el precio se
# convierte con el dólar oficial VENTA del día (dolarapi.com). El valor
# original en USD queda en precio_raw + moneda='USD'.
_tc_cache: dict = {"valor": None, "ts": 0}
_TC_TTL = 3600  # 1 hora


def _tc_oficial() -> float | None:
    """Dólar oficial venta, cacheado 1h. None si la API no responde y no hay
    caché previa (el caller decide fallar cerrado)."""
    import requests as _rq
    ahora = time.time()
    if _tc_cache["valor"] and ahora - _tc_cache["ts"] < _TC_TTL:
        return _tc_cache["valor"]
    try:
        r = _rq.get("https://dolarapi.com/v1/dolares/oficial", timeout=8)
        r.raise_for_status()
        venta = float(r.json()["venta"])
        if venta > 0:
            _tc_cache.update(valor=venta, ts=ahora)
            return venta
    except Exception as e:
        print(f"[tc] Error consultando dolarapi: {e}")
    return _tc_cache["valor"]  # mejor un TC de hace >1h que nada


# Espesores comerciales de steel framing: los proveedores escriben el nominal
# (0.9 / 1.2 / 1.25 / 1.6 / 2.0) y el maestro el real con zinc (0,94 / 1,29 /
# 1,64 / 2,04). Se canonizan SOLO en contexto de perfiles PGC/PGU/PGO para no
# tocar medidas de otros rubros. Nota: normalize() ya convirtió la coma en
# espacio, por eso los patrones aceptan "1 29" además de "1.29".
_RE_PERFIL_STEEL = re.compile(r"\b(?:pgc|pgu|pgo)\b")
# Separador obligatorio ("2 0" o "2.0") para no capturar "200" de "PGC 200";
# lookbehind en vez de \b para agarrar formas pegadas ya separadas ("e 1.2").
_GAUGES_STEEL = [
    (re.compile(r"(?<![\d.])0[. ](?:89|90|94|9)(?!\d)"), "0.94"),
    (re.compile(r"(?<![\d.])1[. ](?:20|25|29|2)(?!\d)"), "1.29"),
    (re.compile(r"(?<![\d.])1[. ](?:60|64|6)(?!\d)"), "1.64"),
    (re.compile(r"(?<![\d.])2[. ](?:00|04|0)(?!\d)"), "2.04"),
]
# "E1.2" viene pegado como un solo token: separar el prefijo de espesor
_RE_E_PEGADA = re.compile(r"\be(?=\d)")


def _prep_v2(s: str) -> str:
    """Normaliza + aplica sinónimos → lowercase. Usado en ambos lados del match."""
    t = aplicar_sinonimos(normalize(s)).lower()
    if _RE_PERFIL_STEEL.search(t):
        t = _RE_E_PEGADA.sub("e ", t)
        for rx, canon in _GAUGES_STEEL:
            t = rx.sub(canon, t)
    return t


def _load_knowledge_cache():
    """Carga sinonimos y grupos_marcas desde Supabase (TTL compartido con denominaciones)."""
    global _sin_extra, _grupos_extra, _knowledge_cache_ts
    ahora = time.time()
    if (ahora - _knowledge_cache_ts) < _DEN_TTL:
        return

    sb = get_supabase()
    if not sb:
        return

    # Sinónimos adicionales desde BD (complementan los hardcodeados en matching.py)
    try:
        res = sb.table("sinonimos").select("original,canonico").eq("activo", True).execute()
        _sin_extra = {r["original"]: r["canonico"] for r in (res.data or [])}
    except Exception as e:
        print(f"[v2] Error cargando sinonimos: {e}")

    # Grupos de marcas equivalentes desde BD
    try:
        res = sb.table("grupos_marcas").select("marca,grupo").eq("activo", True).execute()
        grupos: dict[str, set] = {}
        for r in (res.data or []):
            grupos.setdefault(r["grupo"], set()).add(r["marca"].upper())
        _grupos_extra = [frozenset(v) for v in grupos.values()]
    except Exception as e:
        print(f"[v2] Error cargando grupos_marcas: {e}")

    # Conversiones de unidad por material (ej. cable por metro → rollo 100m)
    global _conv_extra
    try:
        res = sb.table("conversion_unidades").select(
            "codigo_material,unidad_comercial,factor,unidad_base"
        ).eq("activo", True).execute()
        _conv_extra = {
            r["codigo_material"]: {
                "unidad_comercial": (r["unidad_comercial"] or "").strip().lower(),
                "factor":           float(r["factor"]),
                "unidad_base":      r["unidad_base"] or "",
            }
            for r in (res.data or []) if float(r["factor"] or 0) > 0
        }
    except Exception as e:
        print(f"[v2] Error cargando conversion_unidades: {e}")

    _knowledge_cache_ts = ahora
    print(f"[v2] Knowledge cache: {len(_sin_extra)} sinónimos BD, {len(_grupos_extra)} grupos marcas, {len(_conv_extra)} conversiones")


def _mismo_grupo_v2(texto_a: str, texto_b: str) -> bool:
    """True si ambos textos comparten al menos una marca del mismo grupo (BD + hardcoded)."""
    todos_grupos = list(MARCAS_EQUIVALENTES) + _grupos_extra
    for grupo in todos_grupos:
        en_a = any(m in texto_a.upper() for m in grupo)
        en_b = any(m in texto_b.upper() for m in grupo)
        if en_a and en_b:
            return True
    return False


def _get_denominaciones() -> list[dict]:
    """Carga material_denominaciones desde Supabase con cache de 5 min.
    Agrega campo 'denominacion_norm' (sinónimos aplicados) para matching mejorado.
    """
    global _den_cache, _den_cache_ts
    ahora = time.time()
    if _den_cache is not None and (ahora - _den_cache_ts) < _DEN_TTL:
        return _den_cache

    sb = get_supabase()
    if not sb:
        return _den_cache or []

    # Cargar sinónimos/grupos antes de armar el índice
    _load_knowledge_cache()

    try:
        todas = []
        page = 0
        PAGE = 1000
        while True:
            res = sb.table("material_denominaciones") \
                    .select("codigo_material,denominacion,origen,confianza,frecuencia_encontrada") \
                    .range(page * PAGE, (page + 1) * PAGE - 1) \
                    .execute()
            batch = res.data or []
            todas.extend(batch)
            if len(batch) < PAGE:
                break
            page += 1

        # Pre-computar forma normalizada (sinónimos aplicados) para cada alias
        for d in todas:
            d["denominacion_norm"] = _prep_v2(d["denominacion"])

        # Descartar aliases "basura": textos sin ninguna palabra real de 3+ letras
        # (unidades/números/fragmentos como "m3", "h21", "1 x 1", "3*6"). Con
        # token_set_ratio matchean CUALQUIER descripción que los contenga a score
        # 100 y arruinan el matching (ej. "hormigón ... x m3" → alias "m3").
        # Umbral en 3 (no 4): 'TEE', 'IPS', 'FUS' son vocabulario real de
        # sanitarios ('p30 tee de 20 mm ips fus i'); los genéricos de una sola
        # palabra corta quedan acotados por la guarda anti-genérico del match.
        antes = len(todas)
        todas = [d for d in todas
                 if re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", d["denominacion_norm"] or "")]
        if antes != len(todas):
            print(f"[v2] Descartados {antes - len(todas)} aliases basura (sin palabra real)")

        # Los fragmentos de la migración (denominacion_principal sola como
        # 'puerta', o descripcion sola como 'estandar'/'con aluminio') quedan
        # FUERA del pool: los reemplazan los aliases sintéticos con el nombre
        # completo. Siguen en la BD por si hiciera falta volver atrás.
        antes = len(todas)
        todas = [d for d in todas if d.get("origen") not in ("migracion_item", "migracion_detalle")]
        if antes != len(todas):
            print(f"[v2] Excluidos {antes - len(todas)} fragmentos de migración (los cubren los sintéticos)")

        # Resolver aliases AMBIGUOS: el mismo texto bajo más de un código (la
        # migración dejó la denominación de familia como alias en cada material:
        # 'fusión gas' ×33 códigos, 'tapa' ×4). Además de dar 100 falso contra
        # un código arbitrario, esos empates desplazan a los aliases específicos
        # fuera de la ventana top_n*3 de fuzz_process.extract.
        # Regla: sobrevive solo la copia de MAYOR confianza; si hay empate en el
        # máximo, el texto no identifica nada y se excluye el grupo entero del
        # matching (queda en la BD).
        grupos_texto: dict[str, list] = {}
        for d in todas:
            grupos_texto.setdefault(d["denominacion_norm"], []).append(d)
        antes = len(todas)
        filtradas = []
        for grupo in grupos_texto.values():
            codigos = {g["codigo_material"] for g in grupo}
            if len(codigos) == 1:
                filtradas.extend(grupo)
                continue
            conf_max = max(g.get("confianza") or 80 for g in grupo)
            ganadores = [g for g in grupo if (g.get("confianza") or 80) == conf_max]
            if len({g["codigo_material"] for g in ganadores}) == 1:
                filtradas.extend(ganadores)
        todas = filtradas
        if antes != len(todas):
            print(f"[v2] Excluidos {antes - len(todas)} aliases ambiguos (mismo texto en varios códigos)")

        # Aliases SINTÉTICOS del maestro: el nombre completo de cada material
        # (denominacion_principal + descripcion). La migración solo indexó los
        # fragmentos por separado ('puerta' / '0,85x2,05 - a30 negro') y el
        # nombre completo nunca existió como alias — por eso los fragmentos
        # daban 100 falso. Estos apuntan a su propio material por construcción
        # (riesgo cero) y llevan la carga de los matches legítimos, lo que
        # permite endurecer la guarda anti-fragmento. Las medidas fusionadas
        # ("100MMX25") se separan para tokenizar como escriben los proveedores.
        try:
            res = sb.table("materiales_validados") \
                    .select("codigo,denominacion_principal,descripcion").execute()
            n_sint = 0
            for m in (res.data or []):
                nombre = f"{m.get('denominacion_principal') or ''} {m.get('descripcion') or ''}".strip()
                if not nombre:
                    continue
                sep = re.sub(r"(?<=\d)\s*[xX*]\s*(?=\d)", " x ", nombre)
                sep = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", sep)
                norm_sint = _prep_v2(sep)
                todas.append({
                    "codigo_material":       m["codigo"],
                    "denominacion":          nombre,
                    "confianza":             100,
                    "frecuencia_encontrada": 1,
                    "denominacion_norm":     norm_sint,
                    "sintetico":             True,
                    "nums":                  extract_nums(norm_sint),
                })
                n_sint += 1
            print(f"[v2] Aliases sintéticos del maestro: {n_sint}")
        except Exception as e:
            print(f"[v2] Error generando aliases sintéticos: {e}")

        # Ordenar por confianza desc: fuzz_process.extract trunca a top_n*3
        # candidatos y en empates de score devuelve los primeros de la lista.
        # Con este orden, los empates favorecen al alias más confiable ANTES
        # del truncado (el sort por confianza de _match_v2 llega tarde si el
        # alias correcto quedó fuera de la ventana).
        todas.sort(key=lambda d: -(d.get("confianza") or 80))

        _den_cache = todas
        _den_cache_ts = ahora
        print(f"[v2] Cache denominaciones: {len(todas)} aliases cargados (con normalización)")
        return todas
    except Exception as e:
        print(f"[v2] Error cargando denominaciones: {e}")
        return _den_cache or []


def _invalidar_cache_den():
    global _den_cache_ts, _knowledge_cache_ts
    _den_cache_ts = 0
    _knowledge_cache_ts = 0


def _match_v2(texto: str, denominaciones: list[dict], top_n: int = 3) -> list[dict]:
    """
    Fuzzy match con sinónimos aplicados en ambos lados + bonus por grupo de marca.
    Retorna hasta top_n resultados con nivel: automatico / dudoso / sin_match.
    """
    if not texto or not denominaciones:
        return []

    texto_prep = _prep_v2(texto)   # normalizar + sinónimos → lowercase
    if not texto_prep:
        return []

    # Usar denominacion_norm (pre-normalizada) si existe, si no la raw
    textos_norm = [d.get("denominacion_norm") or d["denominacion"] for d in denominaciones]

    resultados = fuzz_process.extract(
        texto_prep,
        textos_norm,
        scorer=fuzz.token_set_ratio,
        limit=top_n * 3,   # pedir más candidatos para aplicar el bonus de marca
        score_cutoff=48,
    )

    salida = []
    n_tokens_texto = len(texto_prep.split())
    texto_nums = extract_nums(texto_prep)
    for texto_match, score, idx in resultados:
        den = denominaciones[idx]
        # Bonus si comparten marca del mismo grupo equivalente
        if _mismo_grupo_v2(texto, den["denominacion"]):
            score = min(100, score + 6)
        # Guarda anti-fragmento (bug clase PERFIL/BROCAS): cuando un lado tiene
        # ≤2 tokens y los textos no son idénticos, token_set da 100 por
        # contención sin identificar nada ('puerta', 'contenedor estandar'
        # contra cualquier familia). Nunca automático — tope 84. Los matches
        # legítimos los llevan los aliases sintéticos (nombre completo).
        alias_norm = den.get("denominacion_norm") or den["denominacion"]
        n_tokens_alias = len(alias_norm.split())
        # Excepción: un alias SINTÉTICO corto con números ('cupla 110') no es
        # un fragmento — es el nombre canónico completo de un material chico,
        # y su guarda numérica ya protege contra medidas que no coinciden.
        sintetico_con_medida = den.get("sintetico") and bool(den.get("nums"))
        lado_corto_es_texto = n_tokens_texto < n_tokens_alias
        if min(n_tokens_alias, n_tokens_texto) <= 2 and alias_norm != texto_prep \
                and not (sintetico_con_medida and not lado_corto_es_texto):
            score = min(score, 84.0)
        # Guarda numérica para sintéticos: si el nombre canónico tiene números
        # (medida/presentación) y el texto no los contiene, no puede ser
        # automático (ej. barniz x 1 LT contra el material de 20LT).
        if den.get("sintetico") and score >= 85:
            nums_alias = den.get("nums") or set()
            if nums_alias and not nums_alias.issubset(texto_nums):
                score = min(score, 84.0)
        if score >= 85:
            nivel = "automatico"
        elif score >= 60:
            nivel = "dudoso"
        else:
            nivel = "sin_match"
        salida.append({
            "codigo_material":        den["codigo_material"],
            "denominacion_matcheada": den["denominacion"],   # mostrar la original, no la norm
            "score":                  round(score, 1),
            "nivel":                  nivel,
            "confianza_alias":        den.get("confianza", 80),
        })

    # Ordenar por score desc; en empate de score, preferir el alias de mayor
    # confianza (evita quedarse con un alias contaminado que puntúa igual, ej.
    # "hormigón h-21" empatado 100 entre CONS113=hormigón y CONS108=arena).
    salida.sort(key=lambda x: (-x["score"], -x.get("confianza_alias", 80)))
    return salida[:top_n]


# ── Modelos V2 ────────────────────────────────────────────────────────────────
class ConfirmarItemV2(BaseModel):
    desc_prov: str
    proveedor: str
    codigo_material: str      # confirmado por usuario (puede ser el sugerido u otro)
    precio_sin_iva: float
    unidad: str = "UN"
    cantidad: float = 1.0
    item_id: Optional[str] = None   # id en presupuesto_items (devuelto por /analizar-v2)
    # Trazabilidad (echo de /analizar-v2): precio/unidad tal como vinieron en
    # el documento, moneda original y nota de conversión aplicada.
    precio_raw: Optional[float] = None
    unidad_raw: Optional[str] = None
    moneda: Optional[str] = None
    conversion: Optional[str] = None

class PendienteItem(BaseModel):
    desc_prov: str
    proveedor: str
    precio_sin_iva: float
    unidad: str = "UN"
    item_id: Optional[str] = None   # id en presupuesto_items (devuelto por /analizar-v2)

class ConfirmarV2Request(BaseModel):
    comparativa_id: str
    confirmados: list[ConfirmarItemV2]
    sin_match: list[PendienteItem] = []


# ── Modelos: emparejar terminaciones ──────────────────────────────────────────
class VinculoItemIn(BaseModel):
    item_id: str                    # id en presupuesto_items (de /analizar-v2)
    proveedor: str                  # nombre del proveedor (clave en la comparativa)
    desc_prov: str = ""             # descripción original, para el "recordar"

class ConceptoIn(BaseModel):
    nombre: str
    unidad: str = "c/u"
    cantidad: float = 1.0
    items: list[VinculoItemIn]

class VinculoManualRequest(BaseModel):
    comparativa_id: str
    conceptos: list[ConceptoIn]
    recordar: bool = True


# ── /analizar-v2 ──────────────────────────────────────────────────────────────
from fastapi import Form as FastAPIForm

# Progreso de análisis en curso, por id que genera el frontend. En memoria:
# una sola instancia de Railway y vida útil de minutos. El frontend lo consulta
# por polling mientras espera la respuesta del análisis.
_PROGRESO: dict[str, dict] = {}


@app.get("/analizar-v2/progreso/{progreso_id}")
async def progreso_analisis(progreso_id: str):
    return _PROGRESO.get(progreso_id) or {"estado": "desconocido"}


@app.post("/analizar-v2")
def analizar_v2(  # def SIN async: el trabajo es bloqueante (extracción, visión,
    # Supabase sync) y como corutina congelaba el event loop — el polling de
    # /analizar-v2/progreso no respondía hasta terminar. Como def, FastAPI lo
    # corre en el threadpool y el progreso se actualiza en vivo.
    files: list[UploadFile] = File(default=[]),
    file_configs: Optional[str] = FastAPIForm(default=None),
    progreso_id: Optional[str] = FastAPIForm(default=None),
    obra_id: Optional[str] = FastAPIForm(default=None),
    authorization: Optional[str] = Header(None),
):
    """
    V2: Matchea presupuestos contra material_denominaciones en Supabase.
    Fuentes soportadas: PDF con texto, fotos (JPG/PNG, vía OCR/visión)
    y planillas (.xlsx/.csv).
    file_configs: JSON array con {bloque, nombre_proveedor, con_iva, descuento}
    por archivo (mismo orden que files).
    Devuelve 3 grupos por proveedor: automatico / dudoso / sin_match.
    """
    user = get_user_plan(authorization)
    _gate_analisis(user)

    # Parsear config por archivo (override de IVA y descuento)
    cfgs: list[dict] = []
    if file_configs:
        try:
            parsed = json.loads(file_configs)
            cfgs = parsed if isinstance(parsed, list) else []
        except Exception:
            cfgs = []

    _validar_archivos(files, cfgs, user["plan"])

    denominaciones = _get_denominaciones()
    if not denominaciones:
        raise HTTPException(
            status_code=503,
            detail={"error": "bd_no_disponible", "mensaje": "No se pudo cargar la base de materiales."}
        )

    # Cargar materiales validados para enriquecer respuesta (nombre, rubro, unidad)
    sb = get_supabase()
    materiales_dict: dict[str, dict] = {}
    if sb:
        try:
            res = sb.table("materiales_validados") \
                    .select("codigo,categoria,denominacion_principal,descripcion,unidades_posibles") \
                    .execute()
            materiales_dict = {m["codigo"]: m for m in (res.data or [])}
        except Exception as e:
            print(f"[v2] Error cargando materiales_validados: {e}")

    resultados = {}
    errores = []
    presupuestos_creados: list[str] = []

    # Obra (plan alto): solo si existe y es del usuario
    obra = _obra_del_usuario(sb, obra_id, user["user_id"]) if _plan_permite_obras(user["plan"]) else None
    obra_valida = obra["id"] if obra else None

    # entradas = [(nombre_archivo, contenido_bytes, cfg), ...]
    entradas: list[tuple[str, bytes, dict]] = []
    for idx, f in enumerate(files or []):
        contenido = f.file.read()
        entradas.append((f.filename or f"archivo_{idx}", contenido,
                         cfgs[idx] if idx < len(cfgs) else {}))

    # Resolver un nombre de proveedor por bloque: todos los archivos de un mismo
    # bloque son el mismo proveedor. Si el usuario no lo nombró, se auto-detecta
    # desde el primer archivo del bloque. Sin 'bloque' (frontend viejo) cada
    # archivo es su propio grupo (índice) → 1 archivo = 1 proveedor.
    nombre_por_bloque: dict = {}
    for idx, (fname, _, cfg) in enumerate(entradas):
        clave = cfg.get("bloque", idx)
        if clave not in nombre_por_bloque:
            nombre = (cfg.get("nombre_proveedor") or "").strip()
            if not nombre:
                nombre = detectar_proveedor(fname) or Path(fname or "archivo").stem.upper()
            nombre_por_bloque[clave] = nombre

    for file_idx, (fname, content, cfg_archivo) in enumerate(entradas):
        if progreso_id:
            if len(_PROGRESO) > 200:
                _PROGRESO.clear()
            _PROGRESO[progreso_id] = {
                "estado": "procesando", "archivo": fname,
                "idx": file_idx + 1, "total": len(entradas),
                "etapa": "procesando",
            }
        # ── Rutear por tipo de contenido ────────────────────────────────────
        lower = (fname or "").lower()
        tmp_path = None
        try:
            if content.startswith(b"%PDF"):
                tipo_fuente = "pdf"
            elif content[:4] == b"PK\x03\x04" and not lower.endswith((".jpg", ".jpeg", ".png")):
                tipo_fuente = "xlsx"   # xlsx/xlsm son ZIP
            elif content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                errores.append({"archivo": fname,
                                "error": "Excel viejo (.xls) no soportado — abrilo y guardalo como .xlsx."})
                continue
            elif lower.endswith(".csv"):
                tipo_fuente = "csv"
            elif content[:3] == b"\xff\xd8\xff" or content[:4] in (b"\x89PNG", b"RIFF") or \
                    lower.endswith((".jpg", ".jpeg", ".png", ".jfif", ".webp")):
                tipo_fuente = "imagen"
            else:
                errores.append({"archivo": fname,
                                "error": "Formato no reconocido. Soportados: PDF, JPG/PNG, .xlsx, .csv o link de Google Sheets."})
                continue
        except Exception as e:
            errores.append({"archivo": fname, "error": str(e)})
            continue

        presupuesto_id = None
        try:
            proveedor = nombre_por_bloque[cfg_archivo.get("bloque", file_idx)]
            proveedor_id = _get_proveedor_id(sb, proveedor)

            if tipo_fuente == "pdf":
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                resultado = extraer(tmp_path)
                # PDF escaneado (sin capa de texto) → renderizar páginas y OCR.
                # Solo si la extracción normal no sacó nada Y el PDF no tiene
                # texto: si tiene texto pero 0 ítems, es un formato nuevo a
                # cubrir con regex, no gastamos visión en eso.
                if not resultado.get("items") and pdf_sin_texto(content):
                    if progreso_id and progreso_id in _PROGRESO:
                        _PROGRESO[progreso_id]["etapa"] = "procesando documento escaneado (≈20s por página)"
                    resultado = extraer_pdf_escaneado(content)
            elif tipo_fuente == "xlsx":
                resultado = extraer_xlsx(content)
            elif tipo_fuente == "csv":
                resultado = extraer_csv(content)
            else:  # imagen → OCR/visión
                if progreso_id and progreso_id in _PROGRESO:
                    _PROGRESO[progreso_id]["etapa"] = "procesando foto (≈20s)"
                resultado = extraer_imagen(content, fname)

            items = resultado.get("items", [])

            # Documento cotizado en dólares (JMA perfiles, importadores):
            # convertir a ARS con el oficial venta del día para que la
            # comparativa y el histórico queden siempre en una sola moneda.
            # Sin TC disponible se falla cerrado: mejor pedir reintento que
            # comparar dólares contra pesos.
            tc_usd = None
            if items and (resultado.get("moneda") or "ARS").upper() == "USD":
                tc_usd = _tc_oficial()
                if not tc_usd:
                    errores.append({
                        "archivo": fname,
                        "error": (f"El presupuesto de {proveedor} está cotizado en USD y "
                                  "no se pudo obtener el tipo de cambio oficial para "
                                  "convertirlo. Volvé a intentar en unos minutos."),
                    })
                    continue

            # Documento sin precios por ítem (ej. EN SECO/GRUPO MMC con solo
            # DESCRIPCIÓN + CANTIDAD): no hay nada que comparar → avisar claro en
            # vez de devolver 0 ítems mudo (que parece que la app está rota).
            if not items and resultado.get("sin_precios"):
                errores.append({
                    "archivo": fname,
                    "error": (f"El presupuesto de {proveedor} lista materiales y "
                              "cantidades pero no tiene precios por ítem, así que no "
                              "se puede comparar. Pedí una versión con precios unitarios."),
                })
                continue

            automatico, dudoso, sin_match = [], [], []

            # Config por archivo: siempre la que el usuario eligió al subir.
            # IVA y descuento son condiciones de cada operación, no del proveedor.
            fac_archivo  = 1.105 if cfg_archivo.get("con_iva", True) else 1.0
            try:
                desc_archivo = max(0.0, min(100.0, float(cfg_archivo.get("descuento", 0) or 0)))
            except (TypeError, ValueError):
                desc_archivo = 0.0

            # Registrar el documento subido (solo logueados: user_id es NOT NULL).
            # Mismo archivo del mismo proveedor re-analizado → REEMPLAZA el
            # registro anterior en vez de duplicarlo en Mis Presupuestos: se
            # borran sus líneas viejas y se reutiliza el id con el análisis
            # nuevo (que además matchea mejor a medida que el motor aprende).
            if sb and user["user_id"] != "anonimo":
                try:
                    prev = sb.table("presupuestos").select("id") \
                             .eq("user_id", user["user_id"]) \
                             .eq("archivo", fname) \
                             .eq("proveedor_detectado", proveedor) \
                             .limit(1).execute()
                    if prev.data:
                        presupuesto_id = prev.data[0]["id"]
                        sb.table("presupuesto_items").delete() \
                          .eq("presupuesto_id", presupuesto_id).execute()
                        sb.table("presupuestos").update({
                            "proveedor_id": proveedor_id,
                            "incluye_iva":  bool(cfg_archivo.get("con_iva", True)),
                            "factor_iva":   fac_archivo,
                            "descuento_pct": desc_archivo,
                            "metodo_extraccion": resultado.get("metodo_extraccion"),
                            "estado":       "PROCESANDO",
                            "obra_id":      obra_valida,
                            "created_at":   datetime.now().isoformat(),
                        }).eq("id", presupuesto_id).execute()
                        presupuestos_creados.append(presupuesto_id)
                    else:
                        pres = sb.table("presupuestos").insert({
                            "user_id":             user["user_id"],
                            "proveedor_id":        proveedor_id,
                            "proveedor_detectado": proveedor,
                            "archivo":             fname,
                            "incluye_iva":         bool(cfg_archivo.get("con_iva", True)),
                            "factor_iva":          fac_archivo,
                            "descuento_pct":       desc_archivo,
                            "metodo_extraccion":   resultado.get("metodo_extraccion"),
                            "estado":              "PROCESANDO",
                            "obra_id":             obra_valida,
                        }).execute()
                        if pres.data:
                            presupuesto_id = pres.data[0]["id"]
                            presupuestos_creados.append(presupuesto_id)
                except Exception as e:
                    print(f"[v2] Error registrando presupuesto para {fname}: {e}")
            def precio_archivo(pu: float, _fac=fac_archivo, _desc=desc_archivo) -> float:
                return round(pu / _fac * (1 - _desc / 100), 2)

            def _precio_inconsistente(pu: float, cant: float, total: float) -> bool:
                """Guarda de calidad post-extracción: si el documento traía un
                total de línea y pu×cant no cierra contra él (tolerancia 1%),
                el precio unitario es sospechoso — columna corrida del parser u
                OCR que leyó mal un dígito. Sin total extraído no hay señal
                (los extractores lo completan con pu×cant)."""
                return total > 0 and abs(pu * cant - total) > max(1.0, 0.01 * total)

            for item in items:
                desc = (item.get("desc") or "").strip()
                pu   = float(item.get("pu") or 0)
                if not desc or pu <= 0:
                    continue

                cant   = float(item.get("cant") or 1)
                # La guarda corre con los números ORIGINALES del documento
                sospechoso = _precio_inconsistente(pu, cant, float(item.get("total") or 0))

                matches = _match_v2(desc, denominaciones, top_n=3)

                # Normalización de unidades: por metro → tira/rollo del material
                # matcheado. Preserva el total de línea (pu×f, cant÷f).
                unidad_final = (item.get("unidad") or "").strip(". ").upper() or "UN"
                # Trazabilidad: precio y unidad tal como vinieron en el documento
                # (si el doc está en USD, precio_raw queda en USD y moneda='USD')
                pu_raw, unidad_raw = round(pu, 4), unidad_final
                notas_conv, unidad_ambigua = [], False
                if tc_usd:
                    pu = pu * tc_usd
                    notas_conv.append(f"USD→ARS ×{tc_usd:g} (oficial venta)")
                if matches and matches[0]["nivel"] != "sin_match":
                    pu, cant, unidad_final, nota_unidad, unidad_ambigua = _convertir_unidad(
                        matches[0]["codigo_material"], desc, item.get("unidad") or "", pu, cant)
                    if nota_unidad:
                        notas_conv.append(nota_unidad)
                conversion_nota = " · ".join(notas_conv) or None

                precio = precio_archivo(pu)

                base = {
                    "desc_prov":     desc,
                    "cod_prov":      str(item.get("cod") or "").strip(),
                    "precio_sin_iva": precio,
                    "precio_con_iva": round(pu, 2),
                    "cant":          cant,
                    "unidad":        unidad_final,
                    "precio_raw":    pu_raw,
                    "unidad_raw":    unidad_raw,
                    "moneda":        "USD" if tc_usd else "ARS",
                }
                if sospechoso:
                    base["precio_sospechoso"] = True
                if conversion_nota:
                    base["conversion"] = conversion_nota
                if unidad_ambigua:
                    base["unidad_ambigua"] = True

                if not matches or matches[0]["nivel"] == "sin_match":
                    sin_match.append(base)
                    continue

                mejor = matches[0]
                mat   = materiales_dict.get(mejor["codigo_material"], {})

                # Alternativas sin repetir código (varios aliases pueden apuntar
                # al mismo material) y con descripción para que el usuario pueda
                # distinguir materiales con la misma denominación (ej. CABLE 1MM
                # vs CABLE 2,5MM).
                alternativas = []
                codigos_vistos = {mejor["codigo_material"]}
                for m in matches[1:]:
                    cod_alt = m["codigo_material"]
                    if cod_alt in codigos_vistos:
                        continue
                    codigos_vistos.add(cod_alt)
                    mat_alt = materiales_dict.get(cod_alt, {})
                    alternativas.append({
                        "codigo_material": cod_alt,
                        "denominacion":    mat_alt.get("denominacion_principal", m["denominacion_matcheada"]),
                        "descripcion":     mat_alt.get("descripcion", ""),
                        "score":           m["score"],
                    })

                entry = {
                    **base,
                    "codigo_material":       mejor["codigo_material"],
                    "denominacion_matcheada": mejor["denominacion_matcheada"],
                    "score":                 mejor["score"],
                    "nivel":                 mejor["nivel"],
                    "categoria":             mat.get("categoria", ""),
                    "denominacion_principal": mat.get("denominacion_principal", ""),
                    "descripcion":           mat.get("descripcion", ""),
                    "alternativas":          alternativas,
                }

                # Precio sospechoso o unidad ambigua → nunca automático: baja a
                # revisión para que un número roto o no comparable no entre solo
                # a precios_historicos.
                if mejor["nivel"] == "automatico" and not sospechoso and not unidad_ambigua:
                    automatico.append(entry)
                else:
                    dudoso.append(entry)

            # Guardar precios automáticos (alta confianza) en histórico sin esperar confirmación.
            # Los dudosos y sin_match se guardan solo cuando el usuario confirma.
            if sb and automatico:
                try:
                    sb.table("precios_historicos").insert([
                        {
                            "proveedor":       proveedor,
                            "proveedor_id":    proveedor_id,
                            "codigo_material":  item["codigo_material"],
                            "unidad":          item.get("unidad") or "UN",
                            "precio":          item["precio_sin_iva"],
                            "cantidad":        max(1, round(float(item.get("cant", 1)))),
                            "pdf_origen":      fname,
                            "precio_raw":      item.get("precio_raw"),
                            "unidad_raw":      item.get("unidad_raw"),
                            "conversion_aplicada": item.get("conversion"),
                            "moneda":          item.get("moneda", "ARS"),
                        }
                        for item in automatico
                    ]).execute()
                except Exception as e:
                    print(f"[v2] Error guardando precios_historicos para {proveedor}: {e}")

            # Guardar cada línea del PDF con su resultado de match. Los ids
            # generados se devuelven en la respuesta (item_id) para que el
            # frontend pueda referenciarlos al confirmar.
            if sb and presupuesto_id:
                try:
                    filas, origen_filas = [], []
                    for grupo, estado in ((automatico, "MATCH"), (dudoso, "REVISAR"), (sin_match, "SIN_MATCH")):
                        for it in grupo:
                            origen_filas.append(it)
                            filas.append({
                                "presupuesto_id":    presupuesto_id,
                                "texto_original":    it["desc_prov"],
                                "texto_normalizado": it["desc_prov"].strip().lower(),
                                "cantidad":          it.get("cant", 1),
                                "precio":            it["precio_sin_iva"],
                                "codigo_material":   it.get("codigo_material"),
                                "score_match":       int(round(float(it["score"]))) if it.get("score") is not None else None,
                                "estado_match":      estado,
                                "origen_match":      "fuzzy" if estado != "SIN_MATCH" else None,
                            })
                    if filas:
                        res_items = sb.table("presupuesto_items").insert(filas).execute()
                        if res_items.data and len(res_items.data) == len(origen_filas):
                            for it, fila_bd in zip(origen_filas, res_items.data):
                                it["item_id"] = fila_bd["id"]
                    sb.table("presupuestos").update({"estado": "PROCESADO"}).eq("id", presupuesto_id).execute()
                except Exception as e:
                    print(f"[v2] Error guardando presupuesto_items para {fname}: {e}")

            # Fusionar con lo ya acumulado del proveedor: un bloque puede tener
            # varios PDFs, y antes esto pisaba el resultado del archivo anterior.
            acc = resultados.get(proveedor)
            if acc is None:
                acc = {
                    "automatico": [], "dudoso": [], "sin_match": [],
                    "iva_detectado":     resultado.get("iva_detectado"),
                    "metodo_extraccion": resultado.get("metodo_extraccion", "desconocido"),
                    "n_items_extraidos": 0,
                    "cfg_aplicada": {
                        "con_iva":   cfg_archivo.get("con_iva", True) if cfg_archivo else (factor_iva(proveedor) != 1.0),
                        "descuento": cfg_archivo.get("descuento", 0) if cfg_archivo else descuento_proveedor(proveedor),
                    },
                }
                resultados[proveedor] = acc

            acc["automatico"].extend(automatico)
            acc["dudoso"].extend(dudoso)
            acc["sin_match"].extend(sin_match)
            acc["n_items_extraidos"] += resultado.get("n_items", 0)
            if tc_usd:
                acc["moneda_documento"] = "USD"
                acc["tc_aplicado"] = tc_usd

        except Exception as e:
            errores.append({"archivo": fname, "error": str(e)})
            if sb and presupuesto_id:
                try:
                    sb.table("presupuestos").update({"estado": "ERROR"}).eq("id", presupuesto_id).execute()
                except Exception:
                    pass
        finally:
            # tmp_path solo existe para PDFs (los demás tipos se procesan en memoria)
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    if progreso_id:
        _PROGRESO.pop(progreso_id, None)

    if not resultados:
        raise HTTPException(status_code=422, detail={"error": "sin_resultados", "errores": errores})

    # Recalcular stats por proveedor sobre las listas ya fusionadas
    for data in resultados.values():
        n_auto, n_dud, n_sin = len(data["automatico"]), len(data["dudoso"]), len(data["sin_match"])
        total = n_auto + n_dud + n_sin
        data["stats"] = {
            "total":          total,
            "automatico":     n_auto,
            "dudoso":         n_dud,
            "sin_match":      n_sin,
            "pct_automatico": round(100 * n_auto / max(1, total), 1),
        }

    # Construir tabla pivot comparativa (igual que v1 pero con estructura v2)
    comparativo = _build_comparativo_v2(resultados, materiales_dict)
    comparativa_id = str(uuid.uuid4())

    _guardar_comparativa(
        comparativa_id,
        {"comparativo": comparativo, "proveedores": list(resultados.keys())},
        user_id=user["user_id"],
        # Título legible: "{Obra} — {proveedores} (fecha)"; sin obra, solo proveedores
        titulo=(f"{obra['nombre']} — " if obra else "") +
               f"{', '.join(resultados.keys())} ({datetime.now().strftime('%d/%m/%Y')})"
    )

    # Vincular los documentos procesados a su comparativa (la FK requiere que
    # la fila de comparativas exista: solo se crea para usuarios logueados)
    if sb and presupuestos_creados and user["user_id"] != "anonimo":
        try:
            sb.table("presupuestos").update({"comparativa_id": comparativa_id}) \
              .in_("id", presupuestos_creados).execute()
        except Exception as e:
            print(f"[v2] Error vinculando presupuestos a comparativa: {e}")

    if sb and obra_valida and user["user_id"] != "anonimo":
        try:
            sb.table("comparativas").update({"obra_id": obra_valida}) \
              .eq("id", comparativa_id).execute()
        except Exception as e:
            print(f"[v2] Error vinculando comparativa a obra: {e}")

    _incrementar_uso(user["user_id"], user["usos_hoy"])

    usos_restantes = None
    if user["plan"] == "free" and user["user_id"] != "anonimo":
        usos_restantes = max(0, user["limite"] - user["usos_hoy"] - 1)

    # Config REAL que el usuario eligió al subir cada bloque (no la tabla
    # legacy por nombre de proveedor): es lo que decide si el neto que se
    # muestra es de documento o estimado.
    config_provs = {
        prov: {
            "iva_incluido":  bool((data.get("cfg_aplicada") or {}).get("con_iva", True)),
            "factor_iva":    1.105 if (data.get("cfg_aplicada") or {}).get("con_iva", True) else 1.0,
            "descuento_pct": (data.get("cfg_aplicada") or {}).get("descuento", 0),
        }
        for prov, data in resultados.items()
    }

    return {
        "comparativa_id":   comparativa_id,
        "proveedores":      list(resultados.keys()),
        "resultados":       resultados,
        "comparativo":      comparativo,
        "errores":          errores,
        "plan":             user["plan"],
        "usos_restantes":   usos_restantes,
        "aliases_en_bd":    len(denominaciones),
        "config_proveedores": config_provs,
    }


def _build_comparativo_v2(resultados: dict, materiales_dict: dict) -> list[dict]:
    """Tabla pivot para v2: solo con items automáticos (los de confianza alta)."""
    proveedores = list(resultados.keys())
    por_cod: dict[str, dict] = {}

    for prov, data in resultados.items():
        for m in data.get("automatico", []):
            cod = m["codigo_material"]
            if cod not in por_cod:
                mat = materiales_dict.get(cod, {})
                label = mat.get("denominacion_principal", cod)
                desc  = mat.get("descripcion", "")
                por_cod[cod] = {
                    "cod_int":  cod,
                    "rubro":    mat.get("categoria", ""),
                    "material": f"{label} — {desc}".rstrip(" —"),
                    "unidad":   (mat.get("unidades_posibles") or [{}])[0].get("unidad", "UN"),
                    "precios":  {},
                }
            por_cod[cod]["precios"][prov] = {
                "precio_sin_iva": m["precio_sin_iva"],
                "score":          m["score"],
                "origen":         "v2",
                "cant":           m.get("cant", 1),
            }

    rows = []
    for cod, row in por_cod.items():
        precios_val = {p: row["precios"][p]["precio_sin_iva"] for p in row["precios"]}
        if precios_val:
            mejor_prov = min(precios_val, key=precios_val.get)
            row["mejor_proveedor"] = mejor_prov
            row["cant"] = row["precios"][mejor_prov]["cant"]
            if len(precios_val) > 1:
                row["ahorro"] = round((max(precios_val.values()) - min(precios_val.values())) * row["cant"], 2)
            else:
                row["ahorro"] = 0
        row["en_varios"] = len(row["precios"]) > 1
        rows.append(row)

    rows.sort(key=lambda r: (-int(r["en_varios"]), r["rubro"], r["material"]))
    return rows


# ── /confirmar-v2 ─────────────────────────────────────────────────────────────
@app.post("/confirmar-v2")
async def confirmar_v2(
    req: ConfirmarV2Request,
    authorization: Optional[str] = Header(None),
):
    """
    V2: Guarda aliases confirmados + pendientes + precios históricos.
    - confirmados → material_denominaciones (alias) + precios_historicos
    - sin_match   → materiales_pendientes + precios_historicos (sin codigo_material)
    """
    user = get_user_plan(authorization)
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})

    guardados = {"aliases": 0, "pendientes": 0, "precios": 0}

    # ── Confirmados: alias + precio histórico ──────────────────────────────────
    for item in req.confirmados:
        desc_norm = item.desc_prov.strip().lower()

        # Alias: upsert (puede ya existir, solo sube frecuencia)
        try:
            existing = sb.table("material_denominaciones") \
                         .select("id,frecuencia_encontrada") \
                         .eq("codigo_material", item.codigo_material) \
                         .eq("denominacion", desc_norm) \
                         .execute()

            if existing.data:
                freq = (existing.data[0].get("frecuencia_encontrada") or 1) + 1
                sb.table("material_denominaciones") \
                  .update({"frecuencia_encontrada": freq, "confianza": min(99, 80 + freq)}) \
                  .eq("id", existing.data[0]["id"]) \
                  .execute()
            elif not _desc_es_codigo(_prep_v2(desc_norm)):
                # Solo crear alias NUEVO si tiene una palabra real (no unidades ni
                # números): evita volver a contaminar la base con aliases basura.
                sb.table("material_denominaciones").insert({
                    "codigo_material":      item.codigo_material,
                    "denominacion":         desc_norm,
                    "origen":               f"usuario_{item.proveedor.lower().replace(' ', '_')}",
                    "confianza":            80,
                    "frecuencia_encontrada": 1,
                }).execute()
            guardados["aliases"] += 1
        except Exception as e:
            print(f"[v2] Error guardando alias '{desc_norm}': {e}")

        # Precio histórico
        try:
            sb.table("precios_historicos").insert({
                "proveedor":      item.proveedor,
                "proveedor_id":   _get_proveedor_id(sb, item.proveedor),
                "codigo_material": item.codigo_material,
                "unidad":         item.unidad,
                "precio":         item.precio_sin_iva,
                "cantidad":       int(item.cantidad),
                "precio_raw":     item.precio_raw,
                "unidad_raw":     item.unidad_raw,
                "conversion_aplicada": item.conversion,
                "moneda":         item.moneda or "ARS",
            }).execute()
            guardados["precios"] += 1
        except Exception as e:
            print(f"[v2] Error guardando precio: {e}")

        # Marcar la línea del presupuesto como confirmada por el usuario
        if item.item_id:
            try:
                sb.table("presupuesto_items").update({
                    "estado_match":    "CONFIRMADO",
                    "codigo_material": item.codigo_material,
                    "origen_match":    "usuario",
                }).eq("id", item.item_id).execute()
            except Exception as e:
                print(f"[v2] Error actualizando presupuesto_item {item.item_id}: {e}")

    # ── Sin match: pendientes + precio histórico (sin codigo_material) ─────────
    for item in req.sin_match:
        try:
            res = sb.table("materiales_pendientes").insert({
                "descripcion_original":    item.desc_prov.strip(),
                "descripcion_normalizada": item.desc_prov.strip().lower(),
                "proveedor":              item.proveedor,
                "precio_visto":           item.precio_sin_iva,
                "estado":                 "PENDIENTE",
            }).execute()
            guardados["pendientes"] += 1

            # Precio histórico referenciando el pendiente
            if res.data:
                pendiente_id = res.data[0]["id"]
                sb.table("precios_historicos").insert({
                    "proveedor":      item.proveedor,
                    "proveedor_id":   _get_proveedor_id(sb, item.proveedor),
                    "codigo_pendiente": pendiente_id,
                    "unidad":         item.unidad,
                    "precio":         item.precio_sin_iva,
                }).execute()
                guardados["precios"] += 1

                # Vincular la línea del presupuesto con su pendiente
                if item.item_id:
                    try:
                        sb.table("presupuesto_items").update({
                            "pendiente_id": pendiente_id,
                        }).eq("id", item.item_id).execute()
                    except Exception as e:
                        print(f"[v2] Error vinculando presupuesto_item {item.item_id}: {e}")
        except Exception as e:
            print(f"[v2] Error guardando pendiente '{item.desc_prov}': {e}")

    # Invalidar cache para que el próximo análisis vea los nuevos aliases
    _invalidar_cache_den()

    return {
        "ok": True,
        "guardados": guardados,
        "mensaje": f"{guardados['aliases']} aliases, {guardados['pendientes']} pendientes, {guardados['precios']} precios guardados.",
    }


# ── /vinculo-manual ───────────────────────────────────────────────────────────
@app.post("/vinculo-manual")
async def vinculo_manual(
    req: VinculoManualRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Emparejar terminaciones: guarda vínculos manuales de ítems SIN MATCH
    (griferías, porcelanatos, inodoros de distintas marcas) agrupados en
    "conceptos" comparables por proveedor. NO toca el catálogo global.

    Si recordar=True, siembra terminaciones_recordadas (por-usuario) para
    pre-sugerir el mismo vínculo en próximos análisis del usuario.

    Solo usuarios logueados: los ítems anónimos no tienen item_id estable.
    """
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=401, detail={
            "error": "login_requerido",
            "mensaje": "Emparejar terminaciones necesita una cuenta. Registrate gratis para guardar tus vínculos.",
        })
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})

    guardados = {"conceptos": 0, "items": 0, "recordados": 0}

    for c in req.conceptos:
        # Un concepto necesita al menos 2 ítems para ser una comparación
        items_validos = [it for it in c.items if it.item_id]
        if len(items_validos) < 2:
            continue

        try:
            ins = sb.table("terminaciones_conceptos").insert({
                "user_id":        user["user_id"],
                "comparativa_id": req.comparativa_id,
                "nombre":         (c.nombre or "").strip() or "Sin nombre",
                "unidad":         c.unidad,
                "cantidad":       c.cantidad,
                "origen":         "manual",
            }).execute()
        except Exception as e:
            print(f"[vinculo] Error creando concepto '{c.nombre}': {e}")
            continue
        if not ins.data:
            continue
        concepto_id = ins.data[0]["id"]
        guardados["conceptos"] += 1

        for it in items_validos:
            pid = _get_proveedor_id(sb, it.proveedor)
            try:
                sb.table("terminaciones_concepto_items").insert({
                    "concepto_id":         concepto_id,
                    "presupuesto_item_id": it.item_id,
                    "proveedor_id":        pid,
                }).execute()
                guardados["items"] += 1
            except Exception as e:
                print(f"[vinculo] Error vinculando item {it.item_id}: {e}")

            # Recuerdo por-usuario: upsert manual (sube frecuencia si ya existía)
            if req.recordar:
                texto = (it.desc_prov or "").strip().lower()
                if not texto:
                    continue
                try:
                    ex = sb.table("terminaciones_recordadas") \
                           .select("id,frecuencia") \
                           .eq("user_id", user["user_id"]) \
                           .eq("proveedor_id", pid) \
                           .eq("texto_normalizado", texto) \
                           .execute()
                    if ex.data:
                        sb.table("terminaciones_recordadas").update({
                            "frecuencia":      (ex.data[0].get("frecuencia") or 1) + 1,
                            "concepto_nombre": (c.nombre or "").strip(),
                        }).eq("id", ex.data[0]["id"]).execute()
                    else:
                        sb.table("terminaciones_recordadas").insert({
                            "user_id":           user["user_id"],
                            "proveedor_id":      pid,
                            "texto_normalizado": texto,
                            "concepto_nombre":   (c.nombre or "").strip(),
                        }).execute()
                    guardados["recordados"] += 1
                except Exception as e:
                    print(f"[vinculo] Error recordando '{texto}': {e}")

    return {
        "ok": True,
        "guardados": guardados,
        "mensaje": f"{guardados['conceptos']} conceptos, {guardados['items']} ítems vinculados.",
    }


# ── /admin/pendientes ─────────────────────────────────────────────────────────
@app.get("/admin/pendientes")
async def admin_pendientes(
    authorization: Optional[str] = Header(None),
    estado: str = "PENDIENTE",
    limit: int = 50,
):
    """Lista materiales pendientes de validación. Solo admin."""
    require_admin(authorization)

    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})

    res = sb.table("materiales_pendientes") \
            .select("*") \
            .eq("estado", estado) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

    return {"pendientes": res.data or [], "total": len(res.data or [])}


class ValidarPendienteRequest(BaseModel):
    pendiente_id: str
    accion: str               # "linkear" | "crear" | "rechazar"
    codigo_material: Optional[str] = None   # para "linkear"
    nueva_denominacion: Optional[str] = None  # para "crear" (se agrega a materiales_validados manualmente luego)

@app.post("/admin/validar-pendiente")
async def admin_validar_pendiente(
    req: ValidarPendienteRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Valida un pendiente:
    - linkear: agrega alias en material_denominaciones y marca VALIDADO
    - rechazar: marca RECHAZADO (duplicado o irrelevante)
    - crear: marca para creación manual (queda como VALIDADO sin codigo_material)
    """
    email = require_admin(authorization)
    user = {"user_id": email}  # quién validó, para el campo validado_por
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})

    # Leer pendiente
    res = sb.table("materiales_pendientes").select("*").eq("id", req.pendiente_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail={"error": "no_encontrado"})

    pendiente = res.data

    if req.accion == "linkear":
        if not req.codigo_material:
            raise HTTPException(status_code=400, detail={"error": "codigo_material requerido para linkear"})

        # Agregar alias
        desc_norm = pendiente["descripcion_normalizada"] or pendiente["descripcion_original"].lower()
        try:
            sb.table("material_denominaciones").insert({
                "codigo_material": req.codigo_material,
                "denominacion":    desc_norm,
                "origen":          "admin_validacion",
                "confianza":       95,
                "frecuencia_encontrada": 1,
            }).execute()
        except Exception:
            pass  # ya existe el alias

        # Actualizar precio histórico si existe
        try:
            sb.table("precios_historicos") \
              .update({"codigo_material": req.codigo_material, "codigo_pendiente": None}) \
              .eq("codigo_pendiente", req.pendiente_id) \
              .execute()
        except Exception:
            pass

        sb.table("materiales_pendientes").update({
            "estado":          "VALIDADO",
            "codigo_asignado": req.codigo_material,
            "validado_por":    user["user_id"],
        }).eq("id", req.pendiente_id).execute()

        _invalidar_cache_den()
        return {"ok": True, "accion": "linkeado", "alias_agregado": desc_norm, "codigo": req.codigo_material}

    elif req.accion == "rechazar":
        sb.table("materiales_pendientes").update({
            "estado":      "RECHAZADO",
            "validado_por": user["user_id"],
        }).eq("id", req.pendiente_id).execute()
        return {"ok": True, "accion": "rechazado"}

    elif req.accion == "crear":
        sb.table("materiales_pendientes").update({
            "estado":      "VALIDADO",
            "validado_por": user["user_id"],
        }).eq("id", req.pendiente_id).execute()
        return {"ok": True, "accion": "marcado_para_crear", "descripcion": pendiente["descripcion_original"]}

    raise HTTPException(status_code=400, detail={"error": "accion inválida"})


# ── Dashboard de métricas (admin) ─────────────────────────────────────────────
# Precios de referencia por plan (ARS/mes). El intermedio "basico" se setea al
# definir su precio; advance = 48.000.
PRECIOS_PLAN = {
    "advance": int(os.environ.get("PRECIO_ADVANCE", "48000")),
    "pro":     int(os.environ.get("PRECIO_PRO", "48000")),
    "basico":  int(os.environ.get("PRECIO_BASICO", "19600")),  # plan Inicial (precio de lanzamiento)
}
# Costo estimado por llamada de visión (USD) — Sonnet 5, ~1 imagen.
COSTO_OCR_USD = float(os.environ.get("COSTO_OCR_USD", "0.02"))

_REGIONES = {
    "caba": "CABA", "ciudad autonoma": "CABA", "capital federal": "CABA",
    "buenos aires": "Buenos Aires", "gba": "Buenos Aires",
    "cordoba": "Centro", "santa fe": "Centro", "entre rios": "Centro",
    "mendoza": "Cuyo", "san juan": "Cuyo", "san luis": "Cuyo",
    "jujuy": "NOA", "salta": "NOA", "tucuman": "NOA", "catamarca": "NOA",
    "santiago del estero": "NOA", "la rioja": "NOA",
    "misiones": "NEA", "corrientes": "NEA", "chaco": "NEA", "formosa": "NEA",
    "neuquen": "Patagonia", "rio negro": "Patagonia", "chubut": "Patagonia",
    "santa cruz": "Patagonia", "tierra del fuego": "Patagonia", "la pampa": "Patagonia",
}

def _region(prov: str) -> str:
    import unicodedata
    p = unicodedata.normalize("NFKD", (prov or "").lower().strip())
    p = "".join(c for c in p if not unicodedata.combining(c))
    for clave, region in _REGIONES.items():
        if clave in p:
            return region
    return "Otras / sin dato"


@app.get("/admin/metrics")
def admin_metrics(authorization: Optional[str] = Header(None)):
    """Métricas de negocio del SaaS (solo admin)."""
    require_admin(authorization)
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})
    try:
        resp = sb.rpc("admin_metrics").execute()
        m = resp.data
        if isinstance(m, list):
            m = m[0] if m else {}
        m = m or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "metrics_error", "detalle": str(e)})

    por_plan = m.get("por_plan") or {}
    total = m.get("usuarios_total") or 0
    pagos = sum(por_plan.get(p, 0) for p in ("advance", "pro", "basico"))
    mrr = sum(por_plan.get(p, 0) * PRECIOS_PLAN.get(p, 0) for p in PRECIOS_PLAN)

    # Agrupar provincias en regiones del país
    zonas: dict = {}
    for row in m.get("usuarios_por_provincia") or []:
        r = _region(row.get("prov", ""))
        zonas[r] = zonas.get(r, 0) + (row.get("n") or 0)
    zonas_arr = sorted(
        ({"zona": k, "usuarios": v} for k, v in zonas.items()),
        key=lambda x: -x["usuarios"],
    )

    # Crecimiento acumulado de usuarios
    acum = 0
    crecimiento = []
    for row in m.get("usuarios_por_mes") or []:
        acum += row.get("nuevos") or 0
        crecimiento.append({"mes": row["mes"], "nuevos": row.get("nuevos") or 0, "acumulado": acum})

    ocr_total = m.get("ocr_total") or 0
    return {
        "usuarios": {
            "total": total,
            "por_plan": por_plan,
            "activos": m.get("activos", 0),
            "pagos": pagos,
        },
        "mrr": mrr,
        "arpu": round(mrr / total, 2) if total else 0,
        "conversion_pago_pct": round(100 * pagos / total, 1) if total else 0,
        "comparativas_total": m.get("comparativas_total", 0),
        "presupuestos_total": m.get("presupuestos_total", 0),
        "ahorro_generado": m.get("ahorro_comparativas", 0),
        "crecimiento_usuarios": crecimiento,
        "usuarios_por_zona": zonas_arr,
        "facturacion_por_mes": m.get("facturacion_por_mes") or [],
        "ocr": {
            "llamadas": ocr_total,
            "costo_usd_estimado": round(ocr_total * COSTO_OCR_USD, 2),
            "por_mes": m.get("ocr_por_mes") or [],
        },
        "precios_plan": PRECIOS_PLAN,
    }


# ── Admin: sinónimos ──────────────────────────────────────────────────────────
@app.get("/admin/sinonimos")
async def admin_listar_sinonimos(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})
    res = sb.table("sinonimos").select("*").order("categoria").order("original").execute()
    return {"sinonimos": res.data or [], "total": len(res.data or [])}


class SinonimoRequest(BaseModel):
    original:  str
    canonico:  str
    categoria: Optional[str] = None
    notas:     Optional[str] = None
    activo:    bool = True

@app.post("/admin/sinonimos")
async def admin_upsert_sinonimo(
    req: SinonimoRequest,
    authorization: Optional[str] = Header(None),
):
    require_admin(authorization)
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})
    sb.table("sinonimos").upsert({
        "original":  req.original.upper().strip(),
        "canonico":  req.canonico.upper().strip(),
        "categoria": req.categoria,
        "notas":     req.notas,
        "activo":    req.activo,
        "updated_at": datetime.now().isoformat(),
    }, on_conflict="original").execute()
    _invalidar_cache_den()
    return {"ok": True, "original": req.original.upper(), "canonico": req.canonico.upper()}


# ── Admin: grupos de marcas ────────────────────────────────────────────────────
@app.get("/admin/grupos-marcas")
async def admin_listar_grupos_marcas(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})
    res = sb.table("grupos_marcas").select("*").order("categoria").order("grupo").execute()
    return {"grupos": res.data or [], "total": len(res.data or [])}


class GrupoMarcaRequest(BaseModel):
    marca:    str
    grupo:    str
    categoria: Optional[str] = None
    notas:    Optional[str] = None
    activo:   bool = True

@app.post("/admin/grupos-marcas")
async def admin_upsert_grupo_marca(
    req: GrupoMarcaRequest,
    authorization: Optional[str] = Header(None),
):
    require_admin(authorization)
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})
    sb.table("grupos_marcas").upsert({
        "marca":     req.marca.upper().strip(),
        "grupo":     req.grupo.strip(),
        "categoria": req.categoria,
        "notas":     req.notas,
        "activo":    req.activo,
    }, on_conflict="marca").execute()
    _invalidar_cache_den()
    return {"ok": True, "marca": req.marca.upper(), "grupo": req.grupo}


# ── Obras (plan alto) ──────────────────────────────────────────────────────────
# Agrupan presupuestos y comparativas por proyecto. La localidad/provincia de la
# obra es además el dato geográfico que alimenta los precios por zona.

def _plan_permite_obras(plan: str) -> bool:
    return plan in ("advance", "pro")


@app.get("/obras")
async def listar_obras(authorization: Optional[str] = Header(None)):
    user = get_user_plan(authorization)
    sb = get_supabase()
    if user["user_id"] == "anonimo" or not sb:
        return {"obras": [], "habilitado": False}
    try:
        res = sb.table("obras").select("id,nombre,localidad,provincia,created_at") \
                .eq("user_id", user["user_id"]).order("created_at", desc=True).execute()
        return {"obras": res.data or [], "habilitado": _plan_permite_obras(user["plan"])}
    except Exception as e:
        print(f"[obras] Error listando: {e}")
        return {"obras": [], "habilitado": _plan_permite_obras(user["plan"])}


class ObraRequest(BaseModel):
    nombre: str
    localidad: Optional[str] = None
    provincia: Optional[str] = None


@app.post("/obras")
async def crear_obra(req: ObraRequest, authorization: Optional[str] = Header(None)):
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=401, detail={"error": "login_requerido"})
    if not _plan_permite_obras(user["plan"]):
        raise HTTPException(status_code=403, detail={
            "error": "plan_requerido",
            "mensaje": "Las obras están disponibles en el plan Advance."})
    if not (req.nombre or "").strip():
        raise HTTPException(status_code=400, detail={"error": "nombre_requerido"})
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})
    res = sb.table("obras").insert({
        "user_id":   user["user_id"],
        "nombre":    req.nombre.strip(),
        "localidad": (req.localidad or "").strip() or None,
        "provincia": (req.provincia or "").strip() or None,
    }).execute()
    return {"obra": res.data[0]}


def _obra_del_usuario(sb, obra_id: Optional[str], user_id: str) -> Optional[dict]:
    """Valida que la obra exista y sea del usuario; devuelve {id, nombre} o None."""
    if not obra_id or user_id == "anonimo" or not sb:
        return None
    try:
        res = sb.table("obras").select("id,nombre").eq("id", obra_id).eq("user_id", user_id).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


# ── Mis Presupuestos ───────────────────────────────────────────────────────────
# Cada documento analizado (PDF/foto/planilla) queda registrado en `presupuestos`
# con sus líneas en `presupuesto_items`. Estos endpoints los exponen read-only
# para que el usuario pueda re-ver lo que subió sin volver a cargarlo.

@app.get("/mis-presupuestos")
async def listar_mis_presupuestos(authorization: Optional[str] = Header(None)):
    """Documentos procesados del usuario, más nuevos primero. Anónimos: vacío."""
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        return {"presupuestos": []}
    sb = get_supabase()
    if not sb:
        return {"presupuestos": []}
    try:
        res = sb.table("presupuestos").select(
            "id,proveedor_detectado,archivo,estado,created_at,obra_id,incluye_iva,descuento_pct"
        ).eq("user_id", user["user_id"]).order("created_at", desc=True).limit(100).execute()
        pres = res.data or []
        # Nombre de la obra de cada presupuesto (para agrupar en el frontend)
        obras_map: dict[str, dict] = {}
        obra_ids = sorted({p["obra_id"] for p in pres if p.get("obra_id")})
        if obra_ids:
            try:
                res_obras = sb.table("obras").select("id,nombre,localidad,provincia").in_("id", obra_ids).execute()
                obras_map = {o["id"]: o for o in (res_obras.data or [])}
            except Exception:
                pass
        counts: dict[str, int] = {}
        totales: dict[str, float] = {}
        ids = [p["id"] for p in pres]
        if ids:
            res_items = sb.table("presupuesto_items") \
                          .select("presupuesto_id,precio,cantidad") \
                          .in_("presupuesto_id", ids).execute()
            for it in (res_items.data or []):
                pid = it["presupuesto_id"]
                counts[pid] = counts.get(pid, 0) + 1
                try:
                    totales[pid] = totales.get(pid, 0.0) + float(it.get("precio") or 0) * float(it.get("cantidad") or 1)
                except (TypeError, ValueError):
                    pass
        return {"presupuestos": [{
            "id":           p["id"],
            "proveedor":    p.get("proveedor_detectado") or "—",
            "archivo":      p.get("archivo") or "",
            "estado":       p.get("estado") or "",
            "fecha":        p.get("created_at"),
            "n_items":      counts.get(p["id"], 0),
            "total_sin_iva": round(totales.get(p["id"], 0.0), 2),
            "obra":         obras_map.get(p.get("obra_id") or "", None),
            "con_iva":      bool(p.get("incluye_iva", True)),
            "descuento":    float(p.get("descuento_pct") or 0),
        } for p in pres]}
    except Exception as e:
        print(f"[mis-presupuestos] Error listando: {e}")
        return {"presupuestos": []}


@app.get("/mis-presupuestos/{presupuesto_id}")
async def detalle_mi_presupuesto(presupuesto_id: str, authorization: Optional[str] = Header(None)):
    """Líneas de un presupuesto del usuario, con el material matcheado."""
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=401, detail={"error": "login_requerido"})
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})

    res = sb.table("presupuestos").select("id,proveedor_detectado,archivo,estado,created_at") \
            .eq("id", presupuesto_id).eq("user_id", user["user_id"]).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail={"error": "no_encontrado"})
    p = res.data[0]

    res_items = sb.table("presupuesto_items").select(
        "texto_original,cantidad,precio,codigo_material,score_match,estado_match"
    ).eq("presupuesto_id", presupuesto_id).execute()
    items = res_items.data or []

    # Enriquecer con el nombre del material matcheado
    codigos = sorted({it["codigo_material"] for it in items if it.get("codigo_material")})
    nombres: dict[str, str] = {}
    if codigos:
        res_mat = sb.table("materiales_validados").select("codigo,denominacion_principal,descripcion") \
                    .in_("codigo", codigos).execute()
        for m in (res_mat.data or []):
            nombres[m["codigo"]] = f"{m['denominacion_principal']} — {m.get('descripcion') or ''}".strip(" —")

    return {
        "presupuesto": {
            "id":        p["id"],
            "proveedor": p.get("proveedor_detectado") or "—",
            "archivo":   p.get("archivo") or "",
            "estado":    p.get("estado") or "",
            "fecha":     p.get("created_at"),
        },
        "items": [{
            "texto":    it.get("texto_original") or "",
            "cantidad": it.get("cantidad"),
            "precio":   it.get("precio"),
            "codigo":   it.get("codigo_material"),
            "material": nombres.get(it.get("codigo_material") or "", ""),
            "score":    it.get("score_match"),
            "estado":   it.get("estado_match"),
        } for it in items],
    }


@app.delete("/mis-presupuestos/{presupuesto_id}")
async def eliminar_mi_presupuesto(presupuesto_id: str, authorization: Optional[str] = Header(None)):
    """Elimina un presupuesto guardado y sus líneas. Solo el propietario."""
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=401, detail={"error": "login_requerido"})
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})
    res = sb.table("presupuestos").select("id").eq("id", presupuesto_id) \
            .eq("user_id", user["user_id"]).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail={"error": "no_encontrado"})
    sb.table("presupuesto_items").delete().eq("presupuesto_id", presupuesto_id).execute()
    sb.table("presupuestos").delete().eq("id", presupuesto_id).execute()
    return {"ok": True}


class CompararGuardadosRequest(BaseModel):
    presupuesto_ids: list[str]
    # {presupuesto_id: {"con_iva": bool, "descuento": float}} — si no viene,
    # se usa la config RECORDADA del análisis original
    overrides: dict[str, dict] = {}


@app.post("/comparar-guardados")
def comparar_guardados(req: CompararGuardadosRequest, authorization: Optional[str] = Header(None)):
    """Re-arma una comparativa desde presupuestos YA procesados, sin re-subir
    archivos. Usa la config recordada (IVA/descuento) de cada documento — con
    override opcional — y RE-MATCHEA los textos con el motor actual (aprovecha
    los aliases aprendidos desde el análisis original).

    Nota: los precios guardados ya están normalizados (unidad convertida), por
    eso acá NO se vuelve a aplicar conversión de unidades."""
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=401, detail={"error": "login_requerido"})
    if not req.presupuesto_ids or len(req.presupuesto_ids) > 20:
        raise HTTPException(status_code=400, detail={"error": "seleccion_invalida"})
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail={"error": "db_no_disponible"})

    denominaciones = _get_denominaciones()
    res_m = sb.table("materiales_validados") \
              .select("codigo,categoria,denominacion_principal,descripcion,unidades_posibles").execute()
    materiales_dict = {m["codigo"]: m for m in (res_m.data or [])}

    res_p = sb.table("presupuestos").select("*").in_("id", req.presupuesto_ids) \
              .eq("user_id", user["user_id"]).execute()
    pres = res_p.data or []
    if not pres:
        raise HTTPException(status_code=404, detail={"error": "no_encontrado"})

    obra_ids = {p.get("obra_id") for p in pres if p.get("obra_id")}
    obra_id_comun = obra_ids.pop() if len(obra_ids) == 1 else None

    resultados: dict[str, dict] = {}
    for p in pres:
        ov = req.overrides.get(p["id"]) or {}
        con_iva_orig = bool(p.get("incluye_iva", True))
        desc_orig    = float(p.get("descuento_pct") or 0)
        fac_orig     = 1.105 if con_iva_orig else 1.0
        con_iva_new  = bool(ov.get("con_iva", con_iva_orig))
        desc_new     = float(ov.get("descuento", desc_orig))
        fac_new      = 1.105 if con_iva_new else 1.0

        res_i = sb.table("presupuesto_items").select("texto_original,cantidad,precio") \
                  .eq("presupuesto_id", p["id"]).execute()
        proveedor = p.get("proveedor_detectado") or "PROVEEDOR"
        automatico, dudoso, sin_match = [], [], []

        for it in (res_i.data or []):
            desc_txt = (it.get("texto_original") or "").strip()
            precio_guardado = float(it.get("precio") or 0)
            if not desc_txt or precio_guardado <= 0:
                continue
            # Reconstruir el precio bruto del documento (deshacer la config
            # original) y re-aplicar la config nueva
            pu_bruto = precio_guardado * fac_orig
            if 0 < desc_orig < 100:
                pu_bruto = pu_bruto / (1 - desc_orig / 100)
            precio = round(pu_bruto / fac_new * (1 - desc_new / 100), 2)
            cant = float(it.get("cantidad") or 1)

            matches = _match_v2(desc_txt, denominaciones, top_n=3)
            base = {
                "desc_prov": desc_txt, "cod_prov": "",
                "precio_sin_iva": precio, "precio_con_iva": round(pu_bruto, 2),
                "cant": cant, "unidad": "UN",
            }
            if not matches or matches[0]["nivel"] == "sin_match":
                sin_match.append(base)
                continue
            mejor = matches[0]
            mat = materiales_dict.get(mejor["codigo_material"], {})
            alternativas = []
            vistos = {mejor["codigo_material"]}
            for m in matches[1:]:
                if m["codigo_material"] in vistos:
                    continue
                vistos.add(m["codigo_material"])
                mat_alt = materiales_dict.get(m["codigo_material"], {})
                alternativas.append({
                    "codigo_material": m["codigo_material"],
                    "denominacion":    mat_alt.get("denominacion_principal", m["denominacion_matcheada"]),
                    "descripcion":     mat_alt.get("descripcion", ""),
                    "score":           m["score"],
                })
            entry = {
                **base,
                "codigo_material":        mejor["codigo_material"],
                "denominacion_matcheada": mejor["denominacion_matcheada"],
                "score":                  mejor["score"],
                "nivel":                  mejor["nivel"],
                "categoria":              mat.get("categoria", ""),
                "denominacion_principal": mat.get("denominacion_principal", ""),
                "descripcion":            mat.get("descripcion", ""),
                "alternativas":           alternativas,
            }
            (automatico if mejor["nivel"] == "automatico" else dudoso).append(entry)

        total_n = len(automatico) + len(dudoso) + len(sin_match)
        acc = resultados.get(proveedor)
        if acc is None:
            resultados[proveedor] = {
                "automatico": automatico, "dudoso": dudoso, "sin_match": sin_match,
                "extraccion": {"metodo": "guardado", "n_items": total_n},
                "n_items_extraidos": total_n,
                "cfg_aplicada": {"con_iva": con_iva_new, "descuento": desc_new},
            }
        else:
            acc["automatico"].extend(automatico)
            acc["dudoso"].extend(dudoso)
            acc["sin_match"].extend(sin_match)
            acc["n_items_extraidos"] += total_n

    if not resultados:
        raise HTTPException(status_code=422, detail={"error": "sin_resultados"})

    for data in resultados.values():
        n_auto, n_dud, n_sin = len(data["automatico"]), len(data["dudoso"]), len(data["sin_match"])
        total = n_auto + n_dud + n_sin
        data["stats"] = {"total": total, "automatico": n_auto, "dudoso": n_dud,
                         "sin_match": n_sin, "pct_automatico": round(100 * n_auto / max(1, total), 1)}

    comparativo = _build_comparativo_v2(resultados, materiales_dict)
    comparativa_id = str(uuid.uuid4())
    obra_nombre = None
    if obra_id_comun:
        try:
            ro = sb.table("obras").select("nombre").eq("id", obra_id_comun).limit(1).execute()
            obra_nombre = ro.data[0]["nombre"] if ro.data else None
        except Exception:
            pass
    _guardar_comparativa(
        comparativa_id,
        {"comparativo": comparativo, "proveedores": list(resultados.keys())},
        user_id=user["user_id"],
        titulo=(f"{obra_nombre} — " if obra_nombre else "") +
               f"{', '.join(resultados.keys())} ({datetime.now().strftime('%d/%m/%Y')})",
    )
    if obra_id_comun:
        try:
            sb.table("comparativas").update({"obra_id": obra_id_comun}).eq("id", comparativa_id).execute()
        except Exception:
            pass

    config_provs = {
        prov: {
            "iva_incluido":  data["cfg_aplicada"]["con_iva"],
            "factor_iva":    1.105 if data["cfg_aplicada"]["con_iva"] else 1.0,
            "descuento_pct": data["cfg_aplicada"]["descuento"],
        }
        for prov, data in resultados.items()
    }
    return {
        "comparativa_id":     comparativa_id,
        "proveedores":        list(resultados.keys()),
        "resultados":         resultados,
        "comparativo":        comparativo,
        "errores":            [],
        "plan":               user["plan"],
        "usos_restantes":     None,
        "aliases_en_bd":      len(denominaciones),
        "config_proveedores": config_provs,
    }


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    master = get_master()
    den = _get_denominaciones()

    # Diagnóstico de OCR sin exponer secretos: motor configurado, largo de la
    # key (post-sanitización) y huella sha256 corta para comparar con la real.
    import hashlib
    from extraer_imagen import ocr_disponible, _api_key_limpia
    key = _api_key_limpia()
    ocr = {
        "motor": ocr_disponible(),
        "key_len": len(key),
        "key_hash": hashlib.sha256(key.encode()).hexdigest()[:8] if key else None,
    }
    try:
        from sheets import sheets_disponible
        sheets_ok = sheets_disponible()
    except Exception:
        sheets_ok = False

    return {
        "status": "ok",
        "master_items": len(master),
        "aliases_v2": len(den),
        "sinonimos_bd": len(_sin_extra),
        "grupos_marcas_bd": len(_grupos_extra),
        "ocr": ocr,
        "sheets_export": sheets_ok,
    }
