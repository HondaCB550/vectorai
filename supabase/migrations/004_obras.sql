-- 004: Obras (plan alto) — agrupan presupuestos y comparativas.
-- La localidad/provincia de la obra alimenta el dato de precios por zona.
-- Aplicada el 2026-07-06 vía MCP.

CREATE TABLE IF NOT EXISTS obras (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id),
  nombre text NOT NULL,
  localidad text,
  provincia text,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE obras ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS obras_own ON obras;
CREATE POLICY obras_own ON obras FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS obra_id uuid REFERENCES obras(id);
ALTER TABLE comparativas ADD COLUMN IF NOT EXISTS obra_id uuid REFERENCES obras(id);
