# -*- coding: utf-8 -*-
"""Aplica las 7 decisiones de catalogo de Pablo (23-07-2026).

Cierran los AMBIGUOS que dejo el curado del 22-07 (ver
curar_aliases_dispersos_2026-07-22.py). Decisiones textuales de Pablo:

1. ARO vs KIT — separar. El kit de fijacion son los dos tornillos especiales
   con tarugos; el aro suplementario de cera va aparte (parte interior del
   inodoro, puede valer mucho mas). Se crea TER597 ARO SUPLEMENTARIO DE CERA
   (TER597 = max(TER)+1 por SQL sin paginar: el primer intento uso TER562
   creyendolo libre porque la lectura de openpyxl del maestro corto en 1000
   filas — la trampa de paginacion documentada en CLAUDE.md; TER562 es un
   basecoat de un curado anterior y la guarda de re-run lo salvo)
   y se mueven ahi los 3 aliases de aro. TER427 queda como kit y su
   descripcion pasa de "CERA + TORNILLOS + CINTA" a "TORNILLOS + TARUGOS"
   para que el sintetico no siga conteniendo "cera".
2. Pileta patio 110 chica Duratop = la de 3 entradas (INSTS056). Confirmado:
   confianza 96 (curado humano).
3. Manguito reparacion 40 awaduct = cupla de 40 -> INSTS055 (existia).
4. Cupla de reduccion 40x50 Tigre: no tiene codigo. Se borra el alias de
   INSTS054; si reaparece cae a pendientes.
5. Camara de lodos 100 y 180 lts: es UNA sola (INSTS008). Los aliases de 180
   quedan donde estan, confirmados a 96.
6. Flexible gas 1/2 x 42cm -> vinculado al de 30 (INSTS202), confirmado a 96.
7. T011 HEX 14*1/2: la foto del presupuesto de Maderera Lobos (jun-26) dice
   "TEL-HEX T2 14X1 C/ARA X 100 OFERTA" $10.855,70 bonif; /1,105 = $9.824,16
   = el precio guardado, exacto. Es CAJA DE 100 -> conversion un/100.

Correr:  cd api && python aplicar_decisiones_catalogo_2026-07-23.py [--aplicar]
"""
import os, sys, json, datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")

NUEVO_MATERIAL = {
    "codigo": "TER597",
    "categoria": "I. SANITARIA",          # misma que TER427
    "denominacion_principal": "ARO SUPLEMENTARIO DE CERA",
    "descripcion": "INODORO",
    "validado_por": "pablo_2026-07-23",
}

ALIASES_ARO = [  # (id, texto) — se mueven TER427 -> TER597
    ("825ea032-767e-4e02-a43e-e292fa64f49e", "aro base inodoro c/cera"),
    ("ae76c830-ac80-4e6e-9176-ae8acb6db657", "aro suplementario c/cera ideal"),
    ("9153c1b9-0542-454d-833a-328a55030be5", "conexion inodoro al piso aro (1568) ideal"),
]

REASIGNAR = [  # (id, texto, de, a)
    ("aa30d7da-44f9-481e-aea5-c6a564891eff", "2013-manguito reparacion 40 awaduct", "INSTS054", "INSTS055"),
]

BORRAR = [  # (id, texto, de)
    ("d4f82982-b04e-4d1e-8fc8-b66d46ec89ac", "29912726 cupla de reduccion de 40 x 50 tigre", "INSTS054"),
]

CONFIRMAR_96 = [  # (id, texto, codigo) — decision humana, sube la confianza
    ("ae7bb3ae-5744-476b-9817-fb617dcd58a2", "pileta patio 110 chica duratop", "INSTS056"),
    ("330f54cd-0d16-459f-b866-a60f46596ccb", "flexible gas aprobado ext. 1/2 x 42cm", "INSTS202"),
    ("d64242dc-4695-489d-a51d-c2a0db15579d", "camara registro lodos waterplast 180lts", "INSTS008"),
    ("ef1f38e9-382e-4bfd-a651-ada44f345e33", "cr180 camara registro lodos waterplast 180lts", "INSTS008"),
]

