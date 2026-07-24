# Curado de datos pendiente — presentaciones y unidades

> Documento de handoff. Escrito el 2026-07-22 al cerrar la sesión donde se
> detectó el problema. Pensado para arrancar una sesión nueva sin contexto previo.
>
> **ACTUALIZADO 2026-07-22 (sesión de ejecución).** Los pasos 1 a 4 están
> hechos. Ver "Estado al cerrar" al final: el diagnóstico original resultó
> incompleto — las presentaciones eran una parte chica del problema.

---

## PROMPT PARA PEGAR EN LA SESIÓN NUEVA

```
Vectorai (carpeta local `presupuestor/`, repo HondaCB550/vectorai). Leé primero
CLAUDE.md y este archivo (CURADO_PENDIENTE.md).

Quiero cerrar el curado de datos de PRESENTACIONES Y UNIDADES en
precios_historicos. El diagnóstico ya está hecho — no hace falta rehacerlo, está
todo en la sección "Diagnóstico" de este archivo. Necesito que ejecutes la
sección "Trabajo a hacer", en orden, parando en cada punto donde diga DECISIÓN.

Contexto de entorno:
- La service key ya está en `api/.env`, así que el análisis local funciona igual
  que producción (antes estaba bloqueado por RLS).
- Para correr el pipeline sobre un PDF real sin navegador, usá el snippet de la
  sección "Cómo probar el pipeline sin navegador".
- Mis cuentas están marcadas `es_interno = true` en perfiles y quedan fuera de
  las métricas del tablero.

Reglas que no quiero que se rompan (están en CLAUDE.md pero las repito):
- Backup JSON en `api/data/backup_*.json` ANTES de tocar datos.
- Modificar SIEMPRE por IDs explícitos, nunca con un predicado amplio.
- Antes de pushear api/: `python -c "import main"`, `python
  test_extraccion_parsers.py`, `python test_matching_contaminacion.py`,
  `python test_conversion_unidades.py`.
- Un push a main auto-deploya a Vercel y Railway. Preguntame antes.
```

---

## Diagnóstico (ya hecho, no rehacer)

El "ahorro potencial" que mostraba Vectorai era ficticio. Investigando aparecieron
**tres problemas distintos**, no uno:

| # | Problema | Estado |
|---|---|---|
| 1 | Fórmula del ahorro comparaba contra "comprarle siempre al más caro" | **RESUELTO** — ahora es contra el promedio + guarda de dispersión 3x |
| 2 | Matches equivocados (cemento blanco → código del común) | **RESUELTO** — corregido en datos + guarda de calificadores en el matcher |
| 3 | **Presentaciones sin normalizar** | **PENDIENTE — es lo de este documento** |

### El problema pendiente

`precios_historicos` mezcla presentaciones del mismo material sin normalizar: el
mismo tornillo cotizado por unidad, por caja de 100 y por caja de 6.000, todos
guardados como si fueran precios comparables.

Caso testigo, **T005 — TEL ALAS 8*1 1/4, descripción del maestro "(6.000 unidades)"**:

| Texto original del proveedor | Precio | Presentación real |
|---|---|---|
| `CAJA ALAS C/ESTRIAS - 8 X 1,1/4 X 6.000` | $348.804 | caja de 6.000 |
| `TORN ALAS P/SUPERB. 8 x 1-1/4 x 100 u` | $4.265 | caja de 100 |
| `ALAS CON ESTRIAS 8 X 1,1/4 X 100` | $6.260 | caja de 100 |
| `TORNILLO ALAS 8X1 1/4" (BOLSA X 100)- TEL` | $3.310 | bolsa de 100 |

Brecha resultante: **1.003.075%**. Este material solo hace que el promedio de
brecha del Índice dé 310.645.708%.

### Por qué no se resolvió en la sesión anterior

El mecanismo ya existe (`conversion_unidades` + modo `'un'` en
`_convertir_unidad()`, main.py), pero **el regex que detecta el pack se come la
mitad de los formatos reales**:

