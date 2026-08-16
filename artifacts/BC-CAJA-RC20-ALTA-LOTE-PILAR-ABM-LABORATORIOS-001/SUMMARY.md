# BC Caja RC20 — Alta de lote desde Pilar y ABM de laboratorios

Base canónica: `c4e5344aa89b4f87c293ac54174679a273f1ee01` (RC19 CLOSED).

Cierra los dos huecos que impedían que RC19 fuera usable sin asistencia
técnica: cargar el lote de Pilar y administrar los laboratorios, ambos desde
la propia pestaña Seguimiento.

## 1. Alta de lote desde Pilar

**No se recarga nada.** Los candidatos son los pedidos que ya existen en
`orders`, generados por las ventas de la caja de Pilar. La consulta los filtra
por sucursal y rango de fechas y **excluye en SQL los que ya están seguidos**,
mediante `LEFT JOIN tracked_works ... WHERE t.id IS NULL`. Un trabajo no puede
ofrecerse dos veces aunque se repita la búsqueda.

Flujo: `+ Nuevo envío desde Pilar` → sucursal y rango → *Buscar* →
`15 trabajos encontrados` → seleccionar todos o por clic → `Crear envío (N)`
→ confirmación → los N trabajos quedan `ENVIADO_DESDE_PILAR`.

La defensa contra duplicados es doble: la consulta no los ofrece, y
`create_pilar_shipment` vuelve a verificar contra `tracked_works` antes de
escribir. Si algo ya salió, falla nombrando los sobres y **no deja un lote a
medias** (probado).

## 2. Identidad de lote

`pilar_shipments` con origen, destino, fecha, operadora, nota y sus trabajos
asociados por `tracked_works.shipment_id`.

**El lote no sustituye al trabajo.** Su condición —`ENVIADO`,
`RECEPCION_PARCIAL`, `RECIBIDO_COMPLETO`, `VACIO`— se **deriva** de los
trabajos que contiene y no se almacena, igual que el criterio que RC19 usó
para `ATRASADO`. Cada trabajo conserva su id, su traza y su estado propio.

## 3. Recepción en Asunción

Sin reimplementar nada: se reutilizan las transiciones de RC19.
`shipment_detail` reexpone el mismo `reception_progress` ya existente, de modo
que enviados / recibidos / faltantes y el marcado uno por uno siguen siendo el
código de RC19.

## 4. ABM de laboratorios

Diálogo compacto detrás del botón `Laboratorios`: alta, edición de nombre,
línea y WhatsApp por separado, y activación/desactivación.

**Sin borrado físico.** `set_laboratory_active` es baja lógica; si el
laboratorio tiene historial, la UI lo advierte antes de desactivar. Un
laboratorio inactivo se conserva en los trabajos históricos —la fila sigue
mostrando su nombre y su teléfono— pero `selectable_laboratories()` lo excluye
de las opciones para envíos nuevos.

## UX

La pantalla no gana formularios permanentes: dos botones en la barra que ya
existía, y el trabajo ocurre en diálogos. Se mantiene la jerarquía de RC18:
tipografía derivada del perfil visual y el mismo lenguaje de color.

## Fuera de alcance, respetado

FactuFácil, WhatsApp API, encomienda externa automatizada, sincronización cloud
nueva, rediseño general, cambios económicos y entrega final al cliente: sin
tocar. `main` no fue tocada y Comunicaciones quedó intacto.

## Ajustes en pruebas existentes

Las mismas seis aserciones que fijan la cadena de migraciones se extendieron de
016 a 017, conservando su intención. `test_rc19_advances_schema_once_to_016`
pasa a `test_rc20_advances_schema_once_to_017`.

## Defectos corregidos durante la misión

- La sonda de smoke capturaba la pantalla completa; al ser los diálogos más
  chicos que el escritorio, el artifact habría quedado con contenido ajeno del
  equipo. Ahora recorta al rectángulo del diálogo.
- El diálogo de laboratorios cortaba el campo WhatsApp contra el borde: ancho
  ajustado a la fila del formulario.

## Verificación

- Regresión canónica: **327 PASS, 0 FAIL** (RC19 dejó 293; RC20 suma 34).
- Smoke GUI real PASS en 1920×1080 y 1366×768.
- RC18 y RC19 verificados sin regresión.
