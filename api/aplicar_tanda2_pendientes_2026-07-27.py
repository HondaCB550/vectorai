# -*- coding: utf-8 -*-
"""Aplica la tanda 2 del curado conversacional de pendientes (27-07-2026).

Decisiones de Pablo en el chat sobre los 143 dudosos:
- Bloque A aprobado; la tosca por chasis se normaliza a $/m3 (el chasis es el
  acoplado del camion, 7 m3 -> dividir por 7). Modo 'm3' nuevo.
- Bloque B aprobado entero (P20/IP = agua PN20; nervado = aleteado, hierro de
  construccion no es liso; los AWA 10xx son cloacal, no PEX; etc.).
- Weber refractario 20 kg: material NUEVO por envase (CONS272), no modo kilo
  — el refractario se vende por envase.
- Malla 5 mm: existe (CONS243) -> la #5.5 va ahi, y CONS243 gana modo m2.
- Desgrasadera sin marca NO va a la Tigre (INSTS004, es el unico formato con
  esa capacidad): se crea INSTS250 CAMARA DESGRASADORA PVC.
- Bloque C: 17 textos truncados de extraccion rota -> RECHAZADO.

Quedan para tanda 3 (sin tocar): tornillos alas 10x1-5/8 y 10x2, T3 aguja
6x1.5, ladrillo refractario N4 32mm, alambres por kg, OSB 9.5 y ~25 misc.

Correr:  cd api && python aplicar_tanda2_pendientes_2026-07-27.py [--aplicar]
"""
import os, re, sys, json, datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")


