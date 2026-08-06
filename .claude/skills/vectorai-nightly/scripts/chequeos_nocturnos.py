# -*- coding: utf-8 -*-
"""Chequeos nocturnos deterministas de Vectorai.

Corre los chequeos de codigo, seguridad y salud que no requieren MCP ni
criterio del agente, y emite un JSON con resultado PASO / FALLO / ATENCION
por chequeo. El agente que corre el skill vectorai-nightly consume este JSON,
agrega los chequeos MCP (Supabase advisors, Vercel, logs de Railway) y arma
el reporte.

Uso:
    python chequeos_nocturnos.py            # imprime JSON a stdout
    python chequeos_nocturnos.py --guardar  # ademas escribe reports/nocturno/chequeos_<fecha>.json

Solo lecturas y comandos de diagnostico. No escribe en el repo (salvo
reports/, que esta en .gitignore), no commitea, no toca produccion.
"""
import argparse
import ast
import json
import re
import subprocess
import sys
import urllib.request
import warnings
from datetime import datetime
from pathlib import Path

REPO = Path(r"C:\Pablo\presupuestor")
API_DIR = REPO / "api"
FRONTEND_DIR = REPO / "frontend"
HEALTH_URL = "https://vectorai-production-1f06.up.railway.app/health"
PROD_URL = "https://www.vectorai.com.ar"

# Umbrales de /health.
#
# OJO con master_items: NO es el maestro del matching. /health lo calcula con
# get_master(), que lee api/data/master_materiales.json (937 items, estatico en
# el repo); el maestro real del matching sale de Supabase (materiales_validados,
# ~1.123) y se pagina aparte. Por eso un umbral fijo tipo ">= 900" no
# discriminaba nada. El chequeo util es comparar master_items contra el JSON
# commiteado: si difieren, produccion esta sirviendo un build distinto al del
# repo (deploy desfasado o rollback silencioso).
MASTER_JSON_REPO = API_DIR / "data" / "master_materiales.json"

# aliases_v2 si sale de la BD. En vez de un piso fijo que quedo viejo, se
# compara contra la corrida anterior y se alerta si CAYO: el catalogo solo
# crece (flywheel), una baja significa borrado accidental.
UMBRAL_ALIASES_V2 = 4000
CAIDA_ALIASES_TOLERADA = 0.02  # 2%

# Patrones de secretos que jamas deben estar en archivos trackeados por git.
# (key_hash/key_len del /health no matchean: son metadatos, no valores.)
PATRONES_SECRETOS = [
    (r"sb_secret_[A-Za-z0-9_]{10,}", "service key de Supabase"),
    (r"sk-ant-[A-Za-z0-9\-_]{20,}", "API key de Anthropic"),
    (r"APP_USR-\d{6,}", "access token de MercadoPago"),
    (r"eyJhbGciOi[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}", "JWT (posible key anon/service)"),
]


