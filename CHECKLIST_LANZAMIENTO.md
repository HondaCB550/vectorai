# Checklist de lanzamiento — Vectorai

> Lanzamiento: **lunes 13-07-2026** · Promo 30% OFF hasta **23-07-2026**.
> Base: fila "Esta semana (pre-13/07)" de `PLAN_CAME_VECTORAI.md` (iniciativas C4, A3, M4, E2) + checklist E2E del skill `vectorai-ops`.

---

## Verificado automáticamente (corrida del 2026-07-10 20:48)

Chequeos técnicos que no requieren a Pablo. Todos ejecutados en esta corrida; salida real registrada.

| # | Chequeo | Resultado | Detalle |
|---|---|---|---|
| 1 | Tests de extracción (parsers de proveedor) | **PASÓ** | `python test_extraccion_parsers.py` desde `api/` → **21 tests corridos, 0 fallos**. Cubren EN SECO, Carosio (corralón y presupuesto ERP), Alfonsín, Viejo Bueno, Baukraft, Europeo, Fagua, Mad. Lobos, heurístico y detección de "sin precios". (La fila del plan mencionaba 19; la suite ya creció a 21 — todos verdes.) |
| 2 | Type-check del frontend | **PASÓ** | `npx tsc --noEmit` desde `frontend/` → sin errores (exit code 0). |
| 3 | Salud del API en producción | **PASÓ** | `curl -s https://vectorai-production-1f06.up.railway.app/health` → `status: ok`. `master_items: 937` (esperado ~929, OK), `aliases_v2: 4880` (esperado >4000, OK; creció desde 4595 en la corrida del 09-07 — el flywheel de aliases sigue sumando), `ocr.motor: claude` con `key_len: 108` (key configurada; valor no impreso), `sheets_export: true`. Extras: `sinonimos_bd: 115`, `grupos_marcas_bd: 13` (eran 5 el 09-07 — se agregaron los grupos de dominios de marca del 10-07). |
| 4 | Sintaxis del backend | **PASÓ** | `python -c "import ast; ast.parse(open('api/main.py', encoding='utf-8').read())"` → parsea sin errores de sintaxis. |

**Resumen automático: 4 de 4 chequeos en verde.** No hay bloqueos técnicos para el deploy detectados por esta corrida.

---

## Pendiente de Pablo (con fecha límite)

Acciones que requieren decisión, grabación, publicación o verificación manual del usuario.

- [ ] **Revisar y aprobar las piezas de marketing** — antes del **12-07**
  Ref: `marketing/index.html` (hub navegable) → recorrer `post_fundador.html/.md`, `indice_vectorai_2026-07.html`, `canasta_vectorai_2026-07.html`, `emails_bienvenida`, `guia_5_errores`, `conceptos_reels`. Chequear que ninguna pieza nombre competidores y que la UI no use emojis (regla de marca; nota: los posts de redes en `post_fundador.md` sí llevan emojis, que es correcto para el canal social, no para la UI del producto).

- [ ] **Grabar el video demo de 60 s** — antes del **12-07**
  Ref: `marketing/guion_video_demo.md`. Pantalla real de vectorai.com.ar + voz en off de Pablo. Vertical 9:16 para reels + export horizontal. Momento "wow": la foto del papel arrugado. Subtítulos siempre. Verificar el dato contra `precios_historicos` antes de narrar: desde el 22-07 el vigente es **27% (mediana, capa `origen='pipeline'`)** — el 39% era de la medición pre-curado. SQL de verificación en `CURADO_PENDIENTE.md`; nunca narrar el promedio.

- [ ] **Cerrar el pricing nuevo** — antes del **23-07** (la promo corre sobre precios viejos)
  Ref: iniciativa A3 del `PLAN_CAME_VECTORAI.md`. Estructura decidida (04-07): Free reducido (1-2/mes, máx 3 archivos) + plan intermedio **$18-20k** + Advance a redefinir (hoy $48k). La promo 30% OFF ya corre sobre los precios actuales; el precio de régimen debe quedar definido antes de que cierre. Los legales remiten a la página de precios, así que cambiar precios no requiere re-publicar términos.

- [ ] **Correr la beta exprés con contactos** — 8 contactos, antes del **12-07**
  Ref: iniciativa C4 (beta exprés 8-12/07). Invitar contactos a probar una comparación real y recoger feedback antes del lanzamiento público. Pieza de invitación: `marketing/invitacion_beta_whatsapp.md`.

- [ ] **Publicar el Índice Vectorai #1** — el **13-07** (día del lanzamiento)
  Ref: `marketing/indice_vectorai_2026-07.html` (E2). Es la pieza de credibilidad de toda la campaña: brecha mediana 39%, 1.717 precios, 12 proveedores, 261 materiales. Publicar junto con el lanzamiento.

- [ ] **Publicar los posts de fundador (IG + LinkedIn)** — el **13-07**
  Ref: `marketing/post_fundador.md`. IG (Bonhaus + personal) y LinkedIn. Primera imagen del carrusel = foto real en obra. Publicar martes-jueves 11-13 h o 19-21 h; responder todos los comentarios las primeras 24 h. Si el caso Puerto Chascomús ya tiene números confirmados, reemplazar el "$10 millones" ilustrativo por el caso real.

- [ ] **Verificar manualmente una comparación E2E logueado** — antes del **13-07**
  Ref: `vectorai.com.ar/app/comparar` (logueado) + skill `vectorai-ops` sección 3. Subir un PDF real de `C:\Pablo\Cotizaciones\Para cargar\.pdf\`, verificar: extracción (n ítems > 0), stats alineadas, dudosos con formato `denominacion — descripcion` y opción "Ninguno corresponde", export ↓ Excel baja xlsx, y que `precios_historicos` sume filas. **Si se usa un PDF sintético de prueba, borrar los precios sintéticos después** y no tocar "Confirmar y aprender" con datos de prueba.

---

*Chequeos automáticos corridos por agente el 2026-07-10 20:48 (corrida anterior: 09-07). Sin commits, sin escrituras a Supabase, sin publicaciones. Solo lecturas y los comandos de diagnóstico indicados.*
