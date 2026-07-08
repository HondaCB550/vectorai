-- 005_emparejar_terminaciones.sql
-- Feature "Emparejar terminaciones": vínculos manuales de ítems SIN MATCH
-- (griferías, porcelanatos, inodoros de distintas marcas que no están en el
-- catálogo maestro). El usuario agrupa ítems equivalentes de distintos
-- proveedores en un "concepto" para compararlos por precio.
--
-- Reglas de diseño (acordadas con Pablo):
--   * El vínculo NO toca el catálogo global (materiales_validados /
--     material_denominaciones). Vive por-comparativa.
--   * Estructura fila-concepto con N proveedores (no par-a-par).
--   * "Recordar" es POR-USUARIO: siembra terminaciones_recordadas para
--     pre-sugerir el vínculo en futuros presupuestos. Nunca se propaga a
--     otros usuarios ni al pool de matching.
--
-- Patrón RLS: auth.users(id) + policy FOR ALL auth.uid()=user_id
-- (mismo que 004_obras.sql). Se numera 005 por la colisión doble de 004.

-- ─────────────────────────────────────────────────────────────────────────
-- 1) Concepto: una fila de comparación dentro de una comparativa
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS terminaciones_conceptos (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  comparativa_id uuid REFERENCES comparativas(id) ON DELETE CASCADE,
  nombre         text NOT NULL,
  unidad         text NOT NULL DEFAULT 'c/u',
  cantidad       numeric NOT NULL DEFAULT 1,
  origen         text NOT NULL DEFAULT 'manual',  -- 'manual' | 'sugerido'
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tconceptos_comparativa ON terminaciones_conceptos(comparativa_id);
CREATE INDEX IF NOT EXISTS idx_tconceptos_user        ON terminaciones_conceptos(user_id);

ALTER TABLE terminaciones_conceptos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tconceptos_own ON terminaciones_conceptos;
CREATE POLICY tconceptos_own ON terminaciones_conceptos
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- ─────────────────────────────────────────────────────────────────────────
-- 2) Ítems del concepto: el vínculo apoyado en el id estable de la línea
--    (presupuesto_items.id, que ya viaja al frontend como item_id).
--    Un ítem por proveedor y por concepto.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS terminaciones_concepto_items (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  concepto_id         uuid NOT NULL REFERENCES terminaciones_conceptos(id) ON DELETE CASCADE,
  presupuesto_item_id uuid NOT NULL REFERENCES presupuesto_items(id) ON DELETE CASCADE,
  proveedor_id        uuid REFERENCES proveedores(id),
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (concepto_id, proveedor_id),   -- una celda por proveedor
  UNIQUE (concepto_id, presupuesto_item_id)
);
CREATE INDEX IF NOT EXISTS idx_tci_concepto ON terminaciones_concepto_items(concepto_id);
CREATE INDEX IF NOT EXISTS idx_tci_item     ON terminaciones_concepto_items(presupuesto_item_id);

ALTER TABLE terminaciones_concepto_items ENABLE ROW LEVEL SECURITY;
-- La propiedad se hereda del concepto padre.
DROP POLICY IF EXISTS tci_own ON terminaciones_concepto_items;
CREATE POLICY tci_own ON terminaciones_concepto_items
  FOR ALL
  USING (EXISTS (
    SELECT 1 FROM terminaciones_conceptos c
    WHERE c.id = concepto_id AND c.user_id = auth.uid()
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM terminaciones_conceptos c
    WHERE c.id = concepto_id AND c.user_id = auth.uid()
  ));

-- ─────────────────────────────────────────────────────────────────────────
-- 3) Recuerdo por-usuario: qué texto de qué proveedor cayó en qué concepto.
--    Sirve para pre-sugerir el vínculo en la próxima comparativa del usuario.
--    texto_normalizado usa la MISMA normalización del matching (normalize()).
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS terminaciones_recordadas (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  proveedor_id      uuid REFERENCES proveedores(id),
  texto_normalizado text NOT NULL,
  concepto_nombre   text NOT NULL,
  frecuencia        int  NOT NULL DEFAULT 1,
  updated_at        timestamptz NOT NULL DEFAULT now(),
  created_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, proveedor_id, texto_normalizado)
);
CREATE INDEX IF NOT EXISTS idx_trec_user  ON terminaciones_recordadas(user_id);
CREATE INDEX IF NOT EXISTS idx_trec_texto ON terminaciones_recordadas(user_id, texto_normalizado);

ALTER TABLE terminaciones_recordadas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS trec_own ON terminaciones_recordadas;
CREATE POLICY trec_own ON terminaciones_recordadas
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
