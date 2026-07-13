#!/usr/bin/env python3
"""Algoritmo de matching híbrido entre descripciones de proveedor e ítems del maestro.

Score combinado:
  - 50% token_set_ratio (orden insensible)
  - 30% partial_ratio (subcadenas)
  - 20% match de tokens numéricos (dimensiones)
  - bonificaciones por marca textual y keywords categóricas
  - penalizaciones por keywords distintivas no compartidas
  - bonus por equivalencia confirmada en cargas anteriores

Categorías de score:
  >= 75 -> OK (alta confianza)
  60-74 -> REVISAR (media)
  < 60  -> SIN MATCH (baja, requiere intervención manual)

Feedback loop:
  matchear_item() acepta equivalencias={cod_prov: cod_int} extraídas de la hoja
  Equivalencias del maestro. Si el cod_prov ya fue confirmado antes, el match
  correspondiente sube a score >= 90 y se marca con origen="EQUIV".

Pre-filtro por rubro:
  matchear_item() acepta rubro_prov (str) para restringir la búsqueda a ítems del
  mismo rubro en el maestro antes del scoring. Mejora precisión y velocidad.
"""
import re
from rapidfuzz import fuzz

NUM_TOK = re.compile(r"\b(\d+(?:[.,]\d+)?)\b")

