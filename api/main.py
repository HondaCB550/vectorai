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


# ── Supabase ──────────────────────────────────────────────────────────────────
# Validación de token: el frontend envía el JWT de Supabase en Authorization
# La API verifica el plan del usuario para aplicar límites freemium.
# En producción usar supabase-py para verificar el JWT.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
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

            fac = factor_iva(proveedor)
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
                    sin_match.append({"cod_prov": cod, "desc_prov": desc, "precio": round(pu / fac, 2)})
                    continue

                score, mat, origen = top[0]
                accion = "OK" if score >= 75 else ("REVISAR" if score >= 60 else "SIN MATCH")

                entry = {
                    "cod_prov":       cod,
                    "desc_prov":      desc,
                    "cant":           float(item.get("cant") or 1),
                    "precio_con_iva": pu,
                    "precio_sin_iva": round(pu / fac, 2),
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
    xlsx_bytes = generar_excel_comparativo(
        comparativo=comparativo,
        proveedores=cached["proveedores"],
        titulo=titulo,
    )
    filename = f"VectorAI_Comparativa_{fecha}.xlsx"
    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _aplicar_filtros(comparativo: list, req: SheetsRequest) -> list:
    rows = comparativo
    if req.solo_comunes:
        rows = [r for r in rows if r.get("en_varios")]
    if req.filtro_rubro and req.filtro_rubro != "Todos":
        rows = [r for r in rows if r.get("rubro") == req.filtro_rubro]
    return rows


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


@app.post("/mp/webhook")
async def mp_webhook(request: Request):
    """
    Webhook de MercadoPago. Cuando una suscripción se activa o renueva,
    actualiza perfiles.plan = 'advance'.
    """
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


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    master = get_master()
    return {"status": "ok", "master_items": len(master)}
