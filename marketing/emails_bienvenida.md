# Secuencia de bienvenida — 3 emails

> Disparadores: email 1 al confirmar la cuenta (o +1 h), email 2 a las 48 h si NO corrió ninguna comparativa (si corrió, saltar al 3), email 3 al día 5-7.
> Remitente: Pablo de Vectorai <hola@vectorai.com.ar>. Firma simple: Pablo Bontempo — Vectorai · vectorai.com.ar
> Mientras no haya automatización, se pueden mandar a mano desde Gmail (send-as hola@).

---

## Email 1 — "Tu primera comparativa en 2 minutos"

**Asunto:** Subí un presupuesto y mirá lo que pasa
**Preheader:** PDF, foto o Excel — como te lo mandó el corralón, así lo subís.

Hola [nombre]:

Soy Pablo, el que armó Vectorai. Soy constructor, y esto existe porque me cansé de pasar precios de PDFs a Excel un domingo a la noche.

Tu primera comparativa lleva 2 minutos, en serio:

1. Entrá a [vectorai.com.ar/app/comparar](https://vectorai.com.ar/app/comparar)
2. Subí 2 o más presupuestos de tus proveedores — **PDF, foto del papel o Excel, tal cual te llegaron**
3. Listo. La tabla te marca el mejor precio ítem por ítem, y podés bajarla a Excel con el pedido armado para cada proveedor.

Un dato para que veas por qué vale la pena: en los presupuestos que ya pasaron por Vectorai, **el mismo material varía un 27% de precio entre proveedores** (mediana de nuestro Índice). Ese margen hoy lo está dejando alguien sobre la mesa — que no seas vos.

¿Trabas, dudas, algo que no matcheó bien? Respondé este mail y te contesto yo.

Pablo

---

## Email 2 — caso real (a las 48 h, si no corrió comparativa)

**Asunto:** Cómo comparo 4 corralones en 5 minutos (caso real)
**Preheader:** Una compra de obra real, con números.

Hola [nombre]:

Te muestro un caso real de la obra que estamos haciendo en Puerto Chascomús (una casa de steel frame):

- Pedimos presupuesto del mismo listado a [N] proveedores
- Los subimos a Vectorai tal como llegaron (dos eran fotos de papel)
- La comparativa mostró **[X]% de diferencia** entre el total más caro y el armado óptimo comprando cada ítem donde convenía
- En plata: **$[monto]** en una sola compra

> ⚠️ COMPLETAR con los números reales del caso antes de mandar (pendiente de confirmación de Pablo).

Lo que más tiempo ahorra no es la tabla — es no tener que tipear nada: la foto del presupuesto alcanza.

Tu cuenta tiene una comparativa gratis esperando: [probala con una compra real](https://vectorai.com.ar/app/comparar). Si el resultado no te ahorra más de lo que sale un mes del plan Inicial, no lo pagues y listo.

Pablo

---

## Email 3 — qué te dan los planes (día 5-7)

**Asunto:** ¿Cuánto vale no pagar de más?
**Preheader:** Inicial $19.600/mes (precio de lanzamiento) — se paga solo con una compra.

Hola [nombre]:

Antes de los números, una forma de pensarlo: las constructoras grandes tienen una persona dedicada a compras — cotiza, compara, negocia. Las empresas chicas hacemos ese trabajo nosotros, de noche y gratis. **Vectorai es ese puesto de compras**, por menos de lo que sale una hora de obra al mes.

Los tres niveles:

**Free** — 1 comparativa para probar, sin tarjeta. Ya la tenés.

**Inicial — $19.600/mes** (precio de lanzamiento; después $28.000)
6 comparativas por mes, hasta 5 proveedores por comparativa, lista de compras por proveedor lista para mandar. Si comprás materiales todos los meses, con **una sola compra** bien comparada lo recuperás varias veces.

**Advance — $48.000/mes**
Comparativas ilimitadas, tus presupuestos guardados para re-comparar sin volver a subirlos, organización por obra, y acceso prioritario a lo que viene: **precios de referencia por zona** (saber si el hierro que te cotizaron está caro para tu zona, antes de comprar).

[Ver planes →](https://vectorai.com.ar/suscribirse)

Y si Vectorai no te cierra, también me sirve saberlo: respondé este mail con el motivo y te leo personalmente.

Pablo

---

## Notas de implementación

- Variables: [nombre] viene de `perfiles.nombre`.
- Los envíos automáticos requieren SMTP propio + un job; mientras tanto: envío manual semanal a los registros nuevos (query: perfiles con `acepta_marketing=true` creados en la semana).
- Respetar `acepta_marketing=false`: a esos usuarios solo les llega lo transaccional (confirmación de cuenta).
- Link con atribución en campañas externas; en estos mails no hace falta (ya están registrados).
