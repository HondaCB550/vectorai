-- Migración 006 — Cierra la escalada de plan por DELETE + INSERT (auditoría CSO 22-07-2026)
--
-- El problema: la policy `perfiles_own` es FOR ALL, y anon/authenticated tenían
-- DELETE e INSERT sobre public.perfiles. La única protección del campo `plan`
-- era el trigger trg_freeze_perfil_sensitive, definido BEFORE UPDATE. Con eso,
-- cualquier usuario logueado podía, usando la anon key pública del bundle:
--
--   DELETE /rest/v1/perfiles?id=eq.<su-uuid>
--   POST   /rest/v1/perfiles  {"id":"<su-uuid>","plan":"pro"}
--
-- El INSERT no dispara un trigger BEFORE UPDATE, y perfiles_plan_check acepta
-- 'pro'. Resultado: plan máximo (límite 999) sin pagar. La misma primitiva
-- servía para resetear usos_total y renovar el free de por vida.
--
-- Esta migración además trae al repo la función freeze_perfil_sensitive, que
-- hasta hoy existía SOLO en la base de producción: si el proyecto se
-- reconstruía desde supabase/migrations/, el candado desaparecía sin aviso.

-- 1) El trigger también cubre INSERT. En INSERT no hay OLD del cual copiar,
--    así que se fuerzan los defaults de alta limpia (los mismos que ya usa
--    handle_new_user: plan 'free', contadores en cero).
CREATE OR REPLACE FUNCTION public.freeze_perfil_sensitive()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO ''
AS $function$
declare
  jwt_role text;
begin
  begin
    jwt_role := current_setting('request.jwt.claims', true)::jsonb ->> 'role';
  exception when others then
    jwt_role := null;
  end;

  -- El API escribe con service key (role 'service_role'), así que los cambios
  -- legítimos de plan (webhook de MercadoPago, panel de admin) pasan de largo.
  if jwt_role in ('authenticated', 'anon') then
    if TG_OP = 'INSERT' then
      new.plan       := 'free';
      new.limite_mes := 2;
      new.usos_mes   := 0;
      new.usos_total := 0;
      new.mes_usos   := null;
      new.org_id     := null;
      new.plan_desde := null;
      new.es_interno := false;
    else
      new.plan       := old.plan;
      new.limite_mes := old.limite_mes;
      new.usos_mes   := old.usos_mes;
      new.usos_total := old.usos_total;
      new.mes_usos   := old.mes_usos;
      new.org_id     := old.org_id;
      new.plan_desde := old.plan_desde;
      new.es_interno := old.es_interno;
    end if;
  end if;

  return new;
end;
$function$;

DROP TRIGGER IF EXISTS trg_freeze_perfil_sensitive ON public.perfiles;

CREATE TRIGGER trg_freeze_perfil_sensitive
  BEFORE INSERT OR UPDATE ON public.perfiles
  FOR EACH ROW EXECUTE FUNCTION public.freeze_perfil_sensitive();

-- 2) Defensa en profundidad: nadie desde el cliente necesita borrar su fila de
--    perfiles. El borrado de cuenta sigue funcionando — baja en cascada desde
--    auth.users (perfiles_id_fkey ON DELETE CASCADE) y ese path corre con el
--    rol de auth, no con anon/authenticated.
REVOKE DELETE ON public.perfiles FROM anon, authenticated;