# ── Sinónimos de construcción ─────────────────────────────────────────────────
# Se aplican ANTES del fuzzy a ambos lados (proveedor Y maestro) para que
# términos distintos que refieren al mismo objeto puntúen igual.
# Clave: término a reemplazar (en texto ya uppercase).
# Valor: forma canónica normalizada.
# IMPORTANTE: frases largas primero (ver _SINONIMOS_ORDENADOS más abajo).
# Referencia completa: references/sinonimos.md
SINONIMOS: dict[str, str] = {

    # ── Caños / tubos (genérico) ─────────────────────────────────────────────
    "CAÑERIA":                    "CAÑO",
    "TUBERIA":                    "CAÑO",
    "TUBERÍA":                    "CAÑO",
    "TUBO":                       "CAÑO",
    "TUBOS":                      "CAÑOS",
    "CONDUIT":                    "CAÑO",

    # ── Hierro corrugado ─────────────────────────────────────────────────────
    "HIERRO CONSTRUCCION":        "CORRUGADO",
    "BARRA CORRUGADA":            "CORRUGADO",
    "VARILLA CORRUGADA":          "CORRUGADO",
    "REDONDO CORRUGADO":          "CORRUGADO",
    "ALETEADO":                   "CORRUGADO",
    "CABILLA":                    "CORRUGADO",
    "BARRA HIERRO":               "CORRUGADO",
    "ADN":                        "ALETEADO",   # Acero De Nervado = corrugado arg.
    "HIERRO ADN":                 "HIERRO ALETEADO",

    # ── Áridos ────────────────────────────────────────────────────────────────
    "ARENA RUBIA":                "ARENA",
    "ARENA FINA":                 "ARENA",
    "ARENA GRUESA":               "ARENA",
    "PIEDRA PARTIDA":             "PIEDRA",
    # HORMIGON ELABORADO H21/H30 — NO normalizar: el grado (H21/H30) es info
    # discriminante. Sin sinónimos, fuzzy matching maneja la similitud correctamente.

    # ── Hierro liso ──────────────────────────────────────────────────────────
    "VARILLA LISA":               "REDONDO LISO",

    # ── Perfiles estructurales ────────────────────────────────────────────────
    # NO mapear tipos específicos (UPN/IPN/HEA/HEB/VIGA/DOBLE T) al genérico
    # "PERFIL": el alias corto (ej. "upn") se convertía en "perfil" y matcheaba
    # al 100 contra CUALQUIER texto con la palabra perfil ("PERFIL PGC 200..."),
    # inundando los candidatos y tapando los códigos correctos (bug PGC,
    # detectado por Pablo 03-07-2026). El tipo ES la información discriminante.

    # ── Chapa / plancha ───────────────────────────────────────────────────────
    "PLANCHA":                    "CHAPA",
    "LAMINA":                     "CHAPA",
    "HIERRO PLANO":               "PLANCHUELA",

    # ── Mallas electrosoldadas ────────────────────────────────────────────────
    "MALLA ELECTROSOLDADA":       "MALLA SOLDADA",
    "MALLA ELECTRO SOLDADA":      "MALLA SOLDADA",
    "MALLA SIMA":                 "MALLA SOLDADA",

    # ── Alambre ───────────────────────────────────────────────────────────────
    "ALAMBRE NEGRO":              "ALAMBRE",
    "ALAMBRE ATAR":               "ALAMBRE",

    # ── Steel framing ─────────────────────────────────────────────────────────
    "TRACK":                      "SOLERA",
    "RUNNER":                     "SOLERA",
    "STUD":                       "MONTANTE",
    "PARANTE":                    "MONTANTE",

    # ── Tornillos ─────────────────────────────────────────────────────────────
    "AUTOROSCANTE":               "AUTOPERFORANTE",
    "AUTORROSCANTE":              "AUTOPERFORANTE",
    "AUTOPER":                    "AUTOPERFORANTE",

    # ── Materiales metálicos / recubrimientos ─────────────────────────────────
    "GALVALUME":                  "CINCALUM",
    "GALVACERO":                  "CINCALUM",
    "ZINCANNEALED":               "GALVANIZADO",
    "GALVANIZADA":                "GALVANIZADO",
    "ANGULAR":                    "ANGULO",
    "ÁNGULO":                     "ANGULO",

    # ── Aislaciones ───────────────────────────────────────────────────────────
    "LANA DE ROCA":               "LANA ROCA",
    "LANA MINERAL":               "LANA ROCA",
    "ROCKWOOL":                   "LANA ROCA",
    "LANA DE VIDRIO":             "LANA VIDRIO",
    "ISOVER":                     "LANA VIDRIO",
    "BARRERA DE VAPOR":           "MEMBRANA",
    "BARRERA VAPOR":              "MEMBRANA",
    "VAPOR BARRIER":              "MEMBRANA",

    # ── Placas / paneles ──────────────────────────────────────────────────────
    "PLACA DE YESO":              "PLACA YESO",
    "PYG":                        "PLACA YESO",
    "PLACA CEMENTICIA":           "PLACA CEMENTO",
    "FIBROCEMENTO":               "PLACA CEMENTO",
    "HARDIPANEL":                 "PLACA CEMENTO",
    "MADERA RECONSTITUIDA":       "OSB",

    # ── Eléctrica – conductores ───────────────────────────────────────────────
    "HILO":                       "CABLE",
    "CONDUCTOR":                  "CABLE",
    "ALAMBRE ELECTRICO":          "CABLE",

    # ── Eléctrica – protecciones ──────────────────────────────────────────────
    "BREAKER":                    "DISYUNTOR",
    "TERMOMAGNÉTICO":             "TERMICA",
    "TERMOMAGNETICO":             "TERMICA",
    "LLAVE TERMICA":              "TERMICA",
    "LLAVE TÉRMICA":              "TERMICA",
    "INTERRUPTOR DIFERENCIAL":    "DIFERENCIAL",

    # ── Eléctrica – tomas / llaves ────────────────────────────────────────────
    "TOMA CORRIENTE":             "TOMA",
    "TOMACORRIENTE":              "TOMA",
    "ENCHUFE":                    "TOMA",
    "INTERRUPTOR":                "TECLA",
    "LLAVE LUZ":                  "TECLA",
    "SWITCH":                     "TECLA",

    # ── Eléctrica – luminarias ────────────────────────────────────────────────
    "BOMBILLA":                   "LAMPARA",
    "FOCO":                       "LAMPARA",
    "LUMINARIA":                  "ARTEFACTO",
    "APLIQUE":                    "ARTEFACTO",

    # ── Mangueras / caños flex ────────────────────────────────────────────────
    "CAÑO CORRUGADO":             "MANGUERA CORRUGADA",
    "FLEXIBLE":                   "MANGUERA",

    # ── Sanitaria – cañerías ──────────────────────────────────────────────────
    "POLIETILENO DE ALTA DENSIDAD": "POLIETILENO",
    "PEAD":                       "POLIETILENO",
    "UNION DOBLE":                "UNION",
    "NIPLE":                      "UNION",
    "CUPLA":                      "UNION",   # cupla = unión en desagüe cloacal PVC
    "ACOPLE":                     "UNION",
    "REDUCCIÓN":                  "REDUCCION",
    "REDUCCION EXCENTRICA":       "REDUCCION",
    "REDUCCION CONCENTRICA":      "REDUCCION",

    # ── Sanitaria – grifería / válvulas ───────────────────────────────────────
    "VALVULA DE ESFERA":          "VALVULA",
    "VALVULA ESFERA":             "VALVULA",
    "LLAVE DE PASO":              "VALVULA",
    "LLAVE ESFERA":               "VALVULA",
    "REGISTRO":                   "VALVULA",
    "CANILLA":                    "GRIFO",

    # ── Albañilería – cementos ────────────────────────────────────────────────
    "PORTLAND":                   "CEMENTO",

    # ── Albañilería – cal ─────────────────────────────────────────────────────
    "CAL HIDRATADA":              "CAL",

    # ── Albañilería – áridos ──────────────────────────────────────────────────
    "ÁRIDO":                      "ARENA",
    "ARIDO":                      "ARENA",
    "GRAVILLA":                   "CASCOTE",
    "PEDREGULLO":                 "CASCOTE",

    # ── Albañilería – adhesivos / morteros ────────────────────────────────────
    "MORTERO ADHESIVO":           "ADHESIVO",
    "PEGAMENTO":                  "ADHESIVO",
    "PEGASOL":                    "ADHESIVO",

    # ── Albañilería – revoques / terminaciones ────────────────────────────────
    "JAHARRO":                    "REVOQUE",
    "ENDUIDO PLÁSTICO":           "MASILLA",
    "ENDUIDO PLASTICO":           "MASILLA",
    "ENDUIDO":                    "MASILLA",
    "REVOQUE":                    "MASILLA",

    # ── Pinturas ──────────────────────────────────────────────────────────────
    "ESMALTE SINTÉTICO":          "ESMALTE",
    "ESMALTE SINTETICO":          "ESMALTE",
    "LÁTEX":                      "LATEX",
    "TEMPERA":                    "LATEX",
    "EMULSIÓN":                   "LATEX",
    "EMULSION":                   "LATEX",
    "IMPRIMACIÓN":                "FONDO",
    "IMPRIMACION":                "FONDO",
    "PRIMER":                     "FONDO",
    "AGUARRÁS":                   "AGUARRAS",
    "AGUARAS":                    "AGUARRAS",
    "DILUYENTE":                  "AGUARRAS",
    "DISOLVENTE":                 "AGUARRAS",

    # ── Abreviaciones genéricas ───────────────────────────────────────────────
    "HEX":                        "HEXAGONAL",
}

