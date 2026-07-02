-- Migración 004 — columna moneda en precios_historicos (2026-07-02)
-- El modelo de lanzamiento preveía moneda en PRECIOS_HISTORICOS; necesaria para
-- cargar listas cotizadas en USD (ej. COMPARATIVA_SANITARIOS_Jun26.xlsx).
-- Las comparaciones nunca deben mezclar monedas.
ALTER TABLE precios_historicos ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'ARS';
