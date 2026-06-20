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

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from io import BytesIO
from pydantic import BaseModel

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
    """Equivalencias aprendidas de decisiones_usuario.json + cargas_realizadas.json."""
    global _equiv_cache
    if _equiv_cache is None:
        _equiv_cache = {}
        # Fuente 1: decisiones confirmadas en borrador
        if DECISIONES_JSON.exists():
            with open(DECISIONES_JSON, encoding="utf-8") as f:
                for d in json.load(f):
                    dec = d.get("decision", "")
                    if dec == "CARGAR":
                        cod = d.get("cod_correcto") or d.get("cod_propuesto")
                    elif dec == "CAMBIAR":
                        cod = d.get("cod_correcto")  # solo si el usuario puso código correcto
                    else:
                        cod = None
                    desc = (d.get("desc_prov") or "").strip()
                    if desc and cod:
                        _equiv_cache[desc] = cod
        # Fuente 2: cargas efectivamente realizadas al Excel
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

def get_user_plan(authorization: Optional[str]) -> dict:
    """Devuelve {'user_id': ..., 'plan': 'free'|'basico', 'usos_hoy': N}.

    Sin token → plan free (permite probar sin login).
    TODO: verificar JWT con Supabase en producción.
    """
    if not authorization:
        return {"user_id": "anonimo", "plan": "free", "usos_hoy": 0, "limite": 2}
    # TODO: verificar JWT con supabase-py y consultar tabla perfiles
    return {"user_id": "demo", "plan": "basico", "usos_hoy": 0, "limite": 999}


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


# Cache en memoria de comparativas (hasta Supabase)
_comparativas_cache: dict[str, dict] = {}


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

    # Límite freemium
    if user["plan"] == "free" and len(files) > 2:
        raise HTTPException(
            status_code=402,
            detail={"error": "plan_limit", "mensaje": "El plan gratuito permite máximo 2 PDFs (uno por proveedor).", "upgrade": True}
        )

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

    # Cache en memoria para /sheets (TODO: persistir en Supabase)
    _comparativas_cache[comparativa_id] = {
        "comparativo": comparativa,
        "proveedores": list(resultados.keys()),
    }

    return {
        "comparativa_id": comparativa_id,
        "proveedores": list(resultados.keys()),
        "resultados": resultados,
        "comparativo": comparativa,
        "errores": errores,
        "plan": user["plan"],
    }


def _build_comparativo(resultados: dict, master: list) -> list[dict]:
    """Tabla comparativa: filas = material, columnas = proveedor."""
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
            # Guardar la mayor cantidad vista (para calcular ahorro total)
            cant_actual = por_cod[cod].get("cant", 1)
            por_cod[cod]["cant"] = max(cant_actual, m.get("cant", 1))

    # Calcular mejor precio
    rows = []
    for cod, row in por_cod.items():
        precios_val = {p: row["precios"][p]["precio_sin_iva"] for p in row["precios"]}
        cant = row.get("cant", 1)
        if precios_val:
            row["mejor_proveedor"] = min(precios_val, key=precios_val.get)
            if len(precios_val) > 1:
                row["ahorro"] = round((max(precios_val.values()) - min(precios_val.values())) * cant, 2)
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

    cached = _comparativas_cache.get(req.comparativa_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail={"error": "comparativa_no_encontrada",
                    "mensaje": "La comparativa expiró o no existe. Volvé a subir los PDFs."}
        )

    from exportar_excel import generar_excel_comparativo
    fecha = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    titulo = req.titulo or f"VectorAI — Comparativa {fecha}"
    xlsx_bytes = generar_excel_comparativo(
        comparativo=cached["comparativo"],
        proveedores=cached["proveedores"],
        titulo=titulo,
    )
    filename = f"VectorAI_Comparativa_{fecha}.xlsx"
    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    master = get_master()
    return {"status": "ok", "master_items": len(master)}