CONVERSION_T011 = {
    "codigo_material": "T011", "unidad_comercial": "un", "factor": 100,
    "unidad_base": "UN",
    "descripcion": "caja de 100 (TEL-HEX T2 14X1 C/ARA, foto Maderera Lobos jun-26)",
    "activo": True,
}


def backup():
    ids = [a[0] for a in ALIASES_ARO + REASIGNAR + BORRAR + CONFIRMAR_96]
    filas = sb.table("material_denominaciones").select("*").in_("id", ids).execute().data or []
    ter427 = sb.table("materiales_validados").select("*").eq("codigo", "TER427").execute().data or []
    ruta = os.path.join(DATA, "backup_decisiones_catalogo_2026-07-23.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"tomado": datetime.datetime.now().isoformat(timespec="seconds"),
                   "motivo": "7 decisiones de catalogo de Pablo 23-07",
                   "aliases": filas, "ter427_previo": ter427}, f, ensure_ascii=False, indent=1)
    print(f"backup -> {ruta}  ({len(filas)} aliases + TER427)")


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv

    print("PLAN:")
    print(f"  + alta TER597: {NUEVO_MATERIAL['denominacion_principal']} | {NUEVO_MATERIAL['descripcion']}")
    print("  ~ TER427 descripcion: CERA + TORNILLOS + CINTA -> TORNILLOS + TARUGOS")
    for _, t in ALIASES_ARO:
        print(f"  > TER427 -> TER597   {t}")
    for _, t, de, a in REASIGNAR:
        print(f"  > {de} -> {a}   {t}")
    for _, t, de in BORRAR:
        print(f"  x {de}   {t}")
    for _, t, c in CONFIRMAR_96:
        print(f"  conf 96 [{c}]   {t}")
    print(f"  + conversion T011 un/100")

    if not aplicar:
        print("\n(simulacion — correr con --aplicar)")
        raise SystemExit(0)

    # Guardas de re-ejecucion
    if sb.table("materiales_validados").select("codigo").eq("codigo", "TER597").execute().data:
        print("\nTER597 ya existe. Abortado (parece un re-run).")
        raise SystemExit(1)
    if sb.table("conversion_unidades").select("id").eq("codigo_material", "T011").execute().data:
        print("\nT011 ya tiene conversion. Abortado (parece un re-run).")
        raise SystemExit(1)

    backup()

    sb.table("materiales_validados").insert(NUEVO_MATERIAL).execute()
    print("TER597 creado")
    sb.table("materiales_validados").update({"descripcion": "TORNILLOS + TARUGOS"}) \
      .eq("codigo", "TER427").execute()
    print("TER427 renombrado")

    for _id, t in ALIASES_ARO:
        sb.table("material_denominaciones").update({"codigo_material": "TER597"}).eq("id", _id).execute()
    print(f"{len(ALIASES_ARO)} aliases de aro movidos a TER597")

    for _id, t, de, a in REASIGNAR:
        ya = sb.table("material_denominaciones").select("id") \
               .eq("codigo_material", a).eq("denominacion", t).execute().data
        if ya:
            sb.table("material_denominaciones").delete().eq("id", _id).execute()
            print(f"{de}->{a} '{t[:30]}': destino ya lo tenia, duplicado borrado")
        else:
            sb.table("material_denominaciones").update({"codigo_material": a}).eq("id", _id).execute()
            print(f"{de}->{a} '{t[:30]}' reasignado")

    for _id, t, de in BORRAR:
        sb.table("material_denominaciones").delete().eq("id", _id).execute()
    print(f"{len(BORRAR)} alias borrado (cupla reduccion, sin codigo)")

    for _id, t, c in CONFIRMAR_96:
        sb.table("material_denominaciones").update({"confianza": 96}).eq("id", _id).execute()
    print(f"{len(CONFIRMAR_96)} aliases confirmados a 96")

    sb.table("conversion_unidades").insert(CONVERSION_T011).execute()
    print("conversion T011 un/100 cargada")
    print("\nListo. Cache TTL 5 min.")
