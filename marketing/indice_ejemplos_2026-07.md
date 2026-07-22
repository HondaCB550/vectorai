# Índice Vectorai #1 — datos y ejemplos de respaldo (medición 20-07-2026)

> Munición para responder si preguntan por el dato del 40%. Todos los precios son **netos (sin IVA)** — si alguien compara contra un ticket con IVA, sumar ~10,5%.
> Fuente: `precios_historicos`, precio más reciente por material/proveedor, proveedores normalizados (mismo negocio bajo varios nombres = 1).

## El número

- **Brecha mediana: 40%** (41% con proveedores normalizados; 39% en junio con muchos menos datos → el número aguantó).
- Brecha promedio: 51%.
- Medido sobre **23 proveedores reales** y **111 materiales comparables** (≥3 proveedores, spreads >150% excluidos como ruido de unidad).

## Objeciones descartadas (verificadas 20-07)

1. **¿Proveedores duplicados inflando el conteo?** No. Normalizados (Sauce×3, Carosio Sanitario×2, Viejo Bueno×3, Materalia×2), la mediana quedó en 41%.
2. **¿Neto vs bruto por IVA?** No. Solo 2 de 111 materiales caen en la banda del IVA (8-13%); excluyéndolos la mediana SUBE a 43%. Las brechas son 4× el IVA.
3. **¿Modelos/marcas distintos disfrazados de brecha?** No. De 111 materiales, 101 son commodities de espec; sacando los 10 sensibles a marca, la mediana queda igual (41%).

## Aclaración clave (para no quedar mal parado)

**El 40% es la MEDIANA entre materiales, no el número de cada ítem.** Hay materiales con 17% (PGC 100 0,90) y otros con 46% (Isocrete). Mensaje correcto: "en promedio 40%, y en muchos ítems bastante más". Nadie gana en todo: el más barato en un ítem es el más caro en otro — por eso comprar todo al de siempre deja plata sobre la mesa.

## Canasta representativa (materiales que pesan en una obra) — idea de Pablo 20-07

Medir la brecha solo en los ítems de alta incidencia (estructura, hormigón, cerramiento) en vez de todos los materiales. **Precios limpios (cluster correcto), netos.**

| Material | Corralones | Más barato | Más caro | Brecha |
|---|---|---|---|---|
| Piedra m³ | 10 | $52.489 | $88.000 | **68%** |
| OSB 11mm | 6 | $22.001 | $32.705 | 49% |
| Isocrete perlas EPS 170 L | 5 | $26.434 | $38.501 | 46% |
| Hierro aleteado Ø12 (barra) | 5 | $17.974 | $26.000 | 45% |
| EPS 30mm | 3 | $5.666 | $7.864 | 39% |
| Cemento bolsa 25kg | 8 | $6.500 | $8.869 | 36% |
| PGU 100 0,90 | 5 | $17.592 | $23.525 | 34% |
| Arena m³ | 7 | $38.009 | $48.934 | 29% |
| PGC 100 0,90 | 4 | $23.644 | $27.633 | 17% |

**Mediana de la canasta: 39% · Promedio: 40%** — coincide con el número general. El 40% se sostiene en los materiales que mueven el presupuesto, no en accesorios baratos.

- **Piedra m³ (68%, 10 corralones)** es el ejemplo más fuerte: distribución continua real, sensible a flete.
- **Ladrillo común / hueco 12: NO está en el corpus** con suficientes corralones (solo refractario). Sumar.
- **Hierro Ø10: sin datos limpios** (solo Ø12).

### DEUDA DE DATOS — precios contaminados en precios_historicos (arreglar antes de publicar canasta cruda)
Errores de unidad/matching que obligan a limpiar a mano; además indican posible bug de matching/conversión en los materiales pesados:
- **Cemento 25kg**: cluster erróneo $39.589-60.851 (Baukraft, Laprida, Nuevo Pilar, En Seco, San Rafael) — pallet o mal matcheado — mezclado con la bolsa real ~$7.500.
- **Hierro Ø12**: cluster erróneo $2.815-3.894 (Maderera Lobos, En Seco) — por metro / Ø equivocado — mezclado con la barra real ~$20.000.
- **Chapa sinusoidal galv C25**: $13.601-15.721 (por metro) vs $80.633-87.617 (por chapa entera).
- **Tornillos T1/T2 mecha**: precios por unidad ($15-23) mezclados con caja de 10.000 ($170k-199k).

## Ejemplos — commodities de espec (misma pieza exacta)

### Sanitarios
| Material | Más barato | Más caro | Brecha |
|---|---|---|---|
| Llave de paso fusión 25 | $12.678 — El Galpón (13/07) | $17.743 — Sauce (09/07) | 40% |
| Boca de acceso 63×50 3 entradas | $4.378 — Carosio Sanitario (09/07) | $6.127 — Triunvirato (13/07) | 40% |
| Codo cloacal 45° HH 50 | $1.386 — Sauce (09/07) | $1.948 — Casa Alfonsín (09/07) | 41% |

