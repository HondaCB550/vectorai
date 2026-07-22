-- Migración 010 — Hardening restante (auditoría CSO 22-07-2026)
--
-- 1) Tablas *_referencia: quedaron fuera de la 009 por precaución, porque este
--    repo no las usa y podían estar sirviendo a otro proyecto sobre el mismo
--    Supabase. Verificado que no: ni `presupuestor/` ni `bonhaus-saas/` las
--    mencionan. Son 393 filas de datos de referencia de obra (258 costos
--    unitarios, 36 rubros, 72 tipologías, 27 resoluciones constructivas) que
--    hoy cualquiera baja con la anon key del bundle.
--
--    Si algún proyecto las necesita, que las lea con service key como el resto.
DROP POLICY IF EXISTS "select_public" ON public.costos_unitarios_referencia;
DROP POLICY IF EXISTS "select_public" ON public.rubros_referencia;
DROP POLICY IF EXISTS "select_public" ON public.tipologias_referencia;
DROP POLICY IF EXISTS "select_public" ON public.resoluciones_constructivas_referencia;

-- 2) TRUNCATE. Supabase concede ALL sobre las tablas de `public` a anon y
--    authenticated, y confía en RLS para filtrar — pero **TRUNCATE no respeta
--    RLS**: quien lo tenga vacía la tabla entera sin importar las policies.
--
--    Hoy no es alcanzable (PostgREST solo expone SELECT/INSERT/UPDATE/DELETE y
--    RPC, y ninguna función lo hace), pero se vuelve alcanzable con la primera
--    función RPC `SECURITY INVOKER` que se agregue. Nada legítimo trunca desde
--    el cliente, así que el permiso solo puede hacer daño.
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM anon, authenticated;

-- Y que las tablas nuevas nazcan sin TRUNCATE.
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE TRUNCATE ON TABLES FROM anon, authenticated;

-- NO se toca el privilegio TRIGGER: sin CREATE sobre el schema public (verificado
-- en prod: has_schema_privilege('authenticated','public','CREATE') = false) no se
-- pueden crear funciones de trigger, así que no hay camino de escalada.
