# CLAUDE.md — VectorAI

SaaS comparador de presupuestos de construcción: el usuario sube PDFs/fotos/planillas de sus proveedores, el sistema extrae los ítems, los matchea contra un maestro de materiales y genera una comparativa de precios con export a Excel/PDF/JPG.

## Arquitectura y deploy

| Pieza | Tech | Hosting | Deploy |
|---|---|---|---|
| Frontend | Next.js (`frontend/`) | Vercel, proyecto **"vectorai"** (team bontempopablo) | `git push origin main` → auto |
| API | FastAPI (`api/main.py`) | Railway, proyecto **"desirable-perception"** | `git push origin main` → auto |
| DB | Supabase, proyecto **aetwdwvctowannnbelwb** ("vectorai") | — | migraciones via SQL Editor / MCP |

- Repo GitHub: `HondaCB550/vectorai`. La carpeta local se llama `presupuestor` pero el proyecto en todos lados es **vectorai**.
- Dominios: `vectorai.com.ar` / `www.vectorai.com.ar` (Vercel). API: `vectorai-production-1f06.up.railway.app`.
- Verificar deploys: Vercel MCP (`get_project` → `latestDeployment.readyState`), Railway CLI (`railway status`, `railway logs`).
- `GET /health` reporta: master_items, aliases_v2, sinonimos_bd, grupos_marcas_bd, ocr{motor,key_len,key_hash}, sheets_export.

## Variables de entorno (Railway)

- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (formato nuevo `sb_secret_...`; **necesaria para escribir** — la anon `SUPABASE_KEY` sola hace fallar todos los inserts por RLS, bug histórico arreglado 02-07-2026).
- `ANTHROPIC_API_KEY` — para OCR de fotos (Claude Vision). El código la sanitiza con `_api_key_limpia()` (quita no-ASCII del pegado).
- `MERCADOPAGO_ACCESS_TOKEN`, `FRONTEND_URL`, `OCR_PROVIDER` (claude|google).
- **Nunca imprimir valores de keys** en tool output; para diagnosticar, decodificar solo el claim `role` del JWT o testear funcionalmente (ver scripts patrón en el skill vectorai-ops).

## Modelo de datos (Supabase)

Núcleo del matching:
1. `materiales_validados` (~937) — maestro. **La identidad está partida en dos campos**: `denominacion_principal` (genérico, ej. "CABLE") + `descripcion` (lo que distingue, ej. "2,5MM * 100"). En UI mostrar siempre ambos.
2. `material_denominaciones` (~5.600) — aliases de texto (flywheel: crece con cada confirmación). Campos: codigo_material, denominacion, origen, confianza (90 migración / 96 curado humano), frecuencia_encontrada.
3. `materiales_pendientes` — cola de sin-match para revisión en /app/admin.
4. `precios_historicos` — precio por material/proveedor/fecha, se alimenta automático (ítems con score ≥85) y al confirmar. Columna `moneda` para USD.
5. `sinonimos`, `grupos_marcas` — normalización del matching.

Negocio: `perfiles` (plan free/advance/pro, `usos_mes`/`limite_mes`/`mes_usos` — NO usos_hoy), `presupuestos` + `presupuesto_items` (cada PDF procesado y sus líneas), `proveedores`, `conversion_unidades`.

## Matching v2 — reglas

- Umbrales: **auto ≥85 / dudoso 60-84 / sin match <60**. Score: token_set + partial + bonus numérico + 6pts por grupo de marca.
- `_get_denominaciones()` cachea aliases **5 min** — tras tocar la tabla, esperar TTL o reiniciar para ver el efecto.
- Aliases sin palabra real de 4+ letras se filtran (basura tipo "m3", "3*6").
- **Nunca aprender aliases basura**: el caso A018/BROCAS (imports de borradores ferrocenter/gramabi colgaron placas OSB, yeso y tapas de un código de brocas) rompió el matching de OSB. Al detectar aliases sospechosos: backup JSON en `api/data/backup_aliases_*.json` → borrar/reasignar **por IDs explícitos**, nunca con predicado amplio.
- Frontend dudosos: alternativas deduplicadas por código, muestran `denominacion — descripcion`, y existe la opción sentinel `SIN_MATCH` ("Ninguno corresponde") que manda el ítem a pendientes en vez de aprender un código erróneo.
- **Guarda de precio**: si el documento traía total de línea y `pu×cant` no cierra contra él (tolerancia 1%), el ítem baja a REVISAR aunque el score sea ≥85 (`precio_sospechoso: true` en la respuesta; badge rojo en el tab Dudosos). Un precio roto nunca entra solo a precios_historicos.

## Extracción (api/matching/)