def clave(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


NUEVOS = [
    ("CONS126", {"codigo": "CONS272", "denominacion_principal": "PEGAMENTO",
                 "descripcion": "REFRACTARIO 20 KG"}),
    ("INSTS004", {"codigo": "INSTS250", "denominacion_principal": "CÁMARA DESGRASADORA",
                  "descripcion": "PVC"}),
    # Respuestas de Pablo a las preguntas de la tanda (27-07):
    ("T005", {"codigo": "T019", "denominacion_principal": "TEL ALAS 10*1 5/8",
              "descripcion": "(100 unidades)"}),
    ("T005", {"codigo": "T020", "denominacion_principal": "TEL ALAS 10*2",
              "descripcion": "(100 unidades)"}),
    ("T012", {"codigo": "T021", "denominacion_principal": "T3 6*1 1/2 AGUJA",
              "descripcion": "(100 unidades)"}),
    # "es la tejuela de 32 mm, esa no la tenemos agregada"
    ("CONS125", {"codigo": "CONS273", "denominacion_principal": "TEJUELA REFRACTARIA",
                 "descripcion": "229X114X32MM"}),
    ("EST101", {"codigo": "EST117", "denominacion_principal": "OSB",
                "descripcion": "9,5MM"}),
]

CONVERSIONES = [
    {"codigo_material": "CONS243", "unidad_comercial": "m2", "factor": 1, "unidad_base": "M2",
     "descripcion": "hoja -> m2 (2,40x3 = 7.2; regla Pablo 24-07)", "activo": True},
    {"codigo_material": "CONS107", "unidad_comercial": "m3", "factor": 1, "unidad_base": "M3",
     "descripcion": "chasis 7 m3 -> m3 (regla Pablo 27-07)", "activo": True},
    {"codigo_material": "CONS110", "unidad_comercial": "m3", "factor": 1, "unidad_base": "M3",
     "descripcion": "viaje -> m3 (regla Pablo 27-07)", "activo": True},
    {"codigo_material": "CONS128", "unidad_comercial": "m3", "factor": 1, "unidad_base": "M3",
     "descripcion": "viaje -> m3 (regla Pablo 27-07)", "activo": True},
    # Tornillos nuevos: canonico por unidad, bolsa de 100 vista
    {"codigo_material": "T019", "unidad_comercial": "un", "factor": 100, "unidad_base": "UN",
     "descripcion": "bolsa/pack de 100 (Insuma)", "activo": True},
    {"codigo_material": "T020", "unidad_comercial": "un", "factor": 100, "unidad_base": "UN",
     "descripcion": "bolsa/pack de 100 (Insuma)", "activo": True},
    {"codigo_material": "T021", "unidad_comercial": "un", "factor": 100, "unidad_base": "UN",
     "descripcion": "caja de 100 (Civimet)", "activo": True},
]

DECISIONES = {
    # ── Bloque A ──
    "MAPEI CERAMICO 25KG": "CONS105",
    "Masilla Anclaflex x 32 kg": "Y112",
    "Masilla Durlock Multiuso x 32 kg": "Y112",
    "Tornillos T1 punta mecha x 100 u": "T002",
    "MANGUITO 2015 DE REP. HH DE 63 AWA": "INSTS053",
    "MANGUITO 2014 DE REP. HH DE 50 AWA": "INSTS054",
    "MANGUITO 2013 DE REP. HH DE 40 AWA": "INSTS055",
    "REF LAD RECTO 229X114X63 ART 1": "CONS125",
    "FARA REFRACTARIO RECTO 229X114X63MM 6CM": "CONS125",
    "LADRILLO REFRACTARIO NAT. 228X114X63": "CONS125",
    "Placa Durlock 1.20 m x 2.40 m  x 9,5 mm STD": "Y102",
    "2026-RAMAL SIMP A 45 63X 63MH AWADUCT": "INSTS049",
    "Cable 1,50 mm blanco Fonseca": "INSTE041",
    "BUJE 32-25 ACQUA": "INSTS119",
    "TOSCA X CHASIS 7MT": "CONS107",
    "J.E. RAMAL 110X110A45 M-HPVC 26035112 TIGRE": "INSTS050",
    "CAÑO 1008 DE 40 X 4 AWA": "INSTS030",
    "PILETA 2127 LOSA 5 ENT ACANAL 50/63 X 110 AWA": "INSTS060",
    "TORNILLO P/INODORO COMPLETO 22 X 60": "TER427",
    "REJA 15 X 15 A/INOX MARCO FUND C/EMB (COD 503)": "INSTS185",
    "REJA VENTI. 15X15--100CM2-PLAN-AMU": "TER426",
    "PEGAM REFRAC X 10KG": "CONS126",
    "LLAVE ESF. C/MJA P/TERMOFUS DE 50 ACQ": "INSTS132",
    "LLAVE ESF. C/MJA P/TERMOFUS DE 32 ACQ": "INSTS134",
    "VILLAGE BAÑERA DE EMBUTI R": "TER594",
    # ── Bloque B ──
    "P20 CODO A 90 DE 20 MM I P": "INSTS089",
    "P20 CODO A 90 DE 25 MM I P": "INSTS090",
    "P20 CODO A 90 DE 32 MM I P": "INSTS091",
    "P20 CODO A 90 DE 50 MM I P": "INSTS092",
    "NERVADO 6 mm barra 12 m": "CONS116",
    "NERVADO 8 mm barra 12 m": "CONS136",
    "NERVADO 10 mm barra 12 m": "CONS117",
    "NERVADO 12 mm barra 12 m": "CONS118",
    "NERVADO 16 mm barra 12 m": "CONS137",
    "CAÑO 1031 DE 110 X 1 AWA": "INSTS019",
    "CAÑO 1022 DE 63 X 1 AWA": "INSTS022",
    "CAÑO 1013 DE 50 X 1 AWA": "INSTS025",
    "CAÑO 1004 DE 40 X 1 AWA": "INSTS028",
    "PLANCHA EPS 1.00 X 1.00 ( 30 MM X 20 KG )": "TER112",
    "PLACA CEMENTICIA VOLCANBOARD 8MM": "EST109",
    "CANO DURATOP 50X1.00 MTS": "INSTS025",
    "2057-RAMAL SIMP A 45 40X 40HH AWADUCT": "INSTS048",
    "2053-PIL.PAT.POL.3 ENTRA 40X63 AWADUCT": "INSTS056",
    "SYST UNION DOB.MIXTA C/BRI.50X11/2": "INSTS121",
    "CUPLA HH - Lisa 160 mm P": "INSTS218",
    "PIEDRA BCA MAR D.PLATA X 7 MTS**": "CONS128",
    "Malla SIMA MINI 150 x 150 x 5 mm de 2,40 x 3 m": "CONS243",
    # La #5.5 va con la de 6 (decision de Pablo 27-07), no con la de 5
    "MALLA #5.5 [15 X 15] 2 X 5 MTS [20 KG]": "CONS112",
    "WEBER REFRACTARIO X 20 KG": "CONS272",
    "QUIMTEX impermeable para techos-varios colores x 20 lt": "TER566",
    "FLEX MALLA A.INOX. P/BOMBA 1 X 50 AF 2074": "INSTS206",
    "Cubrecanto 32 x 32 x 2.600 mm": "Y107",
    "PILETA 104P DOBLE 57X37X18 CM": "TER433",
    "ARO DE CERA SELLADOR TOSSAL": "TER597",
    "189/B1 CR BIDET MONOCOMANDO": "TER471",
    "179.05/B1 CR KIT ACCES. 5 PZAS. FV": "TER303",
    "ARIZONA 179.05/B1 JGO ACCES 5 PZAS": "TER303",
    "DESGRASADERA PARA COCINA": "INSTS250",
    # ── Respuestas de Pablo 27-07 (ex tanda 3) ──
    "TORN ALAS P/SUPERB. 10 x 1-5/8 x 100 u": "T019",
    "TORN. ALAS P/SUPERB 10 x 2 x 100 u": "T020",
    "T3 AGUJA - 6 X 1.1/2 X 100": "T021",
    "LADRILLO REFRACTARIO Nº4 [229X114X32 MM]": "CONS273",
    "TABLERO OSB EST 9.50 - 1220X2440 MM": "EST117",
    # Alambres genericos por kg: "todos se unifican" en el alambre dulce
    "Galvanizado Nº16 (1.62 mm esp-rollo 40/60 kg) x kg": "CONS111",
    "Negro recocido Nº 9 x kg": "CONS111",
    "Negro recocido Nº 16 x kg": "CONS111",
}

RECHAZAR = [
    "CODO a 87 30º MH - Con 2",
    "TUBO AMANCO NIVEL 1 - St a",
    "CODO A 45 HH - PN10 16 0",
    "REDUCCIÓN - Excéntrica M H",
    "FLEXIBLE DE COBRE ANILLA D",
    "FLEXIBLE CORRUGADO PARA B",
    "VALVULAS ESFERICAS METAL I",
    "RAMAL CURVO a 87 30º MH",
    "P51 V. ESFERICA CON MANI J",
    "P23 CODO 90 CON ROSCA HE M",
    "P35 TEE REDUCIDA CENTRAL",
    "DESAGUE BASE ABS REJA PL E",
    "ORING + TORNILLOS PARA KIT OTOR OV.CAM",
    "PILETON INYEC. 20 X 20 S A",
    "ZZ 52 ZZ 52 52 x 32 x 15 JHONS O",
    "Bacha de Porcelana Sanit a",
    "7261 RAMAL POSTIZO TIGRE 160 x",
]


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv
    with open(os.path.join(DATA, "analisis_pendientes_2026-07-24.json"), encoding="utf-8") as f:
        analisis = json.load(f)
    idx = {clave(o["texto"]): o for o in analisis}

    def buscar(texto):
        k = clave(texto)
        o = idx.get(k)
        if not o:
            o = next((v for kk, v in idx.items() if kk.startswith(k) or k.startswith(kk)), None)
        return o

    plan, rech, faltan = [], [], []
    for texto, codigo in DECISIONES.items():
        o = buscar(texto)
        (plan.append({"texto": o["texto"], "codigo": codigo, "ids": o["ids"]})
         if o else faltan.append(texto))
    for texto in RECHAZAR:
        o = buscar(texto)
        (rech.append({"texto": o["texto"], "ids": o["ids"]}) if o else faltan.append(texto))

    print(f"asignar: {len(plan)}   rechazar: {len(rech)}   faltantes: {len(faltan)}")
    for t in faltan:
        print(f"  FALTA: {t}")
    if faltan:
        raise SystemExit(1)

    if not aplicar:
        for p in plan:
            print(f"  {p['codigo']:9} <- {p['texto'][:58]}")
        for r in rech:
            print(f"  RECHAZAR  {r['texto'][:58]}")
        print("\n(simulacion — correr con --aplicar)")
        raise SystemExit(0)

    for _, m in NUEVOS:
        if sb.table("materiales_validados").select("codigo").eq("codigo", m["codigo"]).execute().data:
            print(f"{m['codigo']} ya existe. Abortado.")
            raise SystemExit(1)

    todos_ids = [i for p in plan for i in p["ids"]] + [i for r in rech for i in r["ids"]]
    filas_prev = []
    for i in range(0, len(todos_ids), 50):
        filas_prev.extend(sb.table("materiales_pendientes").select("*")
                          .in_("id", todos_ids[i:i + 50]).execute().data or [])
    ruta = os.path.join(DATA, "backup_tanda2_pendientes_2026-07-27.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"tomado": datetime.datetime.now().isoformat(timespec="seconds"),
                   "pendientes": filas_prev, "plan": plan, "rechazos": rech},
                  f, ensure_ascii=False, indent=1)
    print(f"backup -> {ruta}  ({len(filas_prev)} pendientes)")

    for ref, m in NUEVOS:
        cat = (sb.table("materiales_validados").select("categoria")
               .eq("codigo", ref).execute().data or [{}])[0].get("categoria") or "SIN CATEGORIA"
        sb.table("materiales_validados").insert(
            {**m, "categoria": cat, "validado_por": "pablo_chat_2026-07-27"}).execute()
        print(f"+ {m['codigo']} ({cat}): {m['denominacion_principal']} | {m['descripcion']}")

    for c in CONVERSIONES:
        if sb.table("conversion_unidades").select("id") \
             .eq("codigo_material", c["codigo_material"]).eq("activo", True).execute().data:
            print(f"~ conversion {c['codigo_material']} ya existia")
            continue
        sb.table("conversion_unidades").insert(c).execute()
        print(f"+ conversion {c['codigo_material']} {c['unidad_comercial']}")

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
                "validado_por": "pablo_chat_2026-07-27",
            }).in_("id", p["ids"][i:i + 50]).execute()

    ids_rech = [i for r in rech for i in r["ids"]]
    for i in range(0, len(ids_rech), 50):
        sb.table("materiales_pendientes").update({
            "estado": "RECHAZADO", "validado_por": "pablo_chat_2026-07-27",
        }).in_("id", ids_rech[i:i + 50]).execute()

    print(f"\naliases nuevos: {n_alias}  (duplicados: {n_dup})")
    print(f"pendientes validados: {sum(len(p['ids']) for p in plan)}  rechazados: {len(ids_rech)}")
    print("Listo. Cache TTL 5 min.")