def _run(cmd, cwd, timeout=600):
    """Corre un comando y devuelve (exit_code, salida_combinada)."""
    try:
        p = subprocess.run(
            cmd, cwd=str(cwd), shell=True, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT tras {timeout}s"
    except Exception as e:  # noqa: BLE001
        return -2, f"ERROR al ejecutar: {e}"


# Suites de tests que corren en cada verificacion. Agregar aca los archivos
# test_*.py nuevos de api/ que sean autoejecutables (imprimen "N fallos").
SUITES_TESTS = [
    "test_extraccion_parsers.py",
    "test_conversion_unidades.py",
    "test_matching_contaminacion.py",
]


def chequeo_tests():
    total_tests = 0
    fallidas = []
    detalles = []
    for suite in SUITES_TESTS:
        code, out = _run(f"python {suite}", API_DIR, timeout=300)
        # Las suites no comparten formato de salida: extraccion imprime
        # "  ok  <test>" + "N fallos"; conversion y contaminacion imprimen
        # "  OK  <test>" + "N/M tests OK". Las dos salen con exit != 0 si algo
        # falla, asi que el exit code manda y el texto solo aporta el conteo.
        tests = len(re.findall(r"^\s*(?:ok|OK)\s{2}", out, re.M))
        total_tests += tests
        if code == 0 and tests:
            detalles.append(f"{suite}: {tests} ok")
        elif code == 0:
            fallidas.append(f"{suite}: exit 0 pero no se detecto ningun test: {out[-400:]}")
        else:
            fallidas.append(f"{suite} (exit {code}): {out[-800:]}")
    if fallidas:
        return "FALLO", " | ".join(fallidas)
    return "PASO", f"{total_tests} tests, 0 fallos ({'; '.join(detalles)})"


def chequeo_tsc():
    code, out = _run("npx tsc --noEmit", FRONTEND_DIR, timeout=600)
    if code == 0:
        return "PASO", "sin errores de tipos"
    return "FALLO", out[-2000:]


def chequeo_sintaxis_api():
    errores = []
    revisados = 0
    for py in API_DIR.rglob("*.py"):
        partes = {p.lower() for p in py.parts}
        if partes & {"node_modules", ".venv", "venv", "__pycache__"}:
            continue
        revisados += 1
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError as e:
            errores.append(f"{py.relative_to(REPO)}: {e}")
    if errores:
        return "FALLO", "; ".join(errores)
    return "PASO", f"{revisados} archivos .py parsean sin errores"


def _get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "vectorai-nightly"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _corrida_anterior() -> dict:
    """Metricas del ultimo chequeos_<fecha>.json guardado (para deltas)."""
    destino = REPO / "reports" / "nocturno"
    previos = sorted(destino.glob("chequeos_*.json"))
    for f in reversed(previos):
        try:
            return json.loads(f.read_text(encoding="utf-8")).get("metricas", {})
        except (OSError, ValueError):
            continue
    return {}


def _master_items_repo() -> int | None:
    try:
        return len(json.loads(MASTER_JSON_REPO.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def chequeo_health():
    try:
        status, h = _get_json(HEALTH_URL)
    except Exception as e:  # noqa: BLE001
        return "FALLO", f"no responde: {e}", {}
    problemas = []   # FALLO
    avisos = []      # ATENCION
    if h.get("status") != "ok":
        problemas.append(f"status={h.get('status')}")

    # master_items = maestro JSON del build, no la BD. Debe coincidir con el
    # archivo commiteado; si no, produccion corre un build distinto al repo.
    esperado = _master_items_repo()
    servido = h.get("master_items", 0)
    if esperado is None:
        avisos.append("no se pudo leer master_materiales.json del repo")
    elif servido != esperado:
        avisos.append(
            f"master_items={servido} != {esperado} del repo "
            "(produccion sirve un build distinto al commiteado)"
        )

    aliases = h.get("aliases_v2", 0)
    if aliases < UMBRAL_ALIASES_V2:
        problemas.append(f"aliases_v2={aliases} (< {UMBRAL_ALIASES_V2})")
    else:
        previo = _corrida_anterior().get("aliases_v2")
        if previo and aliases < previo * (1 - CAIDA_ALIASES_TOLERADA):
            problemas.append(
                f"aliases_v2 cayo de {previo} a {aliases} "
                f"(-{(1 - aliases / previo) * 100:.1f}%): revisar borrados en material_denominaciones"
            )

    ocr = h.get("ocr") or {}
    if not ocr.get("key_len"):
        problemas.append("OCR sin key configurada")
    metricas = {
        "master_items": servido,
        "master_items_repo": esperado,
        "aliases_v2": aliases,
        "sinonimos_bd": h.get("sinonimos_bd"),
        "grupos_marcas_bd": h.get("grupos_marcas_bd"),
        "ocr_motor": ocr.get("motor"),
    }
    if problemas:
        return "FALLO", "; ".join(problemas + avisos), metricas
    if avisos:
        return "ATENCION", "; ".join(avisos), metricas
    return "PASO", (
        f"ok - master_items={servido} (coincide con el repo), aliases_v2={aliases}, "
        f"ocr={ocr.get('motor')} (key configurada)"
    ), metricas


def chequeo_frontend_prod():
    try:
        req = urllib.request.Request(PROD_URL, headers={"User-Agent": "vectorai-nightly"})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status == 200:
                return "PASO", f"{PROD_URL} responde 200"
            return "FALLO", f"HTTP {r.status}"
    except Exception as e:  # noqa: BLE001
        return "FALLO", f"no responde: {e}"


def _parsear_json_embebido(out):
    """Extrae el primer objeto JSON de una salida que puede traer texto extra
    antes o despues (stdout y stderr vienen combinados)."""
    inicio = out.index("{")
    return json.JSONDecoder().raw_decode(out[inicio:])[0]


def chequeo_npm_audit():
    code, out = _run("npm audit --json", FRONTEND_DIR, timeout=300)
    try:
        data = _parsear_json_embebido(out)
        vulns = data.get("metadata", {}).get("vulnerabilities", {})
    except (ValueError, KeyError):
        return "ATENCION", f"no se pudo parsear npm audit (exit {code}): {out[:500]}", {}
    criticas = vulns.get("critical", 0)
    altas = vulns.get("high", 0)
    resumen = ", ".join(f"{k}={v}" for k, v in vulns.items() if isinstance(v, int))
    metricas = {"npm_critical": criticas, "npm_high": altas}
    if criticas:
        return "FALLO", f"vulnerabilidades criticas: {resumen}", metricas
    if altas:
        return "ATENCION", f"vulnerabilidades altas: {resumen}", metricas
    return "PASO", f"sin high/critical ({resumen})", metricas


def chequeo_pip_audit():
    code, out = _run(
        "python -m pip_audit -r api/requirements.txt -f json --progress-spinner off",
        REPO, timeout=600,
    )
    try:
        data = _parsear_json_embebido(out) if "{" in out else {}
        deps = data.get("dependencies", [])
    except ValueError:
        return "ATENCION", f"no se pudo parsear pip-audit (exit {code}): {out[:500]}", {}
    con_vulns = [d for d in deps if d.get("vulns")]
    total = sum(len(d["vulns"]) for d in con_vulns)
    metricas = {"pip_vulns": total}
    if con_vulns:
        detalle = "; ".join(
            f"{d['name']} {d.get('version', '')}: " + ", ".join(v["id"] for v in d["vulns"])
            for d in con_vulns
        )
        return "ATENCION", f"{total} vulnerabilidades en {len(con_vulns)} paquetes: {detalle}", metricas
    return "PASO", f"{len(deps)} dependencias sin vulnerabilidades conocidas", metricas


def chequeo_secretos():
    code, out = _run("git ls-files", REPO, timeout=60)
    if code != 0:
        return "ATENCION", "git ls-files fallo, no se pudo escanear"
    archivos = [a for a in out.splitlines() if a.strip()]
    # .env.example / .env.sample / .env.template son plantillas, no secretos
    env_trackeados = [
        a for a in archivos
        if re.search(r"(^|/)\.env", a)
        and not re.search(r"\.(example|sample|template)$", a)
    ]
    hallazgos = []
    binarias = (".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2", ".ttf", ".pdf",
                ".xlsx", ".xlsm", ".zip", ".mp4", ".webp", ".svg")
    for rel in archivos:
        if rel.lower().endswith(binarias) or rel.endswith("package-lock.json"):
            continue
        f = REPO / rel
        try:
            texto = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for patron, desc in PATRONES_SECRETOS:
            for m in re.finditer(patron, texto):
                linea = texto.count("\n", 0, m.start()) + 1
                # Reportar ubicacion y tipo, jamas el valor
                hallazgos.append(f"{rel}:{linea} ({desc})")
    problemas = []
    if env_trackeados:
        problemas.append(f"archivos .env trackeados por git: {env_trackeados}")
    if hallazgos:
        problemas.append(f"posibles secretos en archivos trackeados: {hallazgos[:20]}")
    if problemas:
        return "FALLO", "; ".join(problemas)
    return "PASO", f"{len(archivos)} archivos trackeados sin patrones de secretos ni .env"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--guardar", action="store_true",
                        help="guardar JSON en reports/nocturno/")
    parser.add_argument("--rapido", action="store_true",
                        help="saltear npm audit y pip-audit (chequeos lentos)")
    args = parser.parse_args()

    resultados = {}
    metricas = {}

    def registrar(nombre, fn):
        r = fn()
        if len(r) == 3:
            estado, detalle, mets = r
            metricas.update(mets)
        else:
            estado, detalle = r
        resultados[nombre] = {"estado": estado, "detalle": detalle}
        print(f"[{estado}] {nombre}: {detalle[:200]}", file=sys.stderr)

    registrar("tests", chequeo_tests)
    registrar("typecheck_frontend", chequeo_tsc)
    registrar("sintaxis_api", chequeo_sintaxis_api)
    registrar("health_api", chequeo_health)
    registrar("frontend_prod", chequeo_frontend_prod)
    registrar("secretos_en_repo", chequeo_secretos)
    if not args.rapido:
        registrar("npm_audit", chequeo_npm_audit)
        registrar("pip_audit", chequeo_pip_audit)

    estados = [r["estado"] for r in resultados.values()]
    salida = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "resumen": {
            "paso": estados.count("PASO"),
            "atencion": estados.count("ATENCION"),
            "fallo": estados.count("FALLO"),
        },
        "metricas": metricas,
        "chequeos": resultados,
    }
    print(json.dumps(salida, ensure_ascii=False, indent=2))

    if args.guardar:
        destino = REPO / "reports" / "nocturno"
        destino.mkdir(parents=True, exist_ok=True)
        f = destino / f"chequeos_{datetime.now().strftime('%Y-%m-%d')}.json"
        f.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"guardado en {f}", file=sys.stderr)

    sys.exit(1 if estados.count("FALLO") else 0)


if __name__ == "__main__":
    main()
