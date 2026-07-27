# -*- coding: utf-8 -*-
"""Aplica la tanda 1 del curado conversacional de pendientes (24-07-2026).

Decisiones de Pablo en el chat (reemplaza el flujo Excel):
- Bloque 1 aprobado tal cual; CONS112 ademas pasa a canonico $/m2 (modo 'm2'
  nuevo en _convertir_unidad).
- Bloque 2 aprobado con los destinos corregidos por reglas de dominio.
- Bloque 3: se crean 6 materiales nuevos (chapa incolora 0,8; marco porta
  tapa y tapa de camara PVC; T3 mecha 6x1-5/8; reduccion 110a40; correa
  PGC 100 1,60 x 12 m), el fleje C18 se unifica con A001, el "T1 MECHA
  10x3/4" es el hexagonal T001 (el proveedor no escribe HEX), y las llaves
  esfericas son de agua: 3/4" = INSTS133 (25 mm) y 1" = INSTS130.

Todo por IDs/textos explicitos con backup previo. Los pendientes resueltos
quedan estado=VALIDADO + codigo_asignado (mismo estado que usa /admin).

Correr:  cd api && python aplicar_tanda1_pendientes_2026-07-24.py [--aplicar]
"""
import os, re, sys, json, datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")


def clave(t: str) -> str:
    """Clave robusta a acentos, º, Ø y comillas: solo [a-z0-9]."""
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


# (referencia_de_categoria, fila) — la categoria se copia del material vecino
NUEVOS = [
    ("CH010", {"codigo": "CH022", "denominacion_principal": "CHAPA",
               "descripcion": "SINUSOIDAL INCOLORA 0,8MM *1,10"}),
    ("INSTS003", {"codigo": "INSTS247", "denominacion_principal": "MARCO PORTA TAPA",
                  "descripcion": "CAMARA PVC"}),
    ("INSTS003", {"codigo": "INSTS248", "denominacion_principal": "TAPA CAMARA",
                  "descripcion": "PVC"}),
    ("T012", {"codigo": "T018", "denominacion_principal": "T3 6*1 5/8 MECHA",
              "descripcion": "(100 unidades)"}),
    ("INSTS221", {"codigo": "INSTS249", "denominacion_principal": "CAÑO PVC",
                  "descripcion": "REDUCCION 110 A 40"}),
    ("P109", {"codigo": "P118", "denominacion_principal": "PGC 100*1,60",
              "descripcion": "12 MTS"}),
]

CONVERSIONES = [
    {"codigo_material": "CONS112", "unidad_comercial": "m2", "factor": 1, "unidad_base": "M2",
     "descripcion": "hoja -> m2 (2x5=10, 3x2.40=7.2; regla Pablo 24-07)", "activo": True},
    {"codigo_material": "CH022", "unidad_comercial": "ml", "factor": 1, "unidad_base": "ML",
     "descripcion": "chapa entera / largo, como las demas chapas", "activo": True},
    {"codigo_material": "T018", "unidad_comercial": "un", "factor": 100, "unidad_base": "UN",
     "descripcion": "bolsa de 100 (La Foresta)", "activo": True},
]

# texto (como figura en el analisis) -> codigo destino
DECISIONES = {
    # Bloque 1 — aprobados tal cual
    "HIERRO GERDAU Ø 6 MM": "CONS116",
    "VARILLA 6": "CONS116",
    "VARILLA 12": "CONS118",
    "VARILLA 8": "CONS136",
    "TORN AUT S/FRAME 10x3/4 x 100 unid": "T001",
    "CANO DURATOP 110X1.00 MTS": "INSTS019",
    "CANO DURATOP 110X4.00 MTS": "INSTS021",
    "CANO DURATOP 63X1.00 MTS": "INSTS022",
    "CANO DURATOP 63X2.00 MTS": "INSTS023",
    "CANO DURATOP 40X1.00 MTS": "INSTS028",
    "CANO DURATOP 40X2.00 MTS": "INSTS029",
    "CANO DURATOP 40X4.00 MTS": "INSTS030",
    "CAÑO 20MM MAGNUM PN20 A/FRIA YCAL": "INSTS074",
    "CAÑO 25MM MAGNUM PN20 A/FRIA YCAL": "INSTS075",
    "MALLA MINI 15X15 (6) (3X2.40)": "CONS112",
    "WEBER COLOR PRESTIGE X 2 KG GRIS PERLA": "CONS226",
    "A.SYSTEM LLAVE DE PASO 20 MIXTO": "INSTS128",
    "Solera 70 x 30 x 2.600 mm": "P104",
    "A.SYSTEM BUJE RED.25 X 20": "INSTS117",
    "A.SYSTEM BUJE RED.32 X 20": "INSTS118",
    "A.SYSTEM BUJE RED.32 X 25": "INSTS119",
    "A.SYSTEM BUJE RED.50 X 32": "INSTS120",
    "CODO a 45º MH 110 mm PV C": "INSTS038",
    "J.E. REDUCCION TOPE M-H 160X110MM 26037646 TIGRE": "INSTS221",
    "Hidrófugo químico inorgánico Hidrosol x 20 kg": "CONS141",
    "TORNILLO P/INODORO COMPLETO 22 X 80": "TER427",
    # Bloque 2 — destinos corregidos por reglas de dominio
    "J.E. CUPLA H-H 160 PVC 26032563 TIGRE": "INSTS218",
    "CODO a 45º MH 40 mm P V": "INSTS035",
    "Lana de vidrio 50 mm con papel aluminio 21,60 m2": "AISL112",
    "Lana de vidrio Isover con papel aluminio 50 mm x 14,": "AISL112",
    "PF IND C100X40X15X1.3 MM X 6 M": "PC006",
    # Bloque 3 — decisiones de Pablo
    "SINUSOIDAL 0.8mm INC 1.1x 6.0m": "CH022",
    "MARCO PORTA TAPA PVC O.V.CAM (cod.M-KIT) O.V. CAM": "INSTS247",
    "TAPA PVC O.V.CAM (cod.T-KIT) O.V. CAM": "INSTS248",
    "FLEJE CRUZ SAN ANDRES GALV C18 Des.35-60mm": "A001",
    'TORNILLO T1 MECHA 10X3/4" (BOLSA X 100)- TEL': "T001",
    "T3 MECHA 6X1 5/8 TOOLISTER (BOLSAX100)": "T018",
    "J.E. REDUCCION TOPE M-H 110X40MM 26037590 TIGRE": "INSTS249",
    "PFGAL C100X45X15X1.6 MM X 12 M": "P118",
    "Llave esférica 3/4”": "INSTS133",
    "Llave esférica 1”": "INSTS130",
}


