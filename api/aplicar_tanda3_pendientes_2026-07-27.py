# -*- coding: utf-8 -*-
"""Aplica la tanda 3 del curado conversacional de pendientes (27-07-2026).

Reglas nuevas de Pablo en esta tanda:
- SANITARIOS DE LINEA/MARCA VAN POR MODELO, nunca unificados: un inodoro
  South no se compara con un Roca; solo cuando el codigo coincide literal
  (la bacha C37/18) se unifica. -> 11 items nuevos de losa/griferia.
- Accesorios de camara POR MARCA (O.V.CAM / Tuboforte / Tigre / Duke): las
  bocas pueden ser de una marca y la camara de otra en el mismo presupuesto.
- Reja y tapa 15x15 INOX aparte de la de fundicion (fundicion = exterior,
  inox = interior/bano).
- Pileta patio 160x110 es PLUVIAL (boca 160 para poder limpiar, salida 110);
  la boca de acceso 160 es lo mismo sin sifon.
- Envases: tambor 200L e isocrete 100L son items propios (el grande siempre
  es mas barato: no se prorratea por litro). Cinta papel 23m se unifica con
  la de 150 (poca diferencia). La cinta TRAMADA no tiene codigo correcto en
  el maestro (Y124 es la barrera de agua/viento) -> queda pendiente.
- Hierro dulce ES alambre de atar -> CONS111 (el 4.2 y el 0.6xkg).
- Vidrios: NO se cargan (decision explicita).
- Fletes se aceptan en INS029 con la salvedad de que no son comparables por
  distancia (queda anotado).

Correr:  cd api && python aplicar_tanda3_pendientes_2026-07-27.py [--aplicar]
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
    # (ref_categoria, fila) — losa sanitaria por modelo
    ("TER301", {"codigo": "TER598", "denominacion_principal": "INODORO + DEPOSITO", "descripcion": "SOUTH"}),
    ("TER493", {"codigo": "TER599", "denominacion_principal": "BIDET", "descripcion": "SOUTH VESSANTI"}),
    ("TER430", {"codigo": "TER600", "denominacion_principal": "ASIENTO INODORO", "descripcion": "MONACO ROCA"}),
    ("TER430", {"codigo": "TER601", "denominacion_principal": "ASIENTO INODORO", "descripcion": "PARAVOR BA99"}),
    ("TER304", {"codigo": "TER602", "denominacion_principal": "LAVATORIO", "descripcion": "PIAZZA VILLAGE"}),
    ("TER304", {"codigo": "TER603", "denominacion_principal": "BACHA DE APOYO", "descripcion": "A449 465X420"}),
    ("TER485", {"codigo": "TER604", "denominacion_principal": "DEPOSITO INODORO", "descripcion": "FERRUM BARI DUAL"}),
    ("TER485", {"codigo": "TER605", "denominacion_principal": "DEPOSITO INODORO", "descripcion": "MONACO ROCA 3/6L"}),
    ("TER301", {"codigo": "TER606", "denominacion_principal": "INODORO LARGO", "descripcion": "MONACO ROCA"}),
    ("TER302", {"codigo": "TER607", "denominacion_principal": "GRIFERÍA DE BAÑO", "descripcion": "FV ARIZONA - DUCHA EMBUTIR"}),
    ("TER303", {"codigo": "TER608", "denominacion_principal": "SET ACCESORIOS BAÑO", "descripcion": "CUBE 4 PIEZAS"}),
    # otros TER
    ("TER115", {"codigo": "TER609", "denominacion_principal": "MALLA F. VIDRIO", "descripcion": "90 GRS / 1X50 MTS"}),
    ("TER497", {"codigo": "TER610", "denominacion_principal": "ZOCALO MDF", "descripcion": "EUCAFLOOR LAMINADO"}),
    # sanitarios PVC / instalaciones
    ("INSTS056", {"codigo": "INSTS251", "denominacion_principal": "PILETA DE PATIO", "descripcion": "5 ENTRADAS"}),
    ("INSTS056", {"codigo": "INSTS252", "denominacion_principal": "PILETA DE PATIO", "descripcion": "160X110 PLUVIAL C/SIFON"}),
    ("INSTS058", {"codigo": "INSTS253", "denominacion_principal": "BOCA DE ACCESO", "descripcion": "160"}),
    ("INSTS050", {"codigo": "INSTS254", "denominacion_principal": "RAMAL A 45", "descripcion": "160"}),
    ("INSTS003", {"codigo": "INSTS255", "denominacion_principal": "ARO SUPLEMENTO CAMARA", "descripcion": "O.V.CAM 10CM"}),
    ("INSTS005", {"codigo": "INSTS256", "denominacion_principal": "PROLONGACION CAMARA INSPECCION", "descripcion": "TUBOFORTE"}),
    ("INSTS185", {"codigo": "INSTS257", "denominacion_principal": "REJA 15X15", "descripcion": "ACERO INOXIDABLE"}),
    ("INSTS185", {"codigo": "INSTS258", "denominacion_principal": "TAPA 15X15", "descripcion": "ACERO INOXIDABLE"}),
    ("INSTS210", {"codigo": "INSTS259", "denominacion_principal": "CAÑO PVC", "descripcion": "40 X 3,2MM"}),
    ("INSTS210", {"codigo": "INSTS260", "denominacion_principal": "CAÑO PVC", "descripcion": "50 X 3,2MM"}),
    ("INSTS017", {"codigo": "INSTS261", "denominacion_principal": "PURIFICADOR DE AGUA", "descripcion": "DVIGI 6 ETAPAS"}),
    ("INSTS013", {"codigo": "INSTS262", "denominacion_principal": "BOMBA CLOACAL", "descripcion": "750W"}),
    # construccion / envases propios
    ("CONS141", {"codigo": "CONS274", "denominacion_principal": "HIDROFUGO", "descripcion": "TAMBOR 200 LTS"}),
    ("CONS202", {"codigo": "CONS275", "denominacion_principal": "ISOCRETE PERLAS EPS", "descripcion": "BOLSA 100 LTS"}),
    ("CONS268", {"codigo": "CONS276", "denominacion_principal": "MANTA HIDROFUGA", "descripcion": "ROLLO 1,50X30 MTS"}),
    ("CONS268", {"codigo": "CONS277", "denominacion_principal": "MEMBRANA HIDROFUGA", "descripcion": "ROLLO 1,50X20 MTS"}),
    ("CONS105", {"codigo": "CONS278", "denominacion_principal": "ARCILLA", "descripcion": "10 KG"}),
    ("CONS107", {"codigo": "CONS279", "denominacion_principal": "CONTENEDOR VOLQUETE", "descripcion": "5 M3"}),
    # estructura / metalicos / electricos / clima
    ("P115", {"codigo": "P118", "denominacion_principal": "CORREA C", "descripcion": "100*45*15*2,0"}),
    ("CH017", {"codigo": "CH023", "denominacion_principal": "FLEJE ZINC", "descripcion": "C25 610MM"}),
    ("A011", {"codigo": "A022", "denominacion_principal": "ANCLAJES", "descripcion": "ARANDELA 35*35 3.2MM"}),
    ("A011", {"codigo": "A023", "denominacion_principal": "ANCLAJES", "descripcion": "ARANDELA 80*80 3.2MM"}),
    ("INSTE043", {"codigo": "INSTE124", "denominacion_principal": "CABLE PARALELO", "descripcion": "2 X 0,5"}),
    ("CLIM104", {"codigo": "CLIM121", "denominacion_principal": "CAJA PREINSTALACION AIRE ACOND", "descripcion": "SALIDA VERTICAL"}),
]

CONVERSIONES = [
    # "X 10": pack de 10 arandelas — el fallback del factor literal lo detecta
    {"codigo_material": "A022", "unidad_comercial": "un", "factor": 10, "unidad_base": "UN",
     "descripcion": "pack de 10 (Insuma)", "activo": True},
    {"codigo_material": "A023", "unidad_comercial": "un", "factor": 10, "unidad_base": "UN",
     "descripcion": "pack de 10 (Insuma)", "activo": True},
]

DECISIONES = {
    # ── aprobados / unificaciones ──
    "ARENA (AR)": "CONS225",
    "ARENA RUBIA": "CONS240",                       # arena rubia = arena fina (Pablo)
    "CAÑO 1006 DE 40 X 2 AWA": "INSTS029",
    "C 37/18 C 37/18 70,8 x 37 x 18 J H": "TER433",
    "H 21 C.R. 1 x m3": "CONS113",
    "EMPALME ACCESO 63-50 HORIZ.CHICO": "INSTS058",
    "LAVAT APOYO TORI CHICA 1AG L320K* OFERTA": "TER437",
    "BOMBA PLUVIUS CPM 158A (1 HP) (CPM)": "INSTS013",
    "SUMERG ROWA 1HP SUB 4RW COMP 56/7M": "INSTS192",
    "TARUGO SX 8 LAD.HUECO REDEX": "A020",
    "Transporte": "INS029",
    "TELGOPOR PERLAS CAFIVEL X 170 LT": "CONS202",
    "Cinta de papel microperforada x 23 m": "Y106",
    "HIERRO DULCE DEL 4.2": "CONS111",              # hierro dulce = alambre de atar
    "HIERRO DULCE DEL 0.6 X KG AL 220 GERDAU": "CONS111",
    "CAM - KIT-COJINETE-MARCO TAPA": "INSTS247",    # kit marco+tapa, misma marca CAM
    # ── a materiales nuevos ──
    "INODORO + DEPOSITO SOUTH": "TER598",
    "BIDET SOUTH VESSANTI": "TER599",
    "ASIENTO MONACO HERR. BISAG.NYLON BL ROCA": "TER600",
    "ASIENTO PARAVOR BA 99 BLANCO H/NYLON": "TER601",
    "VILLAGE LAV. PIAZZA": "TER602",
    "BACHA DE APOYO 1 AG. 465X420X155 MM (A449)": "TER603",
    "BARI DEPOSITO APOYAR DUAL BL (DKW6F)": "TER604",
    "MONACO DEPOSITO APOYO 3/6L BL ROCA": "TER605",
    "MONACO INOD. LARGO BL 1061200000202 ROCA": "TER606",
    "103/B1P ARIZONA PLUS DUCHA P/EMBUTIR FV": "TER607",
    "CUBE SET 4 PIEZAS - NICK E": "TER608",
    "MALLA FIBRA VIDRIO 90 Grs.1 x 50 Mts.": "TER609",
    "Zócalo Eucafloor MDF laminado": "TER610",
    "PIL. DE PATIO 125 MM C/SAL 63MM 5ENT 40MM": "INSTS251",
    "10-351063540 PIL. DE PATIO 125 MM C/SAL 63MM 5ENT 40": "INSTS251",
    "SOBRE PILETA 110 C/5 ENTRADAS": "INSTS251",
    "6023-PILETA PATIO C/SIF.3S 160X110 AWADUCT": "INSTS252",
    "PVC BOCA ACC. 160 C/2 BOCAS REJILL": "INSTS253",
    "J.E. RAMAL 160X160 A 45 M-H 26035163 TIGRE": "INSTS254",
    "SUPLEMENTO ARO X 100MM O.V.CAM (cod.ARO) O.V. CAM": "INSTS255",
    "CAM - ARO- 10 CM": "INSTS255",
    "PROL. P/ CAM INSP TUBOFORTE": "INSTS256",
    "REJA 15X15 ACERO INOX CROMO CASAL": "INSTS257",
    "4003-PORTARREJILLA AC.INOX 15X15 REJILLA AWADUCT": "INSTS257",
    "TAPA 15X15 ACERO INOX CROMO CASAL": "INSTS258",
    "4005-PORTARREJILLA AC.INOX 15X15 T.CIEGA AWADUCT": "INSTS258",
    "Caño PVC Clásico 40x4x3.2": "INSTS259",
    "Caño PVC Clásico 50x 4 X 3.2": "INSTS260",
    "Purifica Dvigi 6 etapas": "INSTS261",
    "BOMBA CLOACAL MEC QSBJH 750B (PLASTICA)": "INSTS262",
    "HIDROFUGO TAMBOR X 200 LT.": "CONS274",
    "MASTROCRET XBOLSA 100 LTS": "CONS275",
    "MANTA HIDROFUGA ISSA 1.50 x30 MTS": "CONS276",
    "MEMBRANA HIDROFUGA AISLAHOME 1.50X20 MTS": "CONS277",
    "ARCILLA X 10 KG": "CONS278",
    "Contenedor estandar (de 5 m3 de capacidad)": "CONS279",
    "PFGAL C100X45X15X2.0 MM X 12 M": "P118",
    "FLEJE CINC 25 ancho 610 MM": "CH023",
    "ARANDELA CUADRADA GALV 35X35X3,2MM X 10": "A022",
    "ARANDELA CUADRADA GALV 80X80X3,2MM X 10": "A023",
    "Cable paralelo 2 x 0,5 mm": "INSTE124",
    "CAJA PREINSTALACION A.AC SAL.VERT LINEA XDURATOP": "CLIM121",
}

RECHAZAR = [
    "FLETE SIN CARGO",
    "PALLET DESCARTABLE",
    "PALLET VACIO [DEVOLUCION 100%]",
    # Vidrios: "eso no se que es el vidrio, directamente no lo cargues"
    "Cristal Templado 10 mm",
    "Laminado Extra Negro 3+3 mm",
    'Profilit "U Glass" medidas del perfil 0.26 x 3 m',
]


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv
    pend = sb.table("materiales_pendientes").select("id,descripcion_original") \
             .eq("estado", "PENDIENTE").execute().data
    from collections import defaultdict
    idx = defaultdict(list)
    for p in pend:
        idx[clave(p["descripcion_original"])].append(p["id"])

    def ids_de(texto):
        k = clave(texto)
        if k in idx:
            return idx[k]
        for kk, v in idx.items():
            if kk.startswith(k) or k.startswith(kk):
                return v
        return []

    plan, rech, faltan = [], [], []
    for texto, codigo in DECISIONES.items():
        ids = ids_de(texto)
        (plan.append({"texto": texto, "codigo": codigo, "ids": ids}) if ids
         else faltan.append(texto))
    for texto in RECHAZAR:
        ids = ids_de(texto)
        (rech.append({"texto": texto, "ids": ids}) if ids else faltan.append(texto))

    print(f"asignar: {len(plan)}   rechazar: {len(rech)}   faltantes: {len(faltan)}")
    for t in faltan:
        print(f"  FALTA: {t}")
    if faltan:
        raise SystemExit(1)

    if not aplicar:
        for p in plan:
            print(f"  {p['codigo']:9} <- {p['texto'][:58]}  ({len(p['ids'])})")
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
    ruta = os.path.join(DATA, "backup_tanda3_pendientes_2026-07-27.json")
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
        sb.table("conversion_unidades").insert(c).execute()
        print(f"+ conversion {c['codigo_material']} {c['unidad_comercial']}/{c['factor']}")

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