```python
# main.py, cerca de _convertir_unidad
_RE_POR_UNIDADES = re.compile(
    r"(?:x|por)\s*(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(?:un\b|u\b|unid\w*)", re.I)
```

Exige el token `un` / `u` / `unid` DESPUÉS del número. Contra los textos de arriba:

- `x 100 u` → detecta
- `X 6.000` → detecta, pero solo por el fallback que busca el `factor` literal
- `X 100` → **NO detecta**
- `(BOLSA X 100)` → **NO detecta**

Cargar la conversión de T005 sin tocar el regex corregiría 2 de 4 cotizaciones y
dejaría 3 mal. Un arreglo parcial sobre precios es peor que ninguno: queda
mezclado lo normalizado con lo que no, y ya no se distingue.

### Alcance

- **248** materiales cotizados por 2+ proveedores.
- **65 (26%)** tienen el precio más alto a más de 3x el más bajo → sospechosos.
- De los 15 peores, **solo T005 tiene la presentación codificada en el maestro**.
  Los otros 14 (UPN U 60, EIFS ARANDELA, CUPLA 50, HEX 14*1/2, CÁMARA DE LODOS,
  FRISELINA ROLLO, CANTONERA, ANCLAJES…) **no la tienen**: el factor no es
  derivable automáticamente y hay que sacarlo del texto del proveedor o de tu
  conocimiento del producto.

**Ojo**: no todo lo disperso es un error de presentación. En T005 apareció además
`TORN ALAS P/SUPERB. 10 x 1-5/8 x 100 u` — un tornillo **10 x 1-5/8** matcheado a
un material que es **8 x 1,1/4**. Eso es un match equivocado, no una presentación.
Hay que separar las dos cosas antes de aplicar factores.

---

## Trabajo a hacer

### Paso 1 — Ampliar la detección de pack (código)

Ampliar `_RE_POR_UNIDADES` para que capte `X 100`, `(BOLSA X 100)`, `CAJA X 100`
sin exigir el token "un".

**DECISIÓN**: el riesgo es que se vuelva demasiado laxo y capture números que no
son packs (medidas: `8 X 1,1/4`, `100MMX25`, `20MM * 400`). Definir con Pablo qué
contextos cuentan como pack. Sugerencia de partida: exigir una palabra de
presentación cerca (`caja`, `bolsa`, `pack`, `bulto`, `x N un`) o que el número
sea "redondo" (≥25 y múltiplo de 25/50/100).

Red de seguridad: `api/test_conversion_unidades.py` (8 tests, todos en verde hoy).
**Agregar tests con los 4 textos reales de T005 ANTES de tocar el regex** — que
fallen primero y pasen después.

### Paso 2 — Separar matches equivocados de presentaciones

Para cada uno de los 65 materiales dispersos, mirar `presupuesto_items.texto_original`
y clasificar en:

- **(a) presentación distinta** → va a `conversion_unidades`
- **(b) producto distinto mal matcheado** → reasignar código o mandar a pendientes,
  como se hizo con el cemento (ver `api/data/backup_matches_cemento_2026-07-22.json`)
- **(c) basura** → eliminar

SQL para regenerar la lista:

```sql
with disp as (
  select codigo_material, min(precio) mn, max(precio) mx,
         count(distinct proveedor) n_prov
  from precios_historicos where precio > 0
  group by codigo_material
  having count(distinct proveedor) >= 2 and max(precio) > 3*min(precio)
)
select d.codigo_material, m.denominacion_principal, m.descripcion,
       d.mn, d.mx, round(d.mx/d.mn,0) ratio, d.n_prov,
       (c.codigo_material is not null) ya_tiene_conversion
from disp d
join materiales_validados m on m.codigo = d.codigo_material
left join conversion_unidades c on c.codigo_material = d.codigo_material and c.activo
order by d.mx/d.mn desc;
```

Y para ver los textos originales de un material:

