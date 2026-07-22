# -*- coding: utf-8 -*-
"""Curado de aliases contaminados detectados con los materiales dispersos (22-07-2026).

Los 11 materiales que seguian dispersos DESPUES de limpiar presentaciones y
precios no eran un problema del matcher sino de datos: aliases aprendidos de
confirmaciones equivocadas (`origen=usuario_*` casi todos). El matcher les da
100 porque el alias LITERALMENTE dice el texto del otro producto — ninguna
guarda puede con eso.

Solo se tocan los casos donde el destino esta verificado contra el maestro.
Los ambiguos se listan al final y quedan para Pablo: adivinar el destino es
exactamente como nacio el caso A018/BROCAS.

Borrar un alias NO pierde el dato: la proxima vez que aparezca ese texto cae a
materiales_pendientes y se cura con criterio.

Correr:  cd api && python curar_aliases_dispersos_2026-07-22.py [--aplicar]
"""
import os, sys, json, datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
DATA = os.path.join(os.path.dirname(__file__), "data")

# (id, texto, codigo_actual, codigo_nuevo, motivo) — destino verificado en maestro
REASIGNAR = [
    ("4ab97146-7937-4e97-bcf8-a4602e0696a9", "hierro 12 mm",                        "A006", "CONS118", "hierro corrugado Ø12, no un anclaje"),
    ("aba7a476-6e59-49b2-8c48-d11c13844bdd", "hierro 12 mm acindar/bragado",        "A006", "CONS118", "hierro corrugado Ø12"),
    ("8861bb51-e4db-415a-befc-fd20fd4c3c68", "hierro 12.00 mm",                     "A006", "CONS118", "hierro corrugado Ø12"),
    ("e8c67865-4bda-4c37-acca-df831c2cb65b", "hierro adn 12mm",                     "A006", "CONS118", "hierro corrugado Ø12"),
    ("f2f87631-919f-4e40-b4c2-a594c2e12dae", "codo mh 50x90 duratop",               "INSTS036", "INSTS040", "es a 90, no a 45: CODO CLOACAL A 90 MH 50"),
    ("5fba4a5e-b1ac-485d-82a1-1b1d844fa211", "codo mh 63x45 duratop",               "INSTS036", "INSTS037", "es de 63, no de 50: CODO CLOACAL A 45 MH 63"),
    ("fd0fa832-1ef3-4a0a-98e0-c5da0e7bb39c", "codo mh 110x90 duratop",              "INSTS036", "INSTS042", "es 110 a 90: CODO CLOACAL A 90 MH 110"),
    ("82fe529a-6b5e-4eda-bbfa-68a446491238", "08-332050000 union doble 50 acqua system", "INSTS054", "INSTS124", "UNIÓN DOBLE / 50, no la cupla"),
    ("6983e454-039c-41aa-94d9-405f3cd9ab56", "flex.mallado a.inox. 1/2 x 30 latyn af2075 latyn", "INSTS202", "INSTS183", "mallado inox es AGUA; FLEXIBLE MALLADO 1/2x30"),
]

# (id, texto, codigo_actual, motivo) — producto distinto y sin destino en el maestro
BORRAR = [
    ("77f6396f-8574-4c4a-97d6-b913063c9c89", "caño 160 mm amanco std (900309)",     "INSTS019", "no existe CAÑO CLOACAL 160 en el maestro (hay 110/63/50/40)"),
    ("d2eb0c87-65b1-44c3-9971-74f268766c5d", "bulon de expansion fischer fwa 10 x 95", "A006",  "bulón de expansión, no varilla roscada 12*160"),
    ("46f6ae8f-deeb-4f29-b675-2141e62fc78b", 'varilla galv p/anclaje w1/2"x1000mm', "A006",     "otro anclaje: 1/2 x 1000mm"),
    ("7958c4d1-5c56-4abb-ba21-93455621e9b0", "reja acero 15 x 15 marco",            "INSTS008", "una reja no es una cámara de lodos"),
    ("5f2bd741-7fee-479c-9890-8d03943a32a6", "reja marco de acero 15x15 rma1515 waterplast", "INSTS008", "reja; matcheó por la marca WATERPLAST"),
    ("e6415a76-27e8-4e82-8950-4b513858d8d6", "waterplast",                          "INSTS008", "es la MARCA sola: captura cualquier producto Waterplast"),
    ("fa62d72a-0f4d-48e8-8157-a72219a221d6", "305 pileta doble semi lujo 64x34x18", "INSTS056", "pileta de cocina, no pileta de patio"),
    ("569d89bc-e138-45fd-8db3-d619430da7b7", "pileta doble semi lujo 64x34x18",     "INSTS056", "pileta de cocina"),
    ("af055372-9e97-4dc0-9f5b-9f84bd9e3d8f", "10-241160110 cupla red.de 160x110 duratop x", "INSTS054", "cupla de REDUCCIÓN 160x110, no cupla 50"),
    ("3a4a1db8-5bbc-482c-a7b2-2faff2d19559", "flex p/gabinete de gas 3 /",          "INSTS202", "texto truncado, no identifica medida"),
    ("14561376-94ec-4c40-914f-3de47740c6ad", "flex.mallado a.inox. 1/2 x 35 latyn af2075 latyn", "INSTS202", "es de 35 y es agua, no gas 30"),
    # NOTA: "spit varilla 12mm" (A006) estuvo en esta lista y se restauró.
    # El alias era LEGÍTIMO (Spit es marca de anclajes): la víctima del
    # sinónimo VARILLA→HIERRO CORRUGADO, no el culpable. El fix real fue el
    # contexto de anclaje en _prep_v2 (roscada/anclaje/spit/fischer/ftr/rgm
    # enmascara VARILLA antes de sinónimos). Reinsertado como id 082351b2-….
    # EST108 es AQUAPANEL 12MM, una placa cementicia. Estos tres son hierro y
    # varilla: confirmaciones equivocadas de tres proveedores distintos. No se
    # veian porque el filtro de aliases ambiguos los tapaba (el mismo texto
    # existia con mayor confianza en CONS118/A006 y ganaba esa copia) — o sea
    # que ese filtro venia ENMASCARANDO la contaminacion, no resolviendola.
    # Al borrar el de A006, el de EST108 salio a la superficie.
    ("817fca4d-9ace-40b1-9e16-5aa77bd7d51c", "spit varilla 12mm",                  "EST108", "AQUAPANEL no es una varilla"),
    ("e8a83d6f-2019-4767-9a56-f7914cb08589", "hierro adn 12mm",                    "EST108", "AQUAPANEL no es hierro"),
    ("46c0eb1d-fc14-4866-b6dc-cd5e32059f0f", "hierro adn 12mm sipar",              "EST108", "AQUAPANEL no es hierro"),
]

