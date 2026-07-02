-- Migración 003 — Seguridad (advertencias del linter de Supabase, 2026-07-02)
-- handle_new_user es SECURITY DEFINER y estaba expuesta vía /rest/v1/rpc/ a anon y authenticated.

-- 1) search_path fijo: evita hijacking de esquema en funciones SECURITY DEFINER.
--    El cuerpo usa public.perfiles calificado, así que search_path vacío no la rompe.
ALTER FUNCTION public.handle_new_user() SET search_path = '';

-- 2) Revocar ejecución vía API REST. Solo corre como trigger en auth.users,
--    que no depende del permiso EXECUTE del caller.
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;

-- Pendiente manual (no es SQL): activar "Leaked password protection" en
-- Dashboard → Authentication → Providers → Email → Password security
-- (chequea contraseñas contra HaveIBeenPwned al registrarse).
