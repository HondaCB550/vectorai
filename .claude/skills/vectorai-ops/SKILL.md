---
name: vectorai-ops
description: Operaciones de mantenimiento de VectorAI — curado de materiales_pendientes por lote, auditoría de aliases basura, verificación E2E del flujo comparar, checklist post-deploy y diagnóstico con logs de Railway. Usar cuando el usuario diga "revisá los pendientes", "curá pendientes", "auditá aliases", "hay aliases basura", "verificá el deploy", "chequeá vectorai", "diagnosticá el API", o durante sesiones /loop de curado de datos.
---

# VectorAI Ops

Runbooks de mantenimiento. Contexto general del proyecto en `CLAUDE.md` (raíz del repo). Supabase project: `aetwdwvctowannnbelwb`.

## Reglas de dominio (confirmadas por Pablo, 03-07-2026)

Piezas que PARECEN duplicados o matches pero son productos distintos — nunca fusionar ni cruzar aliases entre ellas:
- **Rosca H vs M**: hembra vs macho, misma medida = piezas distintas.
- **Tee reducción vs buje reducción**: la tee empalma 3 caños, el buje 2.
- **Bolsón vs a granel**: misma cantidad (ej. arena m3) pero presentación y precio distintos (bolsón vs tirada desde camión).
- **Fusión agua vs fusión gas**: sistemas distintos (Acqua System = agua; Sigas = gas).
- **Material del cuerpo importa**: rejilla de fundición ≠ rejilla de PVC ≠ cromada.
- **Espesores/medidas distintas = materiales distintos** (guarda numérica siempre).
- **"Codo con base" / "3 acometidas"** son piezas distintas al codo simple MH/HH.
- **Sinónimos: NUNCA mapear un tipo específico a su familia genérica** (UPN→PERFIL, VIGA→PERFIL). El alias corto se normaliza al genérico y matchea al 100 contra cualquier texto que contenga esa palabra, contaminando aliases y precios (bug PGC, 04-07-2026). Sinónimos válidos: variantes del MISMO concepto (PARANTE→MONTANTE, TOMACORRIENTE→TOMA).

## Regla de oro

**Nunca borrar ni modificar datos del maestro sin backup previo + aprobación del usuario.** Backup = JSON con las filas completas en `api/data/backup_aliases_<tema>_<fecha>.json`. Borrados siempre por IDs explícitos, nunca con predicado amplio.

## 1. Curado de pendientes (lote)

Objetivo: vaciar `materiales_pendientes` linkeando cada texto al material correcto. Cada pendiente resuelto = match automático futuro.

1. Traer lote:
   ```sql
   select id, texto_original, proveedor, precio, created_at
   from materiales_pendientes
   where estado is distinct from 'RESUELTO'
   order by created_at limit 10;
   ```
   (verificar nombres de columnas con information_schema si cambió el esquema)
2. Para cada pendiente, buscar candidatos en `materiales_validados` por similitud contra `denominacion_principal || ' ' || descripcion` (usar rapidfuzz local con dump de la tabla, o ilike por palabras clave).
3. Presentar tabla: texto del proveedor → top 3 candidatos (codigo + denominación — descripción + score) → recomendación. Esperar aprobación por lote.
4. Aplicar aprobados:
   - Insertar alias: `material_denominaciones (codigo_material, denominacion, origen='usuario_admin', confianza=96, frecuencia_encontrada=1)` — denominacion en lowercase normalizado como los existentes.
   - Marcar pendiente como resuelto.
   - Si no existe material adecuado: proponer crear fila en `materiales_validados` (el usuario define codigo y categoría; respetar el patrón denominacion_principal genérica + descripcion distintiva).
5. Recordar: el API cachea aliases 5 min — los efectos en matching tardan hasta el próximo refresh.

## 2. Auditoría de aliases basura