def cargar_analisis():
    with open(os.path.join(DATA, "analisis_pendientes_2026-07-24.json"), encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv
    analisis = cargar_analisis()
    idx = {clave(o["texto"]): o for o in analisis}

    plan, faltantes = [], []
    for texto, codigo in DECISIONES.items():
        # La lana Isover viene truncada en la tabla: matchear por prefijo
        k = clave(texto)
        o = idx.get(k)
        if not o:
            o = next((v for kk, v in idx.items() if kk.startswith(k)), None)
        if not o:
            faltantes.append(texto)
            continue
        plan.append({"texto": o["texto"], "codigo": codigo, "ids": o["ids"]})

    print(f"decisiones: {len(DECISIONES)}   mapeadas: {len(plan)}   faltantes: {len(faltantes)}")
    for t in faltantes:
        print(f"  FALTA EN ANALISIS: {t}")
    if faltantes:
        raise SystemExit(1)
    for p in plan:
        print(f"  {p['codigo']:9} <- {p['texto'][:60]}  ({len(p['ids'])} filas)")

    if not aplicar:
        print("\n(simulacion — correr con --aplicar)")
        raise SystemExit(0)

    # Guardas de re-run
    for _, m in NUEVOS:
        if sb.table("materiales_validados").select("codigo").eq("codigo", m["codigo"]).execute().data:
            print(f"\n{m['codigo']} ya existe. Abortado.")
            raise SystemExit(1)

    # Backup de los pendientes tocados
    todos_ids = [i for p in plan for i in p["ids"]]
    filas_prev = []
    for i in range(0, len(todos_ids), 50):
        filas_prev.extend(sb.table("materiales_pendientes").select("*")
                          .in_("id", todos_ids[i:i + 50]).execute().data or [])
    ruta = os.path.join(DATA, "backup_tanda1_pendientes_2026-07-24.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"tomado": datetime.datetime.now().isoformat(timespec="seconds"),
                   "pendientes": filas_prev, "plan": plan}, f, ensure_ascii=False, indent=1)
    print(f"\nbackup -> {ruta}  ({len(filas_prev)} pendientes)")

    # Materiales nuevos (categoria copiada del vecino de referencia)
    for ref, m in NUEVOS:
        cat = (sb.table("materiales_validados").select("categoria")
               .eq("codigo", ref).execute().data or [{}])[0].get("categoria") or "SIN CATEGORIA"
        fila = {**m, "categoria": cat, "validado_por": "pablo_chat_2026-07-24"}
        sb.table("materiales_validados").insert(fila).execute()
        print(f"+ {m['codigo']} ({cat}): {m['denominacion_principal']} | {m['descripcion']}")

    # Conversiones
    for c in CONVERSIONES:
        if sb.table("conversion_unidades").select("id") \
             .eq("codigo_material", c["codigo_material"]).eq("activo", True).execute().data:
            print(f"~ conversion {c['codigo_material']} ya existia, no se duplica")
            continue
        sb.table("conversion_unidades").insert(c).execute()
        print(f"+ conversion {c['codigo_material']} {c['unidad_comercial']}/{c['factor']}")

    # Aliases + resolver pendientes
    n_alias = n_dup = 0
    for p in plan:
        den = p["texto"].strip().lower()
        ya = sb.table("material_denominaciones").select("id") \
               .eq("codigo_material", p["codigo"]).eq("denominacion", den).execute().data
        if ya:
            n_dup += 1
        else:
            sb.table("material_denominaciones").insert({
                "codigo_material": p["codigo"], "denominacion": den,
                "origen": "usuario_admin", "confianza": 96,
                "frecuencia_encontrada": len(p["ids"]),
            }).execute()
            n_alias += 1
        for i in range(0, len(p["ids"]), 50):
            sb.table("materiales_pendientes").update({
                "estado": "VALIDADO", "codigo_asignado": p["codigo"],
                "validado_por": "pablo_chat_2026-07-24",
            }).in_("id", p["ids"][i:i + 50]).execute()

    print(f"\naliases nuevos: {n_alias}  (ya existian: {n_dup})")
    print(f"pendientes resueltos: {len(todos_ids)}")
    print("Listo. Cache TTL 5 min.")