# Quedan para Pablo: el destino no es evidente y prefiero no inventarlo.
AMBIGUOS = [
    ("TER427",   "aro suplementario c/cera ideal",      "hay un hermano curado por vos a conf 96 ('aro base inodoro c/cera'); el precio difiere 12x, puede ser otro producto"),
    ("INSTS056", "pileta patio 110 chica duratop",      "¿es la de 3 entradas o una pileta chica distinta?"),
    ("INSTS054", "2013-manguito reparacion 40 awaduct", "manguito de 40 en la cupla de 50"),
    ("INSTS054", "29912726 cupla de reduccion de 40 x 50 tigre", "reducción 40x50, ¿tiene código propio?"),
    ("INSTS008", "camara registro lodos waterplast 180lts", "el maestro no distingue 100 vs 180 lts — ¿hay que abrir un código?"),
    ("INSTS202", "flexible gas aprobado ext. 1/2 x 42cm", "es de 42cm contra el maestro de 30"),
]


def backup(ids):
    filas = []
    for i in range(0, len(ids), 50):
        filas.extend(sb.table("material_denominaciones").select("*")
                     .in_("id", ids[i:i + 50]).execute().data or [])
    # Timestamp en el nombre: correr el script dos veces NO debe pisar el
    # backup anterior (pasó el 22-07 — la fila de "spit varilla 12mm" se
    # perdió del backup y hubo que reconstruirla del output del diagnóstico).
    stamp = datetime.datetime.now().strftime("%H%M%S")
    ruta = os.path.join(DATA, f"backup_aliases_dispersos_2026-07-22_{stamp}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"tomado": datetime.datetime.now().isoformat(timespec="seconds"),
                   "motivo": "curado de aliases contaminados - materiales dispersos",
                   "filas": len(filas), "datos": filas}, f, ensure_ascii=False, indent=1)
    print(f"backup -> {ruta}  ({len(filas)} filas)")
    return filas


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv

    print(f"=== REASIGNAR ({len(REASIGNAR)}) ===")
    for _, txt, de, a, motivo in REASIGNAR:
        print(f"  {de:9} -> {a:9}  {txt[:46]:46} | {motivo}")
    print(f"\n=== BORRAR ({len(BORRAR)}) ===")
    for _, txt, de, motivo in BORRAR:
        print(f"  {de:9}            {txt[:46]:46} | {motivo}")
    print(f"\n=== QUEDAN PARA PABLO ({len(AMBIGUOS)}) ===")
    for cod, txt, motivo in AMBIGUOS:
        print(f"  {cod:9}            {txt[:46]:46} | {motivo}")

    if not aplicar:
        print("\n(simulacion — correr con --aplicar)")
        raise SystemExit(0)

    todos = [r[0] for r in REASIGNAR] + [b[0] for b in BORRAR]
    backup(todos)

    for _id, txt, de, a, _ in REASIGNAR:
        # idx_den_unique (codigo_material, denominacion): si el destino ya tiene
        # el texto, la reasignacion violaria la constraint -> se borra el duplicado.
        # OJO el neq: sin excluir la propia fila, re-correr el script encontraba
        # el alias YA reasignado en el destino y lo borraba como "duplicado" —
        # paso el 22-07 y borro 8 de las 9 reasignaciones (restauradas por
        # restaurar_reasignados_2026-07-22.py).
        ya = sb.table("material_denominaciones").select("id") \
               .eq("codigo_material", a).eq("denominacion", txt) \
               .neq("id", _id).execute().data
        actual = sb.table("material_denominaciones").select("id") \
                   .eq("id", _id).execute().data
        if not actual:
            print(f"  {de}->{a} '{txt[:34]}': ya no existe (corrida previa), nada que hacer")
        elif ya:
            sb.table("material_denominaciones").delete().eq("id", _id).execute()
            print(f"  {de}->{a} '{txt[:34]}': el destino ya lo tenia, borrado el duplicado")
        else:
            sb.table("material_denominaciones").update({"codigo_material": a}) \
              .eq("id", _id).execute()
            print(f"  {de}->{a} '{txt[:34]}' reasignado")

    ids_borrar = [b[0] for b in BORRAR]
    for i in range(0, len(ids_borrar), 50):
        sb.table("material_denominaciones").delete().in_("id", ids_borrar[i:i + 50]).execute()
    print(f"\nborrados {len(ids_borrar)} aliases")
    print("Ojo: el cache de denominaciones tiene TTL de 5 min.")