Caso patrón: A018 "BROCAS" tenía colgadas placas OSB, yeso y tapas de inspección (imports `borrador_borrador_ferrocenter_*` / `gramabi` del 22-06). Un alias basura hace que textos ajenos matcheen a un código equivocado con score alto.

1. Dump de aliases + su material:
   ```sql
   select d.id, d.codigo_material, d.denominacion, d.origen,
          m.denominacion_principal, m.descripcion
   from material_denominaciones d
   join materiales_validados m on m.codigo = d.codigo_material;
   ```
2. Score local (rapidfuzz `token_set_ratio`) entre `d.denominacion` y `denominacion_principal + descripcion`. Sospechosos: score < 45 y sin palabra en común de 4+ letras. Priorizar origenes `borrador_*` y `migracion_*`.
3. Presentar lista agrupada por material, con acción propuesta: **reasignar** (si el alias claramente pertenece a otro material existente) o **borrar** (irá a pendientes cuando reaparezca).
4. Con aprobación: backup JSON → updates/deletes por IDs explícitos → verificar con select final.
5. Precedentes: `api/data/backup_aliases_basura_2026-07-02.json` (457 aliases) y `backup_aliases_A018_2026-07-02.json` (16).

## 3. Verificación E2E del flujo comparar

- URL: `https://www.vectorai.com.ar/app/comparar` (logueado). PDFs reales: `C:\Pablo\Cotizaciones\Para cargar\.pdf\`.
- El file_upload del browser MCP no acepta archivos locales del disco: inyectar por JS (base64 → `File` → `DataTransfer` → `input.files` + evento `change`). Con PDFs sintéticos chicos (~2 KB via reportlab, precios formato `9.800,00`) alcanza para probar el circuito.
- No fetch a localhost desde la página (Chrome lo bloquea y congela la pestaña).
- Checklist: extracción (n ítems > 0), stats alineadas, dudosos con `denominacion — descripcion` y opción "Ninguno corresponde", export ↓ Excel baja xlsx, y `precios_historicos` suma filas (verificar por SQL count antes/después).
- **Si el análisis de prueba guardó precios sintéticos: borrarlos** (`delete from precios_historicos where pdf_origen = '<archivo de prueba>'` por fecha del test).
- **No tocar "Confirmar y aprender" con datos sintéticos** — contamina aliases y pendientes.
- **Prueba mobile logueado**: el resize de ventana no achica el viewport real y las páginas del app exigen sesión. Truco que funciona: en la pestaña logueada, reemplazar el body por un `<iframe src="/app/comparar" style="width:390px;height:740px">` — mismo origen ⇒ misma sesión, y las media queries responden al ancho del iframe. Interactuar via `iframe.contentDocument`. Páginas públicas: frontend local + preview_resize mobile.

## 4. Checklist post-deploy

1. `git push origin main` dispara Vercel (frontend) y Railway (API) a la vez.
2. Vercel: MCP `get_project` → `latestDeployment.readyState == READY` (~2 min).
3. Railway: `curl -s .../health` — comparar `aliases_v2`/`master_items` con lo esperado.
4. Logs: `railway logs 2>&1 | grep -i -E "error|42501|Traceback" | tail -20` — 42501 = falta service key.
5. Antes de commitear: `npx tsc --noEmit` en `frontend/` y `ast.parse` de `api/main.py`.

## 5. Credenciales — cómo diagnosticar sin exponerlas

- Nunca imprimir valores de keys en el output. Para saber qué key hay configurada: decodificar solo el claim `role` del JWT (anon vs service_role), o largo/prefijo (`sb_secret_` = key nueva de Supabase).
- Para probar una key funcionalmente: script que la lee de `railway variables --json` o del `.env` **internamente** y reporta solo el resultado (SELECT ok / INSERT ok).
- La service key va en Railway como `SUPABASE_SERVICE_KEY`; el código la prefiere sobre `SUPABASE_KEY` (anon).