# Orden de reemplazo: primero frases largas, luego palabras sueltas
_SINONIMOS_ORDENADOS = sorted(SINONIMOS.items(), key=lambda x: -len(x[0]))


def set_sinonimos_extra(extra: dict) -> None:
    """Fusiona sinónimos externos (tabla sinonimos de Supabase) con los
    hardcodeados y reordena. Los llama main._load_knowledge_cache() en cada
    refresh del knowledge cache — sin esto los sinónimos de BD eran código
    muerto (se cargaban y contaban en /health pero nunca se aplicaban).

    Claves y valores pasan por normalize() para calzar con el texto sobre el
    que opera aplicar_sinonimos (uppercase, sin acentos)."""
    global _SINONIMOS_ORDENADOS
    combinados = dict(SINONIMOS)
    for k, v in (extra or {}).items():
        if k and v:
            combinados[normalize(k)] = normalize(v)
    _SINONIMOS_ORDENADOS = sorted(combinados.items(), key=lambda x: -len(x[0]))


# ── Grupos de marcas equivalentes ────────────────────────────────────────────
# Si ambos lados (proveedor y maestro) tienen una marca del mismo grupo,
# se trata como marca compatible aunque no sea idéntica (+5 puntos).
# Útil para accesorios PVC donde Waduct/Duratop/Amanco son intercambiables.
MARCAS_EQUIVALENTES: list[frozenset] = [
    frozenset({"WADUCT", "DURATOP", "AMANCO", "TIGRE", "PLUSGAS", "LOTIX"}),   # PVC desagüe cloacal
    frozenset({"AWADUCT", "ADURATOP"}),                                          # variantes con A-
    frozenset({"BTICINO", "GEWISS", "TICINO"}),                                  # eléctrica modular
    frozenset({"IRAM", "SICA"}),                                                 # cables eléctricos
]

def _marcas_en_texto(texto: str) -> set[str]:
    """Devuelve todas las marcas de MARCAS_EQUIVALENTES presentes en texto (uppercase)."""
    encontradas = set()
    for grupo in MARCAS_EQUIVALENTES:
        for m in grupo:
            if m in texto:
                encontradas.add(m)
    return encontradas

