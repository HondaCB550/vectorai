---
name: vectorai-nightly
description: Verificación nocturna de mantenimiento y seguridad de Vectorai — chequeos de código (tests, type-check, sintaxis), seguridad (vulnerabilidades npm/pip, secretos en el repo, advisors de Supabase), salud de la app (API, frontend, deploys, logs de Railway) y métricas de datos con tendencia. Usar cuando el usuario diga "corré la verificación nocturna", "chequeo de mantenimiento", "verificación de seguridad", "revisión completa de vectorai", o desde la tarea programada nocturna. Genera un reporte en reports/nocturno/ y lo envía al usuario.
---

# Vectorai Nightly — verificación de mantenimiento y seguridad

Runbook de la corrida nocturna completa. Contexto del proyecto en `CLAUDE.md` (raíz del repo, `C:\Pablo\presupuestor`). Complementa a `vectorai-ops` (runbooks interactivos de curado); este skill es de solo lectura y diagnóstico.

## Restricciones estrictas

- **NO commitear ni pushear** — main deploya automático a producción (Vercel + Railway).
- **NO escribir en Supabase** ni tocar datos de producción. Solo SELECTs.
- **NO publicar ni enviar nada a servicios externos.**
- **Nunca imprimir valores de API keys** — solo largo, prefijo o hash (regla de `vectorai-ops` sección 5).
- Lo único que se escribe: el reporte en `reports/nocturno/` (está en `.gitignore`).
- Escribir el reporte en español con voseo y sin emojis (regla de marca).

## Paso 1 — Chequeos deterministas (script)

```bash
cd C:\Pablo\presupuestor
python .claude/skills/vectorai-nightly/scripts/chequeos_nocturnos.py --guardar
```

Corre y devuelve JSON con PASO/ATENCION/FALLO por chequeo:

| Chequeo | Qué valida |
|---|---|
| tests_extraccion | `api/test_extraccion_parsers.py` — parsers de los 8+ formatos de proveedor, 0 fallos |
| typecheck_frontend | `npx tsc --noEmit` en `frontend/` |
| sintaxis_api | `ast.parse` de todos los `.py` de `api/` |
| health_api | `/health` de Railway con umbrales (master_items ≥900, aliases_v2 ≥4000, OCR con key) |
| frontend_prod | `vectorai.com.ar` responde 200 |
| secretos_en_repo | patrones de keys (sb_secret_, sk-ant-, APP_USR-, JWT) en archivos trackeados + `.env` no trackeado |
| npm_audit | vulnerabilidades de dependencias del frontend (critical = FALLO, high = ATENCION) |
| pip_audit | vulnerabilidades de `api/requirements.txt` |

Dura varios minutos (tsc + audits). El flag `--rapido` saltea los dos audits si solo se necesita el pulso de la app. Guarda el JSON en `reports/nocturno/chequeos_<fecha>.json` — sirve de histórico para tendencias.

## Paso 2 — Chequeos MCP y de logs (agente)

1. **Supabase advisors** (proyecto `aetwdwvctowannnbelwb`): `get_advisors` con type `security` y luego `performance`. Registrar cantidad y títulos de lints nuevos vs la corrida anterior (comparar contra el reporte previo en `reports/nocturno/`). Los advisors de seguridad (RLS deshabilitado, funciones sin search_path, etc.) son ATENCION siempre y FALLO si aparece uno nuevo de nivel ERROR.
2. **Vercel**: `get_project` del proyecto **"vectorai"** (team bontempopablo) → `latestDeployment.readyState == READY`. Si está ERROR, traer `get_deployment_build_logs`.
3. **Logs de Railway** (desde `C:\Pablo\presupuestor`):
   ```bash
   railway logs 2>&1 | grep -i -E "error|42501|Traceback|PGRST" | tail -30
   ```
   - `42501` = falta service key (FALLO, revisar `SUPABASE_SERVICE_KEY` en Railway).
   - `PGRST116 get_user_plan` = issue conocido pendiente; registrar cuántos hay, no es FALLO.
   - Tracebacks nuevos = ATENCION con el extracto.
4. **Métricas de datos** (Supabase `execute_sql`, solo SELECT):
   ```sql
   select
     (select count(*) from materiales_pendientes where estado is distinct from 'RESUELTO') as pendientes_sin_resolver,
     (select count(*) from precios_historicos) as precios_historicos,
     (select count(*) from precios_historicos where created_at > now() - interval '1 day') as precios_ultimas_24h,
     (select count(*) from perfiles) as perfiles,
     (select count(*) from presupuestos where created_at > now() - interval '1 day') as presupuestos_ultimas_24h,
     (select count(*) from extracciones_dudosas where estado = 'pendiente') as extracciones_dudosas_pendientes;
   ```
   Con el histórico de `reports/nocturno/` marcar tendencia: pendientes creciendo sin curar = ATENCION de mantenimiento (accionar con `vectorai-ops` sección 1); precios_historicos estancado varios días con uso = revisar que el flywheel siga escribiendo.
   - **extracciones_dudosas_pendientes > 0 = ATENCION siempre**: son archivos de usuarios que el motor no pudo leer y a los que el frontend les prometió resolución en 24 hs. Acción: `python descargar_dudosos.py` (baja los archivos a `Cotizaciones\Para cargar\Dudosos\`), armar el parser nuevo en `api/matching/extraer_pdf_texto.py`, deployar y marcar las filas como 'resuelto'. Listar en el reporte archivo, proveedor y motivo (`select archivo, proveedor, motivo, created_at from extracciones_dudosas where estado='pendiente'`).
5. **Aliases ambiguos** (indicador de calidad del matching, ver CLAUDE.md "Filtros del pool"):
   ```sql
   select count(*) from (
     select lower(trim(denominacion)) t
     from material_denominaciones
     group by 1 having count(distinct codigo_material) > 1
   ) q;
   ```
   Si crece contra la corrida anterior, listar los nuevos en el reporte como candidatos a auditoría (`vectorai-ops` sección 2). No tocar datos.

## Paso 3 — Reporte y envío

1. Escribir `reports/nocturno/reporte_<YYYY-MM-DD>.md` con:
   - **Resumen ejecutivo** (3-4 líneas): estado general, qué falló o requiere atención, qué cambió desde ayer.
   - **Tabla de chequeos** con PASO/ATENCION/FALLO y detalle (del JSON del paso 1 + los MCP del paso 2).
   - **Métricas y tendencia**: aliases_v2, master_items, pendientes, precios_historicos, vulnerabilidades — con delta contra la corrida anterior.
   - **Acciones sugeridas**: para cada FALLO/ATENCION, qué runbook o archivo mirar (ej. "curar pendientes → vectorai-ops sección 1"). Solo sugerir; nunca ejecutar correcciones de datos o deploys en esta corrida.
2. Enviar el reporte con `SendUserFile` (status `proactive` si es corrida programada) con caption de una línea: cuántos chequeos en verde, qué requiere atención.
3. Si TODO pasó y no hay deltas raros, el reporte igual se genera y envía — la señal de "todo en verde" también es información.

## Errores conocidos del entorno

- `npx tsc` la primera vez puede tardar por instalación de dependencias; timeout del script ya contempla 10 min.
- `pip-audit` necesita red (consulta PyPI). Si no está instalado: `python -m pip install pip-audit`.
- `railway logs` requiere el CLI logueado y linkeado al proyecto **"desirable-perception"**; si devuelve error de auth, registrar ATENCION "Railway CLI deslinkeado" y seguir.
- Los scripts de consola en Windows fallan con emojis (cp1252) — otra razón para no usarlos.
