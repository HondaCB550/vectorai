# QA Report — Vectorai (localhost, report-only)

- **Fecha:** 2026-07-20
- **Target:** http://localhost:3000 (frontend Next.js 16) + API http://localhost:8002 (FastAPI)
- **Modo:** report-only (sin arreglos ni commits)
- **Auth:** sesión real de Pablo (admin) vía Claude-in-Chrome sobre Chrome real
- **Evidencia:** árbol de accesibilidad + consola + red + asserts JS. **Sin capturas de imagen** (la captura del panel daba timeout en este entorno; ver Limitaciones).
- **Health score: ~95/100**

## Resumen

La app está sólida. **Cero errores de consola en todas las páginas.** Auth gating, manejo de errores de login, empty states y el panel de admin (100 pendientes con datos reales) funcionan bien. Los hallazgos son en su mayoría menores, más un bug de config de entorno local y una violación de regla de marca.

## Severidad

| # | Sev | Área | Hallazgo |
|---|-----|------|----------|
| 1 | Medium | devex/config | Dev local roto de fábrica: los launchers de API (`api/lanzar_api.bat`, `lanzar_todo.bat`) usan **:8000**, pero `frontend/.env.local` apunta a **:8002**. Un arranque fresco deja todas las features con API (analizar, métricas, historial) sin backend. |
| 2 | Medium | marca | La UI de `/app/comparar` usa emojis **📄** (dropzone) y **⚡** (botón Analizar), en contra de la regla documentada "sin emojis / usar viñeta naranja". |
| ~~3~~ | ~~Low-Med~~ | ~~UX~~ | ~~"⚡ Analizar" sin archivos = no-op silencioso~~ → **FALSO POSITIVO** (revisado en 2ª pasada): el botón ya está `disabled` cuando no hay archivos (`page.tsx:1141`) con `disabled:opacity-40`. El clic no hace nada porque corresponde. No es defecto. |
| 4 | Low | contenido | Copy de planes inconsistente entre landing y `/suscribirse`. Ej.: Advance dice "Soporte prioritario" (landing) vs "Soporte directo por WhatsApp" (/suscribirse); la retención "30 días" figura en landing pero no en /suscribirse. |
| 5 | Low | UX/legal | `/registro` no tiene checkbox de aceptación de términos (solo links a /terminos y /privacidad). |

## No-bugs (limitaciones conocidas de localhost)

- **`/app/admin/metricas` → "No se pudieron cargar las métricas"**: `GET /admin/metrics` devuelve **500** porque llama a la RPC de Supabase `admin_metrics` (main.py:2893), que la anon key local no puede ejecutar (necesita service key). En prod funciona. El frontend degrada con un mensaje limpio. Sin auth el endpoint devuelve **403** correctamente. → No es bug; "no verificable local".

## Verde (funciona bien)

- **Consola limpia**: 0 errores en landing, login, registro, recuperar, suscribirse, comparar, presupuestos, historial, admin.
- **Auth gating**: `/app/comparar` sin sesión → redirect a `/login?from=%2Fapp%2Fcomparar` (preserva `from`). Middleware OK.
- **Login**: validación `required` (HTML5) + credencial inválida → "Mail o contraseña incorrectos" en `role=alert`, sin crash.
- **Empty states** limpios en `/app/presupuestos` ("Todavía no procesaste ningún presupuesto") e `/app/historial` ("No hay comparativas guardadas aún").
- **`/app/admin`** (Panel de revisión): carga 100 pendientes con datos reales y acciones (linkear / crear / rechazar).
- **`/suscribirse`** correctamente bloqueado sin login ("Tenés que iniciar sesión para suscribirte").
- **`/mis-presupuestos` → 200**: reads user-scoped funcionan con anon key + token del usuario.

## Cobertura

Públicas: `/`, `/login`, `/registro`, `/recuperar`, `/suscribirse`.
Logueadas: `/app/comparar`, `/app/presupuestos`, `/app/historial`, `/app/admin`, `/app/admin/metricas`.

**No ejercido:** flujo E2E de subir PDF → analizar → confirmar. `file_upload` de Claude-in-Chrome solo acepta archivos compartidos con la sesión, no PDFs del disco. Para cerrarlo: (a) Pablo arrastra un PDF a mano y sigo desde el análisis, o (b) test backend-directo a `/analizar-v2`. Confirmar/guardar además tiene límite local (anon key). MercadoPago: no se tocó (fuera de alcance).

