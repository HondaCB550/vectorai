# Guion — video demo master (60 segundos)

> Pieza madre de la campaña: se usa entera en WhatsApp/YouTube y recortada (0-30 s) como reel.
> Grabación: pantalla real de vectorai.com.ar + voz en off de Pablo (voz real, no locutor — es parte del mensaje).
> Formato: vertical 9:16 para reels + export horizontal para YouTube/WhatsApp.

| Seg. | Imagen | Voz en off | Texto en pantalla |
|---|---|---|---|
| 0-5 | Mesa de obra: 3 presupuestos en papel + celular con PDFs abiertos | "Tres corralones, tres presupuestos, ¿a cuál le comprás?" | **¿A cuál le comprás?** |
| 5-12 | Pantalla: /app/comparar, arrastra 2 PDFs y saca FOTO de un presupuesto en papel con el celular | "Los subís como te llegaron. PDF, foto del papel, Excel. Sin tipear nada." | *PDF · foto · Excel* |
| 12-20 | Barra de progreso corriendo, se arma la tabla comparativa | "Vectorai lee cada ítem y los cruza entre proveedores." | *937 materiales · lee fotos con IA* |
| 20-32 | Tabla comparativa: zoom a una fila donde el mejor precio está resaltado; scroll mostrando varias | "Y te marca, ítem por ítem, dónde conviene comprar. Este mismo hierro: acá sale 50% más caro." | **El mismo material varía 27% entre proveedores** (mediana del Índice) |
| 32-42 | Tab "Lista de compras": pedido armado por proveedor con subtotales | "Te arma el pedido para cada proveedor, con las cantidades y el total." | *Lista de compras lista para mandar* |
| 42-50 | Click en "↓ Excel", se descarga; vista rápida del Excel abierto | "Y te lo llevás a Excel si querés seguir ahí." | — |
| 50-60 | Logo Vectorai + pantalla de registro | "La primera comparativa es gratis. Subí un presupuesto real y fijate cuánto estabas dejando sobre la mesa." | **vectorai.com.ar — probalo gratis** |

## Notas de grabación

- Usar presupuestos REALES (tapar teléfonos/CUITs de proveedores si hace falta).
- La foto del papel es el momento "wow" — que se vea el papel arrugado de verdad.
- Los datos son reales al 22-07-2026, medidos sobre la capa curada de `precios_historicos` (`origen='pipeline'`): mediana general 27%; hierro aleteado Ø12 concreto: $17.333 vs $26.000 = 50% entre 8 proveedores. Verificar antes de narrar si se regraba (SQL en `CURADO_PENDIENTE.md`). Nunca narrar el promedio.
- Cortes para reels: 0-30 s termina en el zoom del mejor precio + placa final de 2 s con el CTA.
- Subtítulos SIEMPRE (el 80% de reels se mira sin audio).
