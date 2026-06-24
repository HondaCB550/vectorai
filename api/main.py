"""
API FastAPI — Motor de análisis de presupuestos de construcción
Endpoints: /analizar, /confirmar, /sheets
"""
import sys
import json
import os
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
from extraer_pdf_texto import extraer               # noqa: E402
from matching import matchear_item                  # noqa: E402

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

def get_supabase() -> SupabaseClient | None:
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return None

def get_user_plan(authorization: Optional[str]) -> dict:
    """Devuelve {'user_id': ..., 'plan': 'free'|'advance', 'usos_hoy': N, 'limite': N}.

    Sin token → anónimo, plan free, límite 2 análisis/día (no trackeado).
    Con token → verifica JWT, consulta perfiles, resetea contador si es nuevo día.
    """
    if not authorization:
        return {"user_id": "anonimo", "plan": "free", "usos_hoy": 0, "limite": 2}

    token = authorization.removeprefix("Bearer ").strip()
    sb = get_supabase()
    if not sb:
        return {"user_id": "anonimo", "plan": "free", "usos_hoy": 0, "limite": 2}

    try:
        user_resp = sb.auth.get_user(token)
        user_id = user_resp.user.id if user_resp.user else None
        if not user_id:
            return {"user_id": "anonimo", "plan": "free", "usos_hoy": 0, "limite": 2}

        perfil = sb.table("perfiles").select("plan,usos_hoy,fecha_usos").eq("id", user_id).single().execute()
        if not perfil.data:
            # Crear perfil si el trigger no lo hizo
            sb.table("perfiles").insert({"id": user_id, "plan": "free", "usos_hoy": 0}).execute()
            return {"user_id": user_id, "plan": "free", "usos_hoy": 0, "limite": 2}

        plan  = perfil.data.get("plan", "free")
        usos  = perfil.data.get("usos_hoy", 0)
        fecha = str(perfil.data.get("fecha_usos") or "")
        hoy   = datetime.now().strftime("%Y-%m-%d")

        # Resetear contador si es un nuevo día
        if fecha != hoy:
            sb.table("perfiles").update({"usos_hoy": 0, "fecha_usos": hoy}).eq("id", user_id).execute()
            usos = 0

        limite = 999 if plan == "advance" else 2
        return {"user_id": user_id, "plan": plan, "usos_hoy": usos, "limite": limite}
    except Exception as e:
        print(f"get_user_plan error: {e}")
        return {"user_id": "anonimo", "plan": "free", "usos_hoy": 0, "limite": 2}


def _incrementar_uso(user_id: str, usos_actuales: int):
    """Incrementa usos_hoy en perfiles para el usuario logueado."""
    if user_id == "anonimo":
        return
    sb = get_supabase()
    if not sb:
        return
    try:
        hoy = datetime.now().strftime("%Y-%m-%d")
        sb.table("perfiles").update({
            "usos_hoy": usos_actuales + 1,
            "fecha_usos": hoy,
        }).eq("id", user_id).execute()
    except Exception as e:
        print(f"_incrementar_uso error: {e}")


# ── App FastAPI ───────────────────────────────────────────────────────────────
app = FastAPI(title="VectorAI API", version="0.1.0")