## Limitaciones del entorno de QA (no son de Vectorai)

1. **gstack `browse`** no arranca su daemon en Windows + Bun 1.3.14 (bug de `openSync(...,'wx')` en el binario compilado). Por eso se usó Claude-in-Chrome en vez del flujo nativo de `/qa`, y se perdió el `cookie-import`.
2. **Captura de imagen** del panel de navegador da timeout en este entorno. Evidencia = DOM/consola/red/JS.

---

# Segunda pasada — fix mode (2026-07-21)

Rama **`qa/fixes-2026-07-21`** (NO se pusheó: un push a `main` auto-deploya a prod).

## Hallazgo mayor nuevo — un fallo de infra se disfraza de fallo de auth **[ARREGLADO]**

Al correr el E2E con PDFs reales, `POST /analizar-v2` devolvió **401 "Iniciá sesión para analizar presupuestos"** a un usuario **logueado**. Traza:

```
get_user_plan error: 'new row violates row-level security policy
                      for table "perfiles"', code 42501
POST /analizar-v2 → 401 Unauthorized
```

El token se mandaba bien (`/obras`, `/mi-plan`, `/mis-presupuestos` → 200). La causa está en `get_user_plan` (main.py:274-276):

```python
except Exception as e:
    print(f"get_user_plan error: {e}")
    return dict(_ANONIMO)      # degrada a anónimo ante CUALQUIER excepción
```

El JWT ya se verificó en la línea 239. Cualquier excepción posterior es **infraestructura** (RLS, Supabase caído, service key rotada), no auth — pero igual degradaba a anónimo y `_gate_analisis` respondía "iniciá sesión". **Es la tercera vez que esta clase de bug muerde** (el docstring documenta las otras dos: columnas inexistentes y `.single()`/PGRST116).

**Impacto en prod:** si Supabase hipa o la service key rota, los usuarios logueados reciben "Iniciá sesión" — parece login roto y genera tickets de soporte.

**Fix (commit `e7b6f05`):** el fallo de infra se marca con `error_infra` y `_gate_analisis` responde **503 "No pudimos validar tu cuenta en este momento"**. Fail-closed (no habilita bypass de cuota); los endpoints que toleran el fallback anónimo ignoran la clave. **Verificado**: local reproduce la condición exacta y `POST /analizar-v2` pasó de 401 → 503 con el mensaje correcto.

## Emojis en la UI **[ARREGLADO]**

Commit `929a2c5`: 8 emojis eliminados en `comparar`, `presupuestos` y `revisar`. Sin inventar iconografía (el proyecto no tiene librería de íconos); `app/page.tsx` ya había resuelto lo mismo con la viñeta de marca. `tsc --noEmit` limpio y verificado en browser.

## Hallazgo nuevo sin arreglar — arrastrar N archivos crea N proveedores

Al soltar 4 archivos (3 hojas de CAROSIO + 1 de SAUCE SOLO), cada archivo se convirtió en un **proveedor separado**: las 3 hojas del mismo presupuesto quedaron como 3 proveedores distintos. Efectos: (a) la comparación queda semánticamente mal, (b) consume la cuota de proveedores del plan y dispara el muro de upsell ("Cambiar de plan para comparar más de 3"). La UI sí tiene "＋ Agregar otro archivo" por proveedor (la forma correcta), pero el drag-drop no la usa. **Decisión de producto pendiente**: ¿agrupar por nombre de archivo, preguntar al soltar varios, o dejarlo así?

## E2E de analizar — sigue sin poder cerrarse en local

Bloqueado por la limitación de anon key/RLS (`get_user_plan` no puede crear el perfil). En prod con `SUPABASE_SERVICE_KEY` funciona. Para cerrarlo de verdad hay que correrlo contra prod o con service key local.

## Top 3 para arreglar

1. **Port mismatch :8000 vs :8002** — alinear launchers y `.env.local` (o documentarlo) para que el dev local funcione de fábrica.
2. **Emojis en `/app/comparar`** — reemplazar 📄 y ⚡ por la viñeta/íconos de marca (regla "sin emojis").
3. **Feedback en "Analizar" sin archivos** — mostrar "Agregá al menos un archivo" o deshabilitar el botón con hint.
