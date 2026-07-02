-- Migración 002 — Modelo de lanzamiento (ver MODELO_Y_FLUJO_LANZAMIENTO.md)
-- Agrega: organizaciones (tenancy), proveedores, presupuestos, presupuesto_items,
-- conversion_unidades. Aditiva: no modifica datos existentes.
-- perfiles ya cumple el rol de "usuarios"; comparativas es el informe al usuario.

-- ============================================================
-- 1. ORGANIZACIONES (tenancy)
-- ============================================================
CREATE TABLE organizaciones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre TEXT NOT NULL,
  plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'basico', 'pro')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vincular perfiles existentes (nullable: usuarios individuales siguen funcionando sin org)
ALTER TABLE perfiles ADD COLUMN org_id UUID REFERENCES organizaciones(id);

-- ============================================================
-- 2. PROVEEDORES (catálogo global)
-- ============================================================
CREATE TABLE proveedores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre TEXT NOT NULL UNIQUE,
  cuit TEXT,
  zona TEXT,
  activo BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed desde los proveedores ya vistos en datos existentes
INSERT INTO proveedores (nombre)
SELECT DISTINCT TRIM(proveedor) FROM precios_historicos
WHERE proveedor IS NOT NULL AND TRIM(proveedor) <> ''
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO proveedores (nombre)
SELECT DISTINCT TRIM(proveedor) FROM materiales_pendientes
WHERE proveedor IS NOT NULL AND TRIM(proveedor) <> ''
ON CONFLICT (nombre) DO NOTHING;

-- FK en precios_historicos (el campo texto queda como legado; nuevas filas usan la FK)
ALTER TABLE precios_historicos ADD COLUMN proveedor_id UUID REFERENCES proveedores(id);

UPDATE precios_historicos ph
SET proveedor_id = p.id
FROM proveedores p
WHERE TRIM(ph.proveedor) = p.nombre AND ph.proveedor_id IS NULL;

CREATE INDEX idx_precios_proveedor_id ON precios_historicos(proveedor_id);

-- ============================================================
-- 3. PRESUPUESTOS (documento subido por el usuario)
-- ============================================================
CREATE TABLE presupuestos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES perfiles(id),
  org_id UUID REFERENCES organizaciones(id),
  comparativa_id UUID REFERENCES comparativas(id) ON DELETE SET NULL,
  proveedor_id UUID REFERENCES proveedores(id),
  proveedor_detectado TEXT,          -- texto crudo antes de resolver la FK
  archivo TEXT,                      -- nombre / URL del PDF o Excel
  incluye_iva BOOLEAN,               -- resultado de la detección de IVA
  factor_iva NUMERIC DEFAULT 1.105,
  estado TEXT DEFAULT 'PROCESANDO' CHECK (estado IN ('PROCESANDO', 'PROCESADO', 'ERROR')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_presupuestos_user ON presupuestos(user_id);
CREATE INDEX idx_presupuestos_comparativa ON presupuestos(comparativa_id);

-- ============================================================
-- 4. PRESUPUESTO_ITEMS (la bisagra: cada línea del PDF con su match)
-- ============================================================
CREATE TABLE presupuesto_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presupuesto_id UUID NOT NULL REFERENCES presupuestos(id) ON DELETE CASCADE,
  texto_original TEXT NOT NULL,
  texto_normalizado TEXT,
  marca TEXT,
  unidad TEXT,
  cantidad NUMERIC DEFAULT 1,
  precio NUMERIC,                    -- neto de IVA, ya normalizado
  codigo_material TEXT REFERENCES materiales_validados(codigo),
  pendiente_id UUID REFERENCES materiales_pendientes(id),
  score_match INTEGER,
  estado_match TEXT DEFAULT 'SIN_MATCH' CHECK (estado_match IN ('MATCH', 'REVISAR', 'SIN_MATCH', 'CONFIRMADO')),
  origen_match TEXT,                 -- 'alias', 'fuzzy', 'equiv', 'llm', 'usuario'
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_items_presupuesto ON presupuesto_items(presupuesto_id);
CREATE INDEX idx_items_material ON presupuesto_items(codigo_material);
CREATE INDEX idx_items_estado ON presupuesto_items(estado_match);

-- ============================================================
-- 5. CONVERSION_UNIDADES (rollos ×100m, manguera ×25m, bolsas…)
-- ============================================================
CREATE TABLE conversion_unidades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo_material TEXT NOT NULL REFERENCES materiales_validados(codigo),
  unidad_comercial TEXT NOT NULL,    -- ej: 'rollo 100m', 'caja x12'
  factor NUMERIC NOT NULL,           -- multiplicador hacia la unidad base
  unidad_base TEXT NOT NULL,         -- ej: 'm', 'unidad', 'kg'
  descripcion TEXT,
  activo BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (codigo_material, unidad_comercial)
);

CREATE INDEX idx_conversion_material ON conversion_unidades(codigo_material);

-- ============================================================
-- 6. RLS
-- ============================================================
-- Zona tenancy: cada usuario ve solo lo suyo
ALTER TABLE organizaciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE presupuestos ENABLE ROW LEVEL SECURITY;
ALTER TABLE presupuesto_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "miembros ven su organizacion" ON organizaciones
  FOR SELECT USING (
    id IN (SELECT org_id FROM perfiles WHERE perfiles.id = auth.uid())
  );

CREATE POLICY "dueño gestiona sus presupuestos" ON presupuestos
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "dueño gestiona sus items" ON presupuesto_items
  FOR ALL USING (
    EXISTS (SELECT 1 FROM presupuestos pr
            WHERE pr.id = presupuesto_items.presupuesto_id
              AND pr.user_id = auth.uid())
  ) WITH CHECK (
    EXISTS (SELECT 1 FROM presupuestos pr
            WHERE pr.id = presupuesto_items.presupuesto_id
              AND pr.user_id = auth.uid())
  );

-- Catálogo global: lectura pública, escritura solo vía service role (backend)
ALTER TABLE proveedores ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversion_unidades ENABLE ROW LEVEL SECURITY;

CREATE POLICY "lectura publica proveedores" ON proveedores
  FOR SELECT USING (true);

CREATE POLICY "lectura publica conversiones" ON conversion_unidades
  FOR SELECT USING (true);