### Steel frame / aislación / hormigón
| Material | Más barato | Más caro | Brecha |
|---|---|---|---|
| **Perfil PGC 200 – 2,04mm** | $66.700 — Insuma (14/07) | $96.239 — Civimet (14/07) | **44%** |
| Isocrete perlas EPS bolsa 170 L | $26.434 — Carosio Corralón (14/07) | $38.501 — Materalia Quilmes (13/07) | 46% |
| Tubo alcantarilla hormigón 30cm | $25.001 — Materalia Quilmes (13/07) | $36.035 — Sauce (14/07) | 44% |
| PGU 100 – 0,94mm | $17.592 — Insuma (14/07) | $23.525 — En Seco (08/07) | 34% |

**Mejor ejemplo para Pablo (steel frame):** PGC 200 – 2,04mm, $66.700 vs $96.239, ambos cotizados el mismo día 14/07 por dos proveedores de steel. Casi $30.000 de diferencia por tira, misma pieza, mismo día.

### PGC 100 0,90 (perfil base de la Canasta — brecha MENOR, ~17%)
| Proveedor | Precio neto | Fecha |
|---|---|---|
| Maderera Lobos | $23.644 | 08/07 |
| La Foresta (sin facturar) | $24.431 | 14/07 |
| Civimet | $25.278 | 14/07 |
| En Seco | $27.633 | 08/07 |

Entre los dos formales el mismo día (08/07): $23.644 vs $27.633 = **17%**. Ejemplo de que no todos los ítems dan 40% — este perfil es de los más parejos.

## RE-MEDICIÓN POST-CURADO (22-07-2026) — usar ESTOS números de acá en adelante

El curado de presentaciones y matching (ver `CURADO_PENDIENTE.md`, commits
b3be9b7 + 80f8baa) saldó la DEUDA DE DATOS de arriba: los 4 clusters
contaminados (cemento pallet, hierro por metro, chapa entera vs metro,
tornillos por caja) eran errores de matching/presentación y ya no existen en
la capa curada. `precios_historicos` quedó partida en `origen='pipeline'`
(auditable, con texto del proveedor, matcher y conversiones actuales — lo único
que entra al Índice) y `origen='legacy'` (lo anterior, conservado pero afuera).

**El número vigente: brecha mediana 27% (27,6% exacta).** Sin excluir nada:
119 materiales multi-proveedor, 96% con dispersión sana (antes 74%). Ya no
hace falta la guarda de spreads ni excluir outliers — con los datos limpios la
mediana con y sin guarda casi coinciden (25,9% vs 27,6%), señal de que el 40%
anterior estaba inflado por los errores de datos, no por los precios.

**Qué decir si preguntan por el cambio 39→27**: el 39/40% se midió antes del
curado; al limpiar errores de presentación (cajas de 6.000 tornillos
comparadas contra bolsas de 100) y de matching, la brecha real quedó en 27%.
Sigue siendo el mensaje completo: un cuarto del precio del mismo material
depende de a quién le comprás.

### Canasta representativa re-medida (capa pipeline, netos)

| Material | Proveedores | Más barato | Más caro | Brecha |
|---|---|---|---|---|
| Piedra m³ | 8 | $52.724 | $88.000 | **67%** |
| Isocrete perlas EPS 170 L | 5 | $24.185 | $38.501 | 59% |
| Cemento blanco 25kg | 4 | $39.500 | $60.851 | 54% |
| Hierro aleteado Ø12 (barra) | 8 | $17.333 | $26.000 | **50%** |
| PGC 200 2,04mm | 3 | $66.700 | $96.239 | 44% |
| Cerecita 20 L | 5 | $38.118 | $50.000 | 31% |
| Malla sima Q188 15×15 6mm | 7 | $42.750 | $55.001 | 29% |
| Arena m³ bolsón | 3 | $40.317 | $48.934 | 21% |
| Hormigón elaborado H21 | 3 | $167.228 | $194.542 | 16% |

**Mediana de la canasta: 44%** — en los materiales que mueven el presupuesto
la brecha es MAYOR que la mediana general del 27%. Ese es el mejor ángulo
para lo próximo: "la mediana general es 27%, y en los materiales pesados de
la obra, 44%".

- El hierro Ø12 quedó impecable tras el curado: 8 proveedores, $17.333–$26.000,
  todos barra suelta verificada por texto.
- Excluidos de la canasta por prudencia aunque su dispersión sea "sana":
  cámara desgrasadora (94% — puede ser capacidad distinta) y PGC 150 1,64
  (117% — revisar antes de usar).

## Avisos de uso

- **Evitar ejemplos donde el más barato es "La Foresta – Sin Facturar"** (lana de vidrio, EPS 30mm): precio sin factura, invita a la objeción "está en negro". Usar solo proveedores formales.
- **Evitar el hierro aleteado Ø6** (44%): las cotizaciones estaban a 2 semanas (14/07 vs 30/06), el precio pudo moverse.
- **Evitar productos terminados de marca** (inodoros, grifería): el código agrupa varios modelos, la brecha puede ser modelo distinto, no proveedor distinto.
