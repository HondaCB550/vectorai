-- ─────────────────────────────────────────────────────────────
-- PRESUPUESTOR — Schema Supabase
-- Ejecutar en el SQL Editor de tu proyecto Supabase
-- ─────────────────────────────────────────────────────────────

-- Extensión para UUIDs (ya viene con Supabase)
create extension if not exists "uuid-ossp";

-- ── Tabla de perfiles de usuario (extiende auth.users) ───────
create table public.perfiles (
  id            uuid references auth.users(id) on delete cascade primary key,
  mail          text,
  nombre        text,
  profesion     text,              -- "Arquitecto/a", "Constructor/a", etc.
  empresa       text,              -- nombre del estudio u empresa (opcional)
  localidad     text,              -- ciudad o localidad
  provincia     text,
  tipo_obra     text,              -- "Residencial", "Comercial", "Industrial"
  plan          text default 'free' check (plan in ('free', 'basico', 'pro')),
  usos_mes      int  default 0,   -- comparativas generadas este mes
  limite_mes    int  default 2,   -- 2 gratis, 999 en básico
  fecha_registro timestamptz default now(),
  updated_at    timestamptz default now()
);

-- Fila se crea automáticamente al registrarse
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.perfiles (id, mail)
  values (new.id, new.email);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ── Proveedores que cotiza cada usuario ──────────────────────
create table public.proveedores_usuario (
  id          uuid default uuid_generate_v4() primary key,
  user_id     uuid references public.perfiles(id) on delete cascade,
  nombre      text not null,       -- "Baukraft", "Corralón Pérez"
  tipo        text,                -- "steel frame", "gruesos", "sanitario"
  zona        text,                -- provincia o localidad
  created_at  timestamptz default now()
);

-- ── Comparativas generadas ────────────────────────────────────
create table public.comparativas (
  id             uuid default uuid_generate_v4() primary key,
  user_id        uuid references public.perfiles(id) on delete cascade,
  titulo         text,
  proveedores    text[],           -- array de nombres
  n_items        int,
  n_comunes      int,              -- ítems en más de 1 proveedor
  ahorro_total   numeric(12,2),
  url_sheets     text,
  datos_json     jsonb,            -- el resultado completo del análisis
  created_at     timestamptz default now()
);

-- ── Equivalencias aprendidas (Human in the Loop) ─────────────
-- Cada vez que un usuario confirma un match manual, se guarda aquí.
-- Beneficia a todos los usuarios con el mismo proveedor.
create table public.equivalencias (
  id             uuid default uuid_generate_v4() primary key,
  cod_prov       text not null,    -- código del proveedor
  desc_prov      text,             -- descripción original del proveedor
  proveedor      text not null,    -- nombre canónico del proveedor
  cod_int        text not null,    -- código interno (maestro Bonhaus)
  item_int       text,             -- nombre del ítem interno
  confirmado_por uuid references public.perfiles(id),
  fuente         text default 'manual',  -- 'manual' | 'auto'
  confianza      int default 100,   -- 60-100
  usos           int default 1,    -- cuántas veces fue confirmada
  created_at     timestamptz default now(),
  unique (cod_prov, proveedor)     -- una equivalencia por código+proveedor
);

-- ── Precios por zona (el activo de largo plazo) ───────────────
-- Cada precio cargado por un usuario alimenta esta tabla.
-- Permite calcular promedios por zona y detectar outliers.
create table public.precios_zona (
  id             uuid default uuid_generate_v4() primary key,
  cod_int        text not null,    -- código interno maestro
  item           text,
  detalle        text,
  proveedor      text,
  precio_sin_iva numeric(12,2) not null,
  unidad         text,
  provincia      text,
  localidad      text,
  fecha_precio   date default current_date,
  user_id        uuid references public.perfiles(id),
  comparativa_id uuid references public.comparativas(id),
  created_at     timestamptz default now()
);

-- ── Limpieza automática de comparativas viejas (>48h) ─────────
create or replace function public.cleanup_old_comparativas()
returns void language plpgsql security definer as $$
begin
  delete from public.comparativas
  where created_at < now() - interval '48 hours';
end;
$$;

-- Trigger: ejecuta cleanup cada vez que se inserta una nueva comparativa
-- Mantiene la tabla limpia sin necesidad de cron job externo
create trigger cleanup_on_new_comparativa
  after insert on public.comparativas
  for each statement execute procedure public.cleanup_old_comparativas();

-- ── Índices para consultas frecuentes ────────────────────────
create index on public.precios_zona (cod_int, provincia, fecha_precio desc);
create index on public.equivalencias (cod_prov, proveedor);
create index on public.comparativas (user_id, created_at desc);

-- ── Row Level Security ────────────────────────────────────────
alter table public.perfiles enable row level security;
alter table public.comparativas enable row level security;
alter table public.proveedores_usuario enable row level security;

-- Usuarios solo ven sus propios datos
create policy "perfiles_own" on public.perfiles
  for all using (auth.uid() = id);

create policy "comparativas_own" on public.comparativas
  for all using (auth.uid() = user_id);

create policy "proveedores_own" on public.proveedores_usuario
  for all using (auth.uid() = user_id);

-- Equivalencias son de lectura pública (el aprendizaje es compartido)
alter table public.equivalencias enable row level security;
create policy "equivalencias_read_all" on public.equivalencias
  for select using (true);
create policy "equivalencias_insert_auth" on public.equivalencias
  for insert with check (auth.uid() = confirmado_por);

-- Precios: inserción por usuarios autenticados, lectura agregada pública
alter table public.precios_zona enable row level security;
create policy "precios_insert_auth" on public.precios_zona
  for insert with check (auth.uid() = user_id);
create policy "precios_own_read" on public.precios_zona
  for select using (auth.uid() = user_id);
