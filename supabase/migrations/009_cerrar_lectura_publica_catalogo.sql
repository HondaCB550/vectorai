-- Migración 009 — Cierra la lectura pública del catálogo (auditoría CSO 22-07-2026)
--
-- El problema: varias tablas tenían policies de SELECT con USING (true), que
-- aplican al rol `anon`. La anon key viaja en el bundle JS de vectorai.com.ar,
-- así que cualquiera podía paginar /rest/v1/<tabla> y bajarse:
--
--   precios_historicos        4.807 filas   (el histórico de precios)
--   material_denominaciones   5.750 filas   (los aliases curados = el moat)
--   materiales_validados      1.066 filas   (el maestro)
--   materiales_pendientes       727 filas   (ítems sin match de clientes)
--
-- precios_historicos.pdf_origen además guarda el nombre del archivo que subió
-- el cliente junto al proveedor y el precio: expone con quién cotiza cada
-- constructora y a cuánto.
--
-- Nadie necesitaba esas policies: el frontend solo consulta `perfiles` de forma
-- directa (verificado: el único `supabase.from(...)` del proyecto está en
-- app/registro/page.tsx), todo el resto pasa por el API de FastAPI, que escribe
-- y lee con la service key y por lo tanto ignora RLS. Los scripts locales
-- también resuelven `SUPABASE_SERVICE_KEY or SUPABASE_KEY`, con la service key
-- presente en api/.env.
--
-- Queda el mismo patrón que ya usan facturacion_eventos y extracciones_dudosas:
-- RLS habilitada y sin policies = deny-all para anon/authenticated, acceso solo
-- por service key.

-- Núcleo del producto
DROP POLICY IF EXISTS "select_public" ON public.precios_historicos;
DROP POLICY IF EXISTS "select_public" ON public.material_denominaciones;
DROP POLICY IF EXISTS "select_public" ON public.materiales_validados;
DROP POLICY IF EXISTS "select_public" ON public.materiales_pendientes;

-- Configuración del matching
DROP POLICY IF EXISTS "select_public" ON public.sinonimos;
DROP POLICY IF EXISTS "select_public" ON public.grupos_marcas;
DROP POLICY IF EXISTS "lectura publica conversiones" ON public.conversion_unidades;
DROP POLICY IF EXISTS "lectura publica proveedores" ON public.proveedores;

-- Tabla legada de v1. `equivalencias_insert_auth` además dejaba que cualquier
-- usuario logueado escribiera en una tabla global — la misma clase de problema
-- que /confirmar-v2 (hallazgo 2 de la auditoría).
DROP POLICY IF EXISTS "equivalencias_read_all"  ON public.equivalencias;
DROP POLICY IF EXISTS "equivalencias_insert_auth" ON public.equivalencias;

-- NO se tocan las tablas *_referencia (costos_unitarios, rubros, tipologias,
-- resoluciones_constructivas) ni precios_zona: este repo no las usa y podrían
-- estar sirviendo a otro proyecto sobre el mismo Supabase. Revisar aparte antes
-- de cerrarlas.