from whatsapp import router as whatsapp_router
app.include_router(whatsapp_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://vectorai.com.ar", "https://www.vectorai.com.ar"],
    allow_origin_regex=r"https://vectorai.*\.vercel\.app",
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

def _calcular_ahorro_total(comparativo: list) -> float:
    """Suma todos los ahorros de la comparativa."""
    return round(sum(r.get("ahorro", 0) for r in comparativo), 2)

def _guardar_comparativa(comparativa_id: str, data: dict, user_id: str = "anonimo", titulo: str = ""):
    """Persiste en Supabase; fallback a memoria."""
    _comparativas_cache[comparativa_id] = data
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
    """Lee de memoria primero, luego Supabase."""
    if comparativa_id in _comparativas_cache:
        return _comparativas_cache[comparativa_id]
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("comparativas").select("comparativo,proveedores").eq("id", comparativa_id).single().execute()
            if res.data:
                data = {"comparativo": res.data["comparativo"], "proveedores": res.data["proveedores"]}
                _comparativas_cache[comparativa_id] = data
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

    # Sin límites durante el período de lanzamiento

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
            "id,titulo,proveedores,n_items,n_comunes,ahorro_total,created_at"
        ).eq("user_id", user["user_id"]).order("created_at", desc=True).execute()

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
    titulo = req.titulo or f"VectorAI — Comparativa {fecha}"
    comparativo = _aplicar_filtros(cached["comparativo"], req)
    pdf_bytes = generar_pdf_comparativo(
        comparativo=comparativo,
        proveedores=cached["proveedores"],
        titulo=titulo,
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
    titulo = req.titulo or f"VectorAI — Comparativa {fecha}"
    comparativo = _aplicar_filtros(cached["comparativo"], req)
    jpg_bytes = generar_imagen_comparativo(
        comparativo=comparativo,
        proveedores=cached["proveedores"],
        titulo=titulo,
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

@app.post("/mp/suscripcion")
async def crear_suscripcion(req: MPSuscripcionRequest):
    """
    Crea una suscripción recurrente en MercadoPago y devuelve la URL de pago.
    Usa Preapproval (débito automático mensual).
    """
    if not MP_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail={"error": "mp_no_configurado"})

    import mercadopago
    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

    preapproval_data = {
        "preapproval_plan_id": None,  # sin plan predefinido → ad-hoc
        "reason": "VectorAI Plan Advance — comparador de presupuestos",
        "external_reference": req.user_id,
        "payer_email": req.email,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": 48000,
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
    # Verificar firma si está configurada
    if MP_WEBHOOK_SECRET:
        import hmac, hashlib
        sig_header = request.headers.get("x-signature", "")
        raw_body   = await request.body()
        expected   = hmac.new(MP_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
        received   = sig_header.split("v1=")[-1]
        if not hmac.compare_digest(expected, received):
            raise HTTPException(status_code=401, detail="Firma inválida")
        body = json.loads(raw_body)
    else:
        body = await request.json()
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
    user_id = preapproval.get("external_reference", "")

    if not user_id:
        return {"ok": True}

    sb = get_supabase()
    if not sb:
        return {"ok": True}

    if estado == "authorized":
        sb.table("perfiles").update({"plan": "advance"}).eq("id", user_id).execute()
        print(f"Plan Advance activado: {user_id}")
    elif estado in ("cancelled", "paused"):
        sb.table("perfiles").update({"plan": "free"}).eq("id", user_id).execute()
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


def _prep_v2(s: str) -> str:
    """Normaliza + aplica sinónimos → lowercase. Usado en ambos lados del match."""
    return aplicar_sinonimos(normalize(s)).lower()


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

    _knowledge_cache_ts = ahora
    print(f"[v2] Knowledge cache: {len(_sin_extra)} sinónimos BD, {len(_grupos_extra)} grupos marcas")


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
                    .select("codigo_material,denominacion,confianza,frecuencia_encontrada") \
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
    for texto_match, score, idx in resultados:
        den = denominaciones[idx]
        # Bonus si comparten marca del mismo grupo equivalente
        if _mismo_grupo_v2(texto, den["denominacion"]):
            score = min(100, score + 6)
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

    # Ordenar por score desc y devolver top_n
    salida.sort(key=lambda x: -x["score"])
    return salida[:top_n]


# ── Modelos V2 ────────────────────────────────────────────────────────────────
class ConfirmarItemV2(BaseModel):
    desc_prov: str
    proveedor: str
    codigo_material: str      # confirmado por usuario (puede ser el sugerido u otro)
    precio_sin_iva: float
    unidad: str = "UN"
    cantidad: float = 1.0

class PendienteItem(BaseModel):
    desc_prov: str
    proveedor: str
    precio_sin_iva: float
    unidad: str = "UN"

class ConfirmarV2Request(BaseModel):
    comparativa_id: str
    confirmados: list[ConfirmarItemV2]
    sin_match: list[PendienteItem] = []


# ── /analizar-v2 ──────────────────────────────────────────────────────────────
from fastapi import Form as FastAPIForm

@app.post("/analizar-v2")
async def analizar_v2(
    files: list[UploadFile] = File(...),
    file_configs: Optional[str] = FastAPIForm(default=None),
    authorization: Optional[str] = Header(None),
):
    """
    V2: Matchea texto de PDFs contra material_denominaciones en Supabase.
    file_configs: JSON array con {con_iva, descuento} por archivo (mismo orden que files).
    Devuelve 3 grupos por proveedor: automatico / dudoso / sin_match.
    """
    user = get_user_plan(authorization)

    # Parsear config por archivo (override de IVA y descuento)
    cfgs: list[dict] = []
    if file_configs:
        try:
            cfgs = json.loads(file_configs)
        except Exception:
            cfgs = []

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

    for file_idx, f in enumerate(files):
        content = await f.read()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            proveedor = detectar_proveedor(f.filename or "") or Path(f.filename or "archivo").stem.upper()
            resultado = extraer(tmp_path)
            items = resultado.get("items", [])
            automatico, dudoso, sin_match = [], [], []

            # Config por archivo: override explícito del usuario, o default del config
            cfg_archivo = cfgs[file_idx] if file_idx < len(cfgs) else {}
            if cfg_archivo:
                # El usuario especificó explícitamente IVA y descuento para este archivo
                fac_archivo  = 1.105 if cfg_archivo.get("con_iva", True) else 1.0
                desc_archivo = float(cfg_archivo.get("descuento", 0))
                def precio_archivo(pu: float) -> float:
                    return round(pu / fac_archivo * (1 - desc_archivo / 100), 2)
            else:
                # Usar la config del proveedor desde configuracion.json
                def precio_archivo(pu: float) -> float:
                    return precio_neto(pu, proveedor)

            for item in items:
                desc = (item.get("desc") or "").strip()
                pu   = float(item.get("pu") or 0)
                if not desc or pu <= 0:
                    continue

                precio = precio_archivo(pu)
                cant   = float(item.get("cant") or 1)

                matches = _match_v2(desc, denominaciones, top_n=3)

                base = {
                    "desc_prov":     desc,
                    "cod_prov":      str(item.get("cod") or "").strip(),
                    "precio_sin_iva": precio,
                    "precio_con_iva": round(pu, 2),
                    "cant":          cant,
                }

                if not matches or matches[0]["nivel"] == "sin_match":
                    sin_match.append(base)
                    continue

                mejor = matches[0]
                mat   = materiales_dict.get(mejor["codigo_material"], {})

                entry = {
                    **base,
                    "codigo_material":       mejor["codigo_material"],
                    "denominacion_matcheada": mejor["denominacion_matcheada"],
                    "score":                 mejor["score"],
                    "nivel":                 mejor["nivel"],
                    "categoria":             mat.get("categoria", ""),
                    "denominacion_principal": mat.get("denominacion_principal", ""),
                    "descripcion":           mat.get("descripcion", ""),
                    "alternativas": [
                        {
                            "codigo_material": m["codigo_material"],
                            "denominacion":    materiales_dict.get(m["codigo_material"], {}).get("denominacion_principal", m["denominacion_matcheada"]),
                            "score":           m["score"],
                        }
                        for m in matches[1:]
                    ],
                }

                if mejor["nivel"] == "automatico":
                    automatico.append(entry)
                else:
                    dudoso.append(entry)

            resultados[proveedor] = {
                "automatico": automatico,
                "dudoso":     dudoso,
                "sin_match":  sin_match,
                "stats": {
                    "total":          len(automatico) + len(dudoso) + len(sin_match),
                    "automatico":     len(automatico),
                    "dudoso":         len(dudoso),
                    "sin_match":      len(sin_match),
                    "pct_automatico": round(
                        100 * len(automatico) / max(1, len(automatico) + len(dudoso) + len(sin_match)), 1
                    ),
                },
                "iva_detectado":      resultado.get("iva_detectado"),
                "metodo_extraccion":  resultado.get("metodo_extraccion", "desconocido"),
                "n_items_extraidos":  resultado.get("n_items", 0),
                "cfg_aplicada": {
                    "con_iva":   cfg_archivo.get("con_iva", True) if cfg_archivo else (factor_iva(proveedor) != 1.0),
                    "descuento": cfg_archivo.get("descuento", 0) if cfg_archivo else descuento_proveedor(proveedor),
                },
            }

        except Exception as e:
            errores.append({"archivo": f.filename, "error": str(e)})
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if not resultados:
        raise HTTPException(status_code=422, detail={"error": "sin_resultados", "errores": errores})

    # Construir tabla pivot comparativa (igual que v1 pero con estructura v2)
    comparativo = _build_comparativo_v2(resultados, materiales_dict)
    comparativa_id = str(uuid.uuid4())

    _guardar_comparativa(
        comparativa_id,
        {"comparativo": comparativo, "proveedores": list(resultados.keys())},
        user_id=user["user_id"],
        titulo=f"Análisis v2 — {', '.join(resultados.keys())} ({datetime.now().strftime('%d/%m/%Y')})"
    )

    _incrementar_uso(user["user_id"], user["usos_hoy"])

    usos_restantes = None
    if user["plan"] == "free" and user["user_id"] != "anonimo":
        usos_restantes = max(0, user["limite"] - user["usos_hoy"] - 1)

    config_provs = {prov: config_proveedor(prov) for prov in resultados}

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
            else:
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
                "codigo_material": item.codigo_material,
                "unidad":         item.unidad,
                "precio":         item.precio_sin_iva,
                "cantidad":       int(item.cantidad),
            }).execute()
            guardados["precios"] += 1
        except Exception as e:
            print(f"[v2] Error guardando precio: {e}")

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
                    "codigo_pendiente": pendiente_id,
                    "unidad":         item.unidad,
                    "precio":         item.precio_sin_iva,
                }).execute()
                guardados["precios"] += 1
        except Exception as e:
            print(f"[v2] Error guardando pendiente '{item.desc_prov}': {e}")

    # Invalidar cache para que el próximo análisis vea los nuevos aliases
    _invalidar_cache_den()

    return {
        "ok": True,
        "guardados": guardados,
        "mensaje": f"{guardados['aliases']} aliases, {guardados['pendientes']} pendientes, {guardados['precios']} precios guardados.",
    }


# ── /admin/pendientes ─────────────────────────────────────────────────────────
@app.get("/admin/pendientes")
async def admin_pendientes(
    authorization: Optional[str] = Header(None),
    estado: str = "PENDIENTE",
    limit: int = 50,
):
    """Lista materiales pendientes de validación. Solo admin."""
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})

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
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
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


# ── Admin: sinónimos ──────────────────────────────────────────────────────────
@app.get("/admin/sinonimos")
async def admin_listar_sinonimos(authorization: Optional[str] = Header(None)):
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
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
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
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
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
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
    user = get_user_plan(authorization)
    if user["user_id"] == "anonimo":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
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


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    master = get_master()
    den = _get_denominaciones()
    return {
        "status": "ok",
        "master_items": len(master),
        "aliases_v2": len(den),
        "sinonimos_bd": len(_sin_extra),
        "grupos_marcas_bd": len(_grupos_extra),
    }