- `extraer_pdf_texto.py` — cascada de 4 métodos: tablas_bordes → tablas_texto → regex por proveedor (RE_ENSECO, RE_VIEJOBUENO, RE_CAROSIO_PRESU, RE_ALFONSIN, RE_BAUKRAFT, RE_CAROSIO, RE_EUROPEO — el orden importa: los específicos van antes que los genéricos porque RE_BAUKRAFT/RE_CAROSIO matchean líneas de Viejo Bueno con la desc contaminada) → lineas_heuristico. Se elige por `_calidad()` (descripciones reales + consistencia pu×cant≈total).
  - RE_CAROSIO_PRESU (ERP "Presupuesto centro" de Carosio sanitarios): `COD SKU DESC PU CANT UMED TOTAL` americano. Las líneas con texto interleaveado (glitch del ERP) no cumplen el patrón y quedan afuera solas.
  - RE_ALFONSIN: `CANT [COD] DESC P.LISTA -X% P.UNIT TOTAL` europeo; código opcional (alnum≥5 con dígito); pu = precio ya descontado.
  - RE_VIEJOBUENO: `IT CANT.CODIGO DESC MARCA P.LISTA [desc%×3] P.VENTA TOTAL` americano; cantidad y código vienen pegados (`1.00411110001`); pu = precio de venta.
- `lineas_heuristico` exige que el último token sea precio bien formateado (RE_PRECIO_EOL): `9.800,00` sí, `9.800.00` no.
- `_fix_split_words` colapsa letras sueltas ("H ORMIGON"→"HORMIGON") — efecto colateral: "PERFIL EST. C GALV." → "CGALV." (la C de perfil C se pega).
- `_colapsar_tokens_doblados` arregla PDFs que duplican caracteres en negrita ("TToottaall").
- `extraer_imagen.py` — fotos vía Claude Vision (json_schema) o Google Vision OCR según `OCR_PROVIDER`. También `pdf_sin_texto()` + `extraer_pdf_escaneado()`: PDFs escaneados se renderizan con pypdfium2 (scale=2, JPEG q85, máx 8 págs) y pasan página por página por el mismo motor. main.py hace el fallback solo si `extraer()` dio 0 ítems Y el PDF no tiene capa de texto (~19s/página de visión — si tiene texto pero 0 ítems es un formato nuevo para regex, no se gasta visión).
- `extraer_hoja.py` — .xlsx/.csv por aliases de encabezado. `descargar_gsheet()` es código muerto.
- PDFs reales de prueba: `C:\Pablo\Cotizaciones\Para cargar\.pdf\` (EN SECO - STEEL FRAME.pdf = 46 ítems por regex, CAROSIO, SAUCE SOLO). Test local:
  ```python
  import sys; sys.path.insert(0, r'C:\Pablo\presupuestor\api')
  from matching.extraer_pdf_texto import extraer
  r = extraer(ruta_pdf)  # r['items'], r['metodo'], r['iva_detectado']
  ```

## Invariantes críticas

- **IVA y descuento son por archivo subido** (`file_configs`), nunca fijos por proveedor.
- **Google Sheets está dado de baja** (02-07-2026): las service accounts de Google ya no tienen cuota de Drive (`storageQuota.limit=0` → 403 al crear). `/sheets` devuelve siempre xlsx; `api/sheets.py` es código muerto. Si se retoma: OAuth del usuario, no service account.
- **Escrituras a Supabase desde el API**: siempre con service key. Si aparecen errores 42501 (RLS) en logs, revisar `SUPABASE_SERVICE_KEY` en Railway.
- **Frontend**: no usar `window.open` después de un fetch async (popup blocker lo come — el gesto de click ya se consumió). Errores como lista legible, nunca JSON crudo.
- `perfiles` usa **usos_mes/limite_mes/mes_usos** (tracking mensual). El CHECK de plan admite 'advance' (webhook MP). advance/pro → límite 999.
- Precios se muestran sin IVA por default; los datos se guardan netos.

## Diagnóstico rápido

```bash
railway logs 2>&1 | grep -i -E "sheets|error|42501|get_user_plan" | tail -20
curl -s https://vectorai-production-1f06.up.railway.app/health
cd frontend && npx tsc --noEmit          # type-check antes de commitear
python -c "import ast; ast.parse(open('api/main.py', encoding='utf-8').read())"
```

Errores conocidos en logs: `get_user_plan error PGRST116 (0 rows)` — pendiente de investigar si son requests anónimos o perfiles faltantes.

## Operaciones recurrentes

Ver skill **vectorai-ops** (`.claude/skills/vectorai-ops/SKILL.md`): curado de pendientes por lote, auditoría de aliases, verificación E2E, checklist post-deploy. Plan de lanzamiento con pasos pendientes: `plan_lanzamiento_vectorai.html`.
