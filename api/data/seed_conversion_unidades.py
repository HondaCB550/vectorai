"""Seed de conversion_unidades desde las descripciones de materiales_validados.

Detecta materiales vendidos en múltiplos (rollos de 100m, bolsas *100, etc.)
usando la heurística validada en Cotizaciones (references/ajustes_unidad.md):
si la descripción interna tiene "*100", "x 25M", "X 100M" → el proveedor suele
cotizar la unidad suelta (metro/unidad) y hay que multiplicar por el factor.

Idempotente: usa upsert sobre UNIQUE(codigo_material, unidad_comercial).
Correr desde api/: python data/seed_conversion_unidades.py [--aplicar]
Sin --aplicar solo lista lo que detecta (dry run).
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

# Multiplicador al FINAL del texto: "*100", "X 25M", "x 16" (con unidad opcional).
# Los patrones en el medio del texto suelen ser dimensiones (12*18*33, 60X60).
PAT_MULT_FINAL = re.compile(r'[*x]\s*(\d{2,4})\s*(m|mts|u)?\.?["\s]*$', re.IGNORECASE)
# Cadena dimensional: dos separadores entre números (12*18*33, 40*20*20)
PAT_CADENA_DIM = re.compile(r"\d\s*[*x]\s*\d+(?:[.,]\d+)?\s*[*x]\s*\d", re.IGNORECASE)


def _detectar_en(texto: str) -> tuple[int, bool] | None:
    """Devuelve (factor, es_metros) si el texto termina en multiplicador real."""
    texto = texto.strip()
    if not texto or PAT_CADENA_DIM.search(texto):
        return None  # es una medida tipo ladrillo/caño, no un pack
    m = PAT_MULT_FINAL.search(texto)
    if not m:
        return None
    factor = int(m.group(1))
    if factor < 10 or factor > 1000:
        return None
    # "x" pegada a letras: solo vale si son una unidad (100MMX25 sí, HEX16 no)
    sep = texto[m.start()]
    if sep in "xX" and m.start() > 0 and texto[m.start() - 1].isalpha():
        letras = re.search(r"[a-záéíóúñ]+$", texto[: m.start()], re.IGNORECASE)
        if not letras or letras.group(0).lower() not in {"mm", "m", "mts", "cm", "grs", "gr", "kg", "lt", "lts"}:
            return None
    tiene_unidad = bool(m.group(2))
    # Sin unidad explícita y precedido por dígito → dimensión AxB (60X60, 100 x 50)
    if not tiene_unidad:
        antes = texto[: m.start()].rstrip()
        if antes and antes[-1].isdigit():
            return None
    es_metros = (m.group(2) or "").lower().startswith("m") or \
        any(p in texto.upper() for p in ("CABLE", "MANGUERA", "ROLLO"))
    return factor, es_metros


def detectar(mat: dict) -> dict | None:
    for campo in (mat.get("denominacion_principal"), mat.get("descripcion")):
        hit = _detectar_en(campo or "")
        if hit:
            factor, es_metros = hit
            return {
                "codigo_material": mat["codigo"],
                "unidad_comercial": "m" if es_metros else "unidad",
                "factor": factor,
                "unidad_base": f"rollo {factor}m" if es_metros else f"pack x{factor}",
                "descripcion": f"Detectado de: {(campo or '').strip()[:80]}",
                "activo": True,
            }
    return None


def main():
    aplicar = "--aplicar" in sys.argv
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    mats = sb.table("materiales_validados") \
             .select("codigo,denominacion_principal,descripcion") \
             .execute().data or []

    filas = [r for r in (detectar(m) for m in mats) if r]

    print(f"Materiales escaneados: {len(mats)}")
    print(f"Conversiones detectadas: {len(filas)}\n")
    for r in filas:
        print(f"  {r['codigo_material']:<12} ×{r['factor']:<5} {r['unidad_comercial']} → {r['unidad_base']:<14} | {r['descripcion'][:60]}")

    if not aplicar:
        print("\nDry run — correr con --aplicar para insertar.")
        return

    if filas:
        sb.table("conversion_unidades").upsert(
            filas, on_conflict="codigo_material,unidad_comercial"
        ).execute()
        print(f"\n{len(filas)} conversiones insertadas/actualizadas en conversion_unidades.")


if __name__ == "__main__":
    main()
