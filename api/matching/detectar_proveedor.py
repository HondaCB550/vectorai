#!/usr/bin/env python3
"""Detectar proveedor automáticamente desde nombre de archivo o texto de PDF.

Uso:
    python detectar_proveedor.py <nombre_archivo_o_texto>
    → imprime el nombre canónico del proveedor, o "DESCONOCIDO" si no matchea.

Ejemplos:
    python detectar_proveedor.py "presupuesto_baukraft_mayo2026.pdf"  → BAUKRAFT
    python detectar_proveedor.py "FAGUA materiales.xlsx"              → FAGUA2
    python detectar_proveedor.py "Cotizacion Electricidad Belgrano"   → E. BELGRANO
"""
import sys
import json
import re
from pathlib import Path

CONFIG_DEFAULT = Path(__file__).parent.parent.parent / "carga-precios-proveedores" / "references" / "configuracion.json"


def _cargar_config(config_path: str | Path = None) -> dict:
    path = Path(config_path) if config_path else CONFIG_DEFAULT
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def detectar_proveedor(texto: str, config_path: str | Path = None) -> str | None:
    """Detecta el nombre canónico del proveedor buscando alias en el texto.

    El texto puede ser el nombre del archivo, el path completo, o cualquier
    fragmento de texto que identifique al proveedor (encabezado del PDF, etc.).

    Estrategia:
      1. Normalizar texto a mayúsculas sin acentos.
      2. Para cada proveedor en configuracion.json, verificar si algún alias
         aparece como palabra completa o subcadena del texto normalizado.
      3. Priorizar aliases más largos (match más específico primero).
      4. Devolver nombre_canonico del primer match, o None si no se detecta.
    """
    config = _cargar_config(config_path)
    texto_norm = _normalizar(texto)

    candidatos = []
    for prov in config.get("proveedores", []):
        for alias in prov.get("alias_archivo", []):
            alias_norm = _normalizar(alias)
            if alias_norm and alias_norm in texto_norm:
                candidatos.append((len(alias_norm), prov["nombre_canonico"]))

    if not candidatos:
        return None

    # El alias más largo gana (más específico)
    candidatos.sort(key=lambda x: -x[0])
    return candidatos[0][1]


def _normalizar(s: str) -> str:
    s = s.upper()
    # Normalizar acentos simples del español
    for src, dst in [("Á","A"),("É","E"),("Í","I"),("Ó","O"),("Ú","U"),("Ñ","N")]:
        s = s.replace(src, dst)
    # Reducir separadores a espacio
    s = re.sub(r"[_\-\.]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def detectar_desde_archivo(path_archivo: str, config_path: str | Path = None) -> str | None:
    """Detecta el proveedor usando el nombre del archivo (sin directorio, sin extensión)."""
    nombre = Path(path_archivo).stem
    return detectar_proveedor(nombre, config_path)


def detectar_con_fallback(
    path_archivo: str,
    texto_pdf: str = "",
    config_path: str | Path = None
) -> dict:
    """Intenta detectar el proveedor primero por nombre de archivo, luego por texto.

    Devuelve:
      {
        "proveedor": str | None,
        "confianza": "ARCHIVO" | "TEXTO" | "NO DETECTADO",
        "texto_usado": str
      }
    """
    # 1. Por nombre de archivo
    resultado = detectar_desde_archivo(path_archivo, config_path)
    if resultado:
        return {
            "proveedor": resultado,
            "confianza": "ARCHIVO",
            "texto_usado": Path(path_archivo).name
        }

    # 2. Por contenido del PDF (primeras líneas o encabezado)
    if texto_pdf:
        primeras_lineas = "\n".join(texto_pdf.splitlines()[:20])
        resultado = detectar_proveedor(primeras_lineas, config_path)
        if resultado:
            return {
                "proveedor": resultado,
                "confianza": "TEXTO",
                "texto_usado": primeras_lineas[:120]
            }

    return {
        "proveedor": None,
        "confianza": "NO DETECTADO",
        "texto_usado": ""
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    texto_input = " ".join(sys.argv[1:])
    resultado = detectar_con_fallback(texto_input, texto_pdf=texto_input)
    if resultado["proveedor"]:
        print(resultado["proveedor"])
        print(f"  (detectado por {resultado['confianza']})", file=sys.stderr)
    else:
        print("DESCONOCIDO")
        sys.exit(1)
