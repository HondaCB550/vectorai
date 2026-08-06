-- 012 — Índice sobre la FK de codigos_promo_canjes.
--
-- La migración 011 creó codigos_promo_canjes.codigo con FK a codigos_promo pero
-- sin índice de cobertura. Postgres necesita ese índice para dos cosas:
--   1. Resolver "cuántos canjes lleva este código" (max_canjes) sin scan lleno.
--   2. Validar la FK al borrar o actualizar un código en codigos_promo.
--
-- Lo detectó el advisor de performance de Supabase (unindexed_foreign_keys) en
-- la verificación nocturna del 06-08-2026.

create index if not exists idx_codigos_promo_canjes_codigo
  on public.codigos_promo_canjes (codigo);
