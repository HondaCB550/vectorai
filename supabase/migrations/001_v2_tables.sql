-- ─────────────────────────────────────────────────────────────
-- MIGRACIÓN 001: Tablas V2 del motor de matching
-- Ejecutar en el SQL Editor de Supabase (idempotente: usa IF NOT EXISTS)
-- ─────────────────────────────────────────────────────────────

-- Catálogo canónico de materiales (una fila = un material interno)
create table if not exists public.materiales_validados (
  codigo                 text primary key,
  categoria              text,
  denominacion_principal text,
  descripcion            text,
  unidades_posibles      jsonb default '[]'::jsonb,
  created_at             timestamptz default now()
);

-- Aliases y denominaciones alternativas para matching fuzzy
-- codigo_material referencia materiales_validados pero sin FK dura
-- para permitir inserts antes de que el catálogo esté completo
create table if not exists public.material_denominaciones (
  id                     bigserial primary key,
  codigo_material        text not null,
  denominacion           text not null,
  origen                 text default 'manual',
  confianza              int  default 80,
  frecuencia_encontrada  int  default 1,
  created_at             timestamptz default now(),
  unique (codigo_material, denominacion)
);

-- Sinónimos de palabras para normalización (tabla editable sin deploy)
create table if not exists public.sinonimos (
  id         bigserial primary key,
  original   text unique not null,
  canonico   text not null,
  categoria  text,
  notas      text,
  activo     boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Grupos de marcas equivalentes (ej: Waduct = Duratop = Amanco)
create table if not exists public.grupos_marcas (
  id         bigserial primary key,
  marca      text unique not null,
  grupo      text not null,
  categoria  text,
  notas      text,
  activo     boolean default true,
  created_at timestamptz default now()
);

-- Ítems sin match que esperan revisión manual
create table if not exists public.materiales_pendientes (
  id                      uuid default uuid_generate_v4() primary key,
  descripcion_original    text not null,
  descripcion_normalizada text,
  proveedor               text,
  precio_visto            numeric(12,2),
  estado                  text default 'PENDIENTE'
                          check (estado in ('PENDIENTE','VALIDADO','RECHAZADO')),
  created_at              timestamptz default now()
);

-- Histórico de precios: se acumula con cada análisis confirmado
-- codigo_material y codigo_pendiente son text/uuid sin FK dura
-- para tolerar catálogo incompleto al inicio
create table if not exists public.precios_historicos (
  id               uuid default uuid_generate_v4() primary key,
  proveedor        text not null,
  codigo_material  text,           -- referencia a materiales_validados.codigo (soft FK)
  codigo_pendiente uuid references public.materiales_pendientes(id) on delete set null,
  unidad           text,
  precio           numeric(12,2) not null,
  cantidad         int default 1,
  user_id          uuid references public.perfiles(id) on delete set null,
  created_at       timestamptz default now()
);

-- Índices para consultas frecuentes
create index if not exists idx_precios_hist_codigo
  on public.precios_historicos (codigo_material, proveedor, created_at desc);

create index if not exists idx_precios_hist_proveedor
  on public.precios_historicos (proveedor, created_at desc);

create index if not exists idx_mat_pendientes_estado
  on public.materiales_pendientes (estado, created_at desc);

create index if not exists idx_mat_denom_codigo
  on public.material_denominaciones (codigo_material);

create index if not exists idx_sinonimos_original
  on public.sinonimos (original);

-- RLS: el backend usa service key (bypassa RLS)
-- Lectura pública de sinónimos y grupos de marcas para transparencia
alter table public.material_denominaciones enable row level security;
alter table public.materiales_validados     enable row level security;
alter table public.materiales_pendientes    enable row level security;
alter table public.precios_historicos       enable row level security;
alter table public.sinonimos                enable row level security;
alter table public.grupos_marcas            enable row level security;

-- CORREGIDO 22-07-2026 (auditoría CSO). Este bloque no se podía ejecutar:
--   1. `create policy if not exists` NO existe en Postgres — la sintaxis correcta
--      no admite IF NOT EXISTS y el parser corta con `ERROR 42601: syntax error
--      at or near "not"`. La migración abortaba acá y por eso las policies vivas
--      terminaron creándose a mano, con OTROS nombres (`select_public`).
--   2. Las dos policies de precios_historicos filtraban por `auth.uid() = user_id`
--      y esa tabla nunca tuvo columna `user_id` (es catálogo compartido, no
--      per-usuario). Se eliminan: describían un modelo que no existe.
--
-- Se reconstruye lo que realmente quedó en producción, con los nombres reales,
-- para que la migración 009 (que las dropea) encuentre lo que espera al
-- reproducir la historia desde cero.
--
-- OJO: estas policies dan lectura al rol `anon`, y la anon key viaja en el
-- bundle JS. La migración 009 las elimina — no volver a agregarlas.
drop policy if exists "sinonimos_read"              on public.sinonimos;
drop policy if exists "grupos_marcas_read"          on public.grupos_marcas;
drop policy if exists "materiales_validados_read"   on public.materiales_validados;
drop policy if exists "select_public"               on public.sinonimos;
drop policy if exists "select_public"               on public.grupos_marcas;
drop policy if exists "select_public"               on public.materiales_validados;
drop policy if exists "select_public"               on public.material_denominaciones;
drop policy if exists "select_public"               on public.materiales_pendientes;
drop policy if exists "select_public"               on public.precios_historicos;

create policy "select_public" on public.sinonimos                for select using (true);
create policy "select_public" on public.grupos_marcas            for select using (true);
create policy "select_public" on public.materiales_validados     for select using (true);
create policy "select_public" on public.material_denominaciones  for select using (true);
create policy "select_public" on public.materiales_pendientes    for select using (true);
create policy "select_public" on public.precios_historicos       for select using (true);