```sql
select distinct pi.texto_original, pi.precio, pi.cantidad, pr.proveedor_detectado
from presupuesto_items pi join presupuestos pr on pr.id = pi.presupuesto_id
where pi.codigo_material = 'T005' order by pi.precio desc;
```

### Paso 3 — Cargar las conversiones

Tabla `conversion_unidades`: `codigo_material`, `unidad_comercial`, `factor`,
`unidad_base`, `descripcion`, `activo`.

Tres modos (documentados en el docstring de `_convertir_unidad`):

- `'m'` → canónico es la tira/rollo. `pu×factor`, `cant÷factor`. Caños, cables.
- `'un'` → canónico es el **precio por unidad** (regla de Pablo 20-07-2026). El
  proveedor cotiza por pack → se divide (`pu÷n`, `cant×n`). Tornillería.
- `'ml'` → canónico es el metro lineal. Chapas.

**DECISIÓN por material**: el factor sale del texto del proveedor o del
conocimiento de Pablo. No inventarlo.

El cache tiene **TTL de 5 minutos**: tras insertar, esperar o reiniciar para ver
el efecto.

### Paso 4 — Recalcular los precios ya guardados

Las conversiones aplican al procesar. Los ~4.800 precios ya en
`precios_historicos` quedaron sin normalizar (`conversion_aplicada` está en null
en todos los casos dispersos).

**DECISIÓN**: ¿se recalculan los históricos existentes, o se deja que se corrijan
solos a medida que entren presupuestos nuevos? Recalcular es más prolijo pero toca
4.800 filas; dejarlo correr es más seguro pero mantiene el Índice sucio un tiempo.

### Paso 5 — Recalcular el Índice y actualizar la campaña

Con los datos limpios, recalcular la brecha del Índice y **actualizar las piezas
de marketing**, que hoy dicen **39%**:

- `IDENTIDAD.md:45` — dice "promedio", debería decir mediana
- `marketing/emails_bienvenida.{md,html}` — dice "en promedio un 39%"
- `marketing/guia_5_errores.{md,html}` — dice "mediana de 39%" (el único correcto)
- `marketing/guion_video_demo.{html}` — dice "promedio real"
- `marketing/conceptos_reels.{md,html}` — "39% de diferencia promedio"
- `CHECKLIST_LANZAMIENTO.md:31,40` — pide verificar el dato antes de narrar

**Medición del 2026-07-22 (con los datos todavía sucios):**

| Métrica | Valor |
|---|---|
| Materiales multi-proveedor | 248 |
| Sanos (máx ≤ 3× mín) | 183 |
| Brecha **mediana** con guarda | **43,5%** |
| Brecha mediana sin guarda | 61,6% |
| Brecha promedio con guarda | 57,9% |
| Brecha promedio sin guarda | **310.645.708%** ← inservible |

**Nunca publicar el promedio.** Solo la mediana, y aclarando la muestra.

---

## Cómo probar el pipeline sin navegador

No se pueden subir archivos desde la herramienta de browser. Para correr
extracción + matching sobre un PDF real con el corpus completo de aliases:

```python
import sys, importlib.util
sys.path.insert(0, r'C:\Pablo\presupuestor\api')
import main                      # PRIMERO: si no, se rompe el import de matching

spec = importlib.util.spec_from_file_location(
    "ext", r'C:\Pablo\presupuestor\api\matching\extraer_pdf_texto.py')
ext = importlib.util.module_from_spec(spec); spec.loader.exec_module(ext)

dens = main._get_denominaciones()        # corpus real desde Supabase
r = ext.extraer("CAROSIO - GRUESO.pdf")
for it in r["items"]:
    ms = main._match_v2(it["desc"], dens, top_n=3)
    print(it["desc"][:45], "->", ms[0]["codigo_material"], ms[0]["nivel"]) if ms else None
```