def _mismo_grupo_marca(texto_a: str, texto_b: str) -> bool:
    """True si ambos textos comparten al menos una marca del mismo grupo equivalente."""
    for grupo in MARCAS_EQUIVALENTES:
        en_a = any(m in texto_a for m in grupo)
        en_b = any(m in texto_b for m in grupo)
        if en_a and en_b:
            return True
    return False


KEYWORDS_CATEGORICAS = [
    "MONTANTE", "SOLERA", "PGO", "PGU", "OSB", "LANA", "MEMBRANA", "POLIETILENO",
    "CHAPA", "BANDA", "CINTA", "TORNILLO", "PLACA", "PERFIL", "HEXAGONAL",
    "AGUJA", "MECHA", "AUTOPERFORANTE", "TEL", "ALAS", "YESO", "CINCALUM", "GALVANIZADA",
    "CABLE", "TOMA", "TECLA", "MODULO", "BASTIDOR", "TAPA", "CAÑO", "DISYUNTOR",
    "TERMICA", "SPOT", "DICROICO", "JABALINA", "PRECINTO", "RELOJ",
    "BIDIRECCIONAL", "MIGNON", "ESTANCA", "EMBUTIR", "OCTOGONAL", "RECTANGULAR",
    "MANGUERA", "CONECTOR", "UNION", "ARTEFACTO", "CORRUGADO",
    # Agregados para hierros/caños
    "ANGULO", "PLANCHUELA", "CUADRADO", "REDONDO", "ALETEADO",
    "SOLDADA", "MALLA", "ZINCANNEALED", "LAF", "SAE",
]

KEYWORDS_DISTINTIVAS = {
    "MONTANTE", "SOLERA", "PGO", "PGU", "AGUJA", "MECHA", "HEXAGONAL",
    "CAJA", "CABLE", "TOMA", "TECLA", "MODULO", "BASTIDOR", "TAPA", "SPOT",
    "DISYUNTOR", "TERMICA", "CORRUGADO", "REDONDO", "ANGULO", "PLANCHUELA",
    "MALLA", "SOLDADA", "BLOQUE",
}


