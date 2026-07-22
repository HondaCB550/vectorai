-- Curado de presentaciones y unidades (22-07-2026).
--
-- precios_historicos no guardaba el texto del proveedor, y sin ese texto
-- _convertir_unidad no puede decidir la presentacion: no habia forma de
-- recalcular una conversion sobre una fila ya guardada. De 4.807 filas, solo
-- 1.004 se podian reenganchar con su presupuesto_item por precio exacto (el
-- IVA y el descuento son por archivo y se aplican en el medio).
--
--   texto_original: la descripcion tal cual la escribio el proveedor.
--   origen: 'pipeline' = fila con texto, matcher y conversiones actuales,
--           auditable fila por fila. Es la unica que entra al Indice y a
--           /precios-historial.
--           'legacy'   = fila anterior al 22-07-2026, sin texto recuperable.
--           Se conservan pero quedan fuera: mezclan $/unidad con $/caja y
--           $/bolsa de distinto peso sin forma de distinguirlos.
--
-- El default 'legacy' marca las filas existentes sin necesidad de un UPDATE
-- amplio sobre la tabla.
alter table precios_historicos
  add column if not exists texto_original text,
  add column if not exists origen text not null default 'legacy';

create index if not exists precios_historicos_origen_idx
  on precios_historicos (origen);
