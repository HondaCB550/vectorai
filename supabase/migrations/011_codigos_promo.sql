-- Migración 011 — Códigos promocionales (meses gratis de un plan)
--
-- Caso de uso: Pablo genera códigos (ej. AMIGOS2, INFLU-JUAN) que regalan 1 o 2
-- meses de un plan pago. El canje lo hace el API con service key vía
-- POST /promo/canjear; el vencimiento vive en perfiles.plan_hasta y lo aplica
-- get_user_plan (al vencer, el perfil vuelve a free).
--
-- Seguridad (mismo modelo que el resto del catálogo): RLS habilitado SIN
-- policies + REVOKE a anon/authenticated → solo el service key del API puede
-- leer/escribir. La anon key del bundle no puede enumerar códigos ni canjes.

-- 1) Vencimiento del plan regalado. NULL = plan sin vencimiento (pagos por MP).
ALTER TABLE public.perfiles ADD COLUMN IF NOT EXISTS plan_hasta timestamptz;

-- 2) Códigos
CREATE TABLE IF NOT EXISTS public.codigos_promo (
  codigo      text PRIMARY KEY CHECK (codigo = upper(codigo) AND codigo ~ '^[A-Z0-9_-]{3,32}$'),
  plan        text NOT NULL DEFAULT 'advance' CHECK (plan IN ('basico', 'advance')),
  meses       int  NOT NULL DEFAULT 1 CHECK (meses BETWEEN 1 AND 12),
  max_canjes  int  CHECK (max_canjes > 0),   -- NULL = sin tope
  canjes      int  NOT NULL DEFAULT 0,       -- contador denormalizado (fuente: codigos_promo_canjes)
  activo      boolean NOT NULL DEFAULT true,
  vence       timestamptz,                   -- fecha límite para CANJEAR (no la duración del regalo)
  nota        text,                          -- para quién es (ej. "influencer Juan")
  creado_en   timestamptz NOT NULL DEFAULT now()
);

-- 3) Canjes. UNIQUE(user_id): un usuario canjea UN código promocional en la
--    vida — evita encadenar códigos de distintos influencers para no pagar nunca.
CREATE TABLE IF NOT EXISTS public.codigos_promo_canjes (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo      text NOT NULL REFERENCES public.codigos_promo(codigo),
  user_id     uuid NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  plan        text NOT NULL,
  meses       int  NOT NULL,
  canjeado_en timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.codigos_promo        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.codigos_promo_canjes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.codigos_promo        FROM anon, authenticated;
REVOKE ALL ON public.codigos_promo_canjes FROM anon, authenticated;

-- 4) plan_hasta es campo sensible: si el cliente pudiera escribirlo con la anon
--    key, se extendería el regalo a mano. Entra al freeze junto con plan.
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
  -- legítimos de plan (webhook de MercadoPago, canje de promo, panel admin)
  -- pasan de largo.
  if jwt_role in ('authenticated', 'anon') then
    if TG_OP = 'INSERT' then
      new.plan       := 'free';
      new.limite_mes := 2;
      new.usos_mes   := 0;
      new.usos_total := 0;
      new.mes_usos   := null;
      new.org_id     := null;
      new.plan_desde := null;
      new.plan_hasta := null;
      new.es_interno := false;
    else
      new.plan       := old.plan;
      new.limite_mes := old.limite_mes;
      new.usos_mes   := old.usos_mes;
      new.usos_total := old.usos_total;
      new.mes_usos   := old.mes_usos;
      new.org_id     := old.org_id;
      new.plan_desde := old.plan_desde;
      new.plan_hasta := old.plan_hasta;
      new.es_interno := old.es_interno;
    end if;
  end if;

  return new;
end;
$function$;