def normalize(s: str) -> str:
    s = (s or "").upper()
    # Quitar acentos frecuentes
    for a, b in [("Á","A"),("É","E"),("Í","I"),("Ó","O"),("Ú","U"),("Ü","U")]:
        s = s.replace(a, b)
    # Quitar contenido entre paréntesis (dimensiones técnicas como "(3,33 x 63,5 mm)")
    s = re.sub(r"\([^)]*\)", " ", s)
    # Quitar patrones de ruido tipo ***NUEVA BOLSA X 25KG*** al inicio
    s = re.sub(r"^\*+[^*]+\*+\s*", "", s)
    # Quitar unidades de presentación redundantes al inicio (BOLSA X NNN, CAJA X NNN)
    s = re.sub(r"^(NUEVA\s+)?(BOLSA|CAJA|PAQUETE|ROLLO|BIDON)\s+X\s+\d+\w*\s*", "", s)
    # Normalizar guión entre letra y número (H-21 → H21, C-25 → C25)
    s = re.sub(r"(?<=[A-Z])-(?=\d)|(?<=\d)-(?=[A-Z])", "", s)
    # Quitar parámetros técnicos de hormigón que no aparecen en el master
    s = re.sub(r"\bASENTAMIENTO\b", " ", s)
    # Quitar medidas de asentamiento como "10 CM" que generan falsos positivos numéricos
    s = re.sub(r"\b\d+\s*CM\b", " ", s)
    s = re.sub(r"[^\w\s\.\-/]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def aplicar_sinonimos(s: str) -> str:
    """Reemplaza sinónimos en texto ya normalizado (uppercase, sin acentos).

    Aplica frases largas primero para evitar reemplazos parciales.
    Usa word boundary para no reemplazar subcadenas (TUBO dentro de TUBOCLAVE, etc.).
    """
    for origen, canonica in _SINONIMOS_ORDENADOS:
        if origen in s:
            s = re.sub(r"\b" + re.escape(origen) + r"\b", canonica, s)
    return s


def extract_nums(s: str) -> set[str]:
    s = normalize(s)
    return {m.replace(",", ".") for m in NUM_TOK.findall(s)}


def _prep(s: str) -> str:
    """Normalize + aplicar sinónimos. Punto de entrada único para ambos lados."""
    return aplicar_sinonimos(normalize(s))


def score_match(prov_desc: str, mat: dict) -> float:
    """
    mat: dict con 'codigo', 'item', 'detalle', 'marca', 'rubro', 'unidad'.
    Devuelve score 0-100.
    """
    p = _prep(prov_desc)
    texto_mat = " ".join([
        mat.get("item", ""), mat.get("detalle", ""),
        mat.get("marca", ""), mat.get("rubro", "")
    ])
    m_text = _prep(texto_mat)

    score = (
        fuzz.token_set_ratio(p, m_text) * 0.5
        + fuzz.partial_ratio(p, m_text) * 0.3
    )

    # Match numérico
    nums_p, nums_m = extract_nums(p), extract_nums(m_text)
    if nums_p and nums_m:
        score += (len(nums_p & nums_m) / max(len(nums_p), 1)) * 20

    # Marca textual — exacta o del mismo grupo equivalente
    marca = (mat.get("marca") or "").upper()
    if marca and marca not in ("VARIOS", "") and marca in p:
        score += 8
    elif _mismo_grupo_marca(p, m_text):
        score += 5   # marca compatible (ej. Waduct ↔ Amanco, mismo producto distinta marca)

    # Keywords categóricas (sobre texto con sinónimos ya aplicados)
    for kw in KEYWORDS_CATEGORICAS:
        in_p = kw in p
        in_m = kw in m_text
        if in_p and in_m:
            score += 4
        elif in_p != in_m and kw in KEYWORDS_DISTINTIVAS:
            score -= 6

    return round(min(100, max(0, score)), 1)


def categorizar(score: float) -> str:
    if score >= 75:
        return "OK"
    if score >= 60:
        return "REVISAR"
    return "SIN MATCH"


def matchear_item(
    prov_desc: str,
    master: list[dict],
    top_n: int = 3,
    cod_prov: str = None,
    equivalencias: dict = None,
    rubro_prov: str = None,
) -> list[tuple[float, dict, str]]:
    """Devuelve top-N candidatos como (score, item_dict, origen).

    origen = "EQUIV" si el match viene de una equivalencia confirmada
             en cargas anteriores, "IA" si es puramente algorítmico.

    equivalencias: dict {cod_prov: cod_int_confirmado} extraído de la hoja
                   Equivalencias del maestro via aplicar_carga.buscar_en_equivalencias().
                   Si cod_prov está en el dict y el item maestro coincide con
                   ese cod_int, el score se sube a max(score_actual, 90).

    rubro_prov: rubro del ítem del proveedor (ej. "CAÑOS", "HIERRO").
                Si se pasa, restringe la búsqueda a ítems maestro con el mismo
                rubro antes del scoring (mejora precisión y velocidad).
                Si el pre-filtro deja <5 candidatos, se hace el scoring completo
                como fallback para no perder matches válidos.
    """
    confirmado_cod = None
    if equivalencias:
        # Buscar por cod_prov (formato skill Excel) o por descripcion (formato API)
        for lookup_key in ([str(cod_prov).strip()] if cod_prov else []) + [str(prov_desc).strip()]:
            entrada = equivalencias.get(lookup_key)
            if entrada:
                confirmado_cod = (
                    entrada.get("cod_interno") if isinstance(entrada, dict) else entrada
                )
                break

    # Pre-filtro por rubro (siempre incluye el ítem de equivalencia si existe)
    if rubro_prov:
        rubro_norm = normalize(rubro_prov)
        candidatos = [m for m in master if normalize(m.get("rubro", "")) == rubro_norm]
        # Asegurar que el ítem confirmado esté en la lista aunque sea de otro rubro
        if confirmado_cod:
            ya_incluido = any(str(m.get("codigo","")).strip() == str(confirmado_cod).strip()
                              for m in candidatos)
            if not ya_incluido:
                for m in master:
                    if str(m.get("codigo","")).strip() == str(confirmado_cod).strip():
                        candidatos.append(m)
                        break
        if len(candidatos) < 5:
            candidatos = master  # fallback: scoring completo
    else:
        candidatos = master

    scored = []
    for m in candidatos:
        s = score_match(prov_desc, m)
        cod_maestro = str(m.get("codigo", "")).strip()
        if confirmado_cod and cod_maestro == str(confirmado_cod).strip():
            origen = "EQUIV"
            s = max(s, 90.0)
        else:
            origen = "IA"
        scored.append((s, m, origen))

    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]


if __name__ == "__main__":
    print("Módulo de matching. Importar y usar score_match() / matchear_item().")