PDFs reales de prueba: `api/*.pdf` y `C:\Pablo\Cotizaciones\Para cargar\.pdf\`.

Resultado de referencia (2026-07-22): CAROSIO 26 extraídos = 21 auto + 5 dudoso,
SAUCE 18 = 17 auto + 1 dudoso. Las cuentas deben cerrar.

---

## Estado al cerrar (2026-07-22, sesión de ejecución)

### Lo que resultó ser el problema

El diagnóstico apuntaba a presentaciones. Al clasificar los 65 materiales
dispersos aparecieron **tres problemas de tamaños muy distintos**:

| Causa | Materiales | |
|---|---|---|
| Presentación sin normalizar | ~5 | lo que este documento asumía que era todo |
| **Match equivocado** | **~54** | el grueso real |
| Extracción rota | ~6 | textos truncados con precios absurdos |

Los dos hallazgos de fondo:

1. **`precios_historicos` no guardaba el texto del proveedor.** Sin ese texto
   `_convertir_unidad` no puede saber qué presentación se cotizó, así que
   recalcular una conversión sobre una fila ya guardada era imposible. De 4.807
   filas, solo 1.004 enganchaban con un ítem por precio exacto (el IVA y el
   descuento son por archivo y se aplican en el medio).
2. **Un PDF entero se leyó con el total de línea en la columna de precio
   unitario.** 34 ítems, verificable al centavo: `precio_malo == precio_bueno *
   cantidad / 1.105`. Eran los que disparaban las brechas de millones por
   ciento, no las presentaciones.

### Lo que se hizo

- **`_detectar_pack()`** (main.py): detección de pack en 3 capas — token de
  unidad, palabra de presentación, y número redondo al final del texto. Detecta
  las 4 formas en que los proveedores cotizan T005 (antes 2 de 4).
- **Modo `'kg'`** en `_convertir_unidad`: canónico $/kg para bolsas. Manda el
  peso del texto, no el factor del maestro (hay basecoat de 25 y de 30 kg).
- **4 conversiones nuevas**: T005 (un/6000), TER114 (un/100), CONS104 (kg/5),
  TER482 (kg/25). Cada factor verificado contra el precio del mismo material
  que ya venía en la unidad canónica.
- **`precios_historicos.texto_original` y `.origen`** (migración
  `precios_historicos_texto_original_y_origen`). `origen='pipeline'` = fila con
  texto, matcher y conversiones actuales, auditable → es la única que entra al
  Índice. `origen='legacy'` = las 4.807 viejas, se conservan pero quedan fuera.
  Los 3 sitios de insert de main.py y `/precios-historial` ya lo respetan.
- **Reparación de ítems corruptos**: 34 eliminados (total leído como unitario) y
  4 normalizados (cantidades 0.01/0.025 que quedaron de la corrección manual del
  13-07 y hacían que la conversión dividiera dos veces).
- **Reconstrucción**: 464 filas `pipeline` desde `presupuesto_items`, cada una
  re-matcheada y re-convertida con el código de hoy.
- Tests: 21/21 conversión (13 nuevos), 9/9 contaminación, parsers sin fallos.

### El número del Índice cambió

Comparación apples-to-apples (mediana con guarda de dispersión 3x):

| | Antes (sucio) | Ahora (capa limpia) |
|---|---|---|
| Materiales multi-proveedor | 248 | **120** |
| Sanos (máx ≤ 3× mín) | 183 (74%) | **109 (91%)** |
| **Brecha mediana con guarda** | 43,5% | **27,4%** |
| Brecha mediana sin guarda | 61,6% | 32,1% |
| Brecha promedio | 310.645.708% | 129,8% |

La muestra es la mitad pero está sana el 91% en vez del 74%. **El promedio
sigue sin ser publicable.** La campaña dice 39% y todavía no se tocó.

### Segunda tanda (22-07, misma fecha): matcher + aliases — HECHA

Los "11 bugs vivos del matcher" resultaron ser dos cosas distintas:

1. **Aliases contaminados** (la mayoría): confirmaciones equivocadas de
   usuario. `CAÑO 160 MM AMANCO` como alias del caño de 110, `codo mh 110x90`
   en el codo a 45 de 50, rejas Waterplast y la marca sola "waterplast" en
   CÁMARA DE LODOS, hierro de obra en ANCLAJES, hierro y varilla en EST108
   (AQUAPANEL — el filtro de ambiguos los ENMASCARABA, no los resolvía).
   Curados por ID con `curar_aliases_dispersos_2026-07-22.py`: 9 reasignados,
   15 borrados. Ojo: el chequeo de duplicados tenía un bug (sin `neq` a la
   propia fila, re-correr el script borraba lo ya reasignado — pasó y se
   restauró con `restaurar_reasignados_2026-07-22.py`).
2. **Dos bugs reales del matcher**, arreglados con tests (18/18):
   - Calificador `doble` en `_CALIFICADORES` + el sinónimo `UNION DOBLE→UNION`
     eliminado (era específico→genérico, la clase prohibida). La guarda ahora
     compara sobre el texto CRUDO (los sinónimos podían borrar justo el
     calificador). "simple" NO se agregó a propósito: capaba 3 matches
     correctos y ninguno equivocado (en sanitaria "simple" es el default que
     el maestro omite, y "unión simple" ES la cupla).
   - Contexto de anclaje en `_prep_v2`: roscada/anclaje/spit/fischer/ftr/rgm
     enmascaran VARILLA antes del sinónimo VARILLA→HIERRO CORRUGADO. Sin esto
     "spit varilla 12mm" capturaba todo el hierro de 12, y la varilla roscada
     Fischer se iba a hierro aleteado.

También: `reconstruir_precios_2026-07-22.py` ahora matchea con `top_n=3` como
producción (con `top_n=1` la ventana de fuzz_process quedaba en 3 candidatos y
los aliases largos con token_set crudo 100 la llenaban antes que los buenos).

**Estado final de la capa limpia: 121 multi-proveedor, 117 sanos (96,7%),
mediana con guarda 26,9% / sin guarda 27,6%** (que casi coincidan = ya no hay
outliers estructurales). Los 4 dispersos que quedan son los casos listados en
AMBIGUOS del script de curado (decisiones de catálogo, no bugs).

### Lo que queda pendiente

1. **Actualizar el dato de campaña PARA LO PRÓXIMO** (decisión de Pablo 22-07:
   lo ya publicado queda como está). El número nuevo es **mediana 27%** (26,9
   con guarda / 27,6 sin, sobre 121 materiales multi-proveedor, 96,7% sanos).
   No es buscar-y-reemplazar: hay ~29 archivos con "39%" (`grep -rl "39%"
   IDENTIDAD.md marketing/ CHECKLIST_LANZAMIENTO.md`), e
   `indice_ejemplos_2026-07.{md,html}` tienen tablas de materiales que hay que
   recalcular con la capa `origen='pipeline'`. **Nunca publicar el promedio.**
2. **6 decisiones de catálogo** (lista AMBIGUOS en
   `curar_aliases_dispersos_2026-07-22.py`): aro suplementario vs kit inodoro,
   pileta patio 110 chica, manguito 40 y cupla reducción 40x50 en CUPLA 50,
   cámara de lodos 180 vs 100 lts, flexible gas 42cm vs 30.
3. **T011 (HEX 14*1/2 MAX)**: $9.824 es claramente una caja pero no hay texto
   del proveedor de donde sacar el factor. Sin resolver a propósito.
4. **Duplicación en las filas legacy** de `precios_historicos` (la misma
   cotización 4-5 veces). Fuera del Índice, sin tocar.
5. **`api/data/backup_precios_historicos_2026-07-22.json`** tiene las 4.807
   filas originales por si hay que revertir.

### Scripts de esta sesión (api/)

`backup_curado_presentaciones_2026-07-22.py` · `cargar_conversiones_2026-07-22.py` ·
`reclasificar_dispersos_2026-07-22.py` · `reparar_items_corruptos_2026-07-22.py` ·
`reconstruir_precios_2026-07-22.py` · `aplicar_curado_dispersos_2026-07-22.py`
(este último quedó **sin aplicar**: lo reemplazó la reconstrucción)

---

## CIERRE (23-07-2026) — todo lo pendiente quedó resuelto

Los puntos 1, 2 y 3 de arriba se cerraron:

1. **Campaña actualizada a 27%** (commit `4ae39e5`): IDENTIDAD, emails, guía,
   guion de video, reels y sus .html. Lo ya publicado quedó como estaba.
   `indice_ejemplos_2026-07.md` ganó la sección RE-MEDICIÓN POST-CURADO con la
   canasta re-medida (mediana de la canasta pesada: 44%).
2. **Las 6 decisiones de catálogo, respondidas por Pablo y aplicadas**
   (`aplicar_decisiones_catalogo_2026-07-23.py`, backup
   `backup_decisiones_catalogo_2026-07-23.json`):
   - Aro vs kit inodoro: SEPARADOS. Nuevo material **TER597 ARO SUPLEMENTARIO
     DE CERA | INODORO** con los 3 aliases de aro; TER427 quedó como kit y su
     descripción pasó a "TORNILLOS + TARUGOS". ⚠ El primer intento usó TER562
     creyéndolo libre — la lectura del maestro cortó en 1000 filas (la trampa
     de paginación de CLAUDE.md); TER562 era un basecoat de un curado previo.
     La guarda de re-run del script lo frenó antes de tocar nada. El código
     libre se busca con `select max(codigo)` por SQL, nunca paginando a mano.
   - Pileta patio 110 chica Duratop = la de 3 entradas (INSTS056), conf 96.
   - Manguito reparación 40 = CUPLA 40 (INSTS055; el destino ya tenía el
     texto, se borró el duplicado).
   - Cupla reducción 40x50 Tigre: sin código a propósito → alias borrado, si
     reaparece cae a pendientes.
   - Cámara de lodos: es UNA sola (100 y 180 lts unificadas en INSTS008).
   - Flexible gas 1/2 x 42cm → vinculado al de 30 (INSTS202), conf 96.
3. **T011 resuelto con evidencia**: la foto `MAD. LOBOS - STEEL - HOJA 2.jpg`
   dice "TEL-HEX T2 14X1 C/ARA X 100 OFERTA" a $10.855,70 bonificado, que
   ÷1,105 = $9.824,16 — el precio guardado, exacto. Es caja de 100 (≈$98/u,
   no $9/u): conversión `T011 un/100` cargada.

**Estado final del Índice (capa pipeline reconstruida, 460 filas):**
121 materiales multi-proveedor, **97,5% sanos**, mediana **27,4%** — el 27%
publicado queda válido. Los 3 dispersos restantes (CUPLA 50 3,7x, TAPA HEMBRA
50 3,3x, BASECOAT 3,1x) son dispersión real de marca/mercado, no errores.

Sigue abierto solo el punto 4 (duplicación en filas legacy, fuera del Índice,
sin urgencia). Este documento queda como registro histórico.

---

## Contexto de la sesión anterior

Cambios ya deployados (no rehacer):

- Ahorro contra promedio + guarda de dispersión 3x (`_ahorro_vs_promedio`, main.py)
- Guarda de calificadores excluyentes blanco/refractario/cementicia en `_match_v2`,
  comparando contra el **nombre canónico del material**, no contra el alias
- 4 tests nuevos en `test_matching_contaminacion.py` que meten el alias
  contaminado a propósito (los que ya existían corrían sobre datos saneados y
  pasaban sin ninguna guarda: no detectaban el fallo que decían cubrir)
- Burbuja "Total de la compra" en los KPIs
- Lista de compras exportable en PDF (una página por proveedor) y JPG (un archivo
  suelto por proveedor, sin zip)
- Cuentas internas excluidas del tablero vía `perfiles.es_interno`
- Fix del conteo de pendientes en la RPC `admin_metrics` (comparaba `'pendiente'`
  contra `'PENDIENTE'` y siempre daba 0)
