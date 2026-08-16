# BC Caja RC22 — El trabajo enviado queda visible

Corrige el fallo detectado en la prueba manual del escenario TEST.

## Causa raíz

**El envío nunca se creó.** La base lo confirma: `pilar_shipments` y
`tracked_works` estaban en 0 y los 15 pedidos seguían sin vincular. La pestaña
no mostraba nada porque no había nada que mostrar.

El origen es un defecto que introduje en la integración RC18–RC20: al agregar
la ventana por defecto de tres días, la **búsqueda** pasó a usar un rango pero
la **creación** siguió revalidando contra un único día. El diálogo pasa
`consultation_date = campo Desde` (14/08) y `create_pilar_shipment` volvía a
resolver candidatos con `start=end=14/08`, donde no hay pedidos: los 15 fueron
creados el 15/08. Resultado: `15 trabajo(s) ya no están disponibles para envío`
y ningún registro escrito.

Reproducido antes de tocar código, y cubierto por
`test_el_envio_funciona_con_la_ventana_por_defecto_de_tres_dias`.

## Corrección

`create_pilar_shipment` deja de re-derivar elegibilidad por fecha. La operadora
ya seleccionó pedidos concretos de una búsqueda que puede abarcar un rango; lo
que hay que validar es lo que de verdad importa:

- que los pedidos existan (`list_orders_by_ids`);
- que sean de la sucursal indicada;
- que no estén ya en el circuito.

Sin fecha explícita, la consulta se deduce del propio lote. Las tres
protecciones anteriores siguen vigentes, con prueba cada una.

## Vista de Seguimiento

- **Abre en `Activos`**: todo lo que no completó el circuito. Antes abría en
  `Todos`.
- **`Completados`** y **`Todos`** como filtros adicionales. Un trabajo en
  `RECIBIDO EN PILAR` sale de la vista activa y aparece en Completados.
- **La tabla vacía explica por qué lo está** y, en `Activos`, indica cómo
  cargar un lote. Una tabla vacía sin explicación fue justamente lo que hizo
  dudar de si el envío se había guardado.
- **La alerta de atrasados es accionable**: un clic aplica el filtro
  `Atrasados` y muestra solo los que la originaron.
- **Ficha de detalle** por botón *Ver detalle* o doble clic: sobre, cliente,
  tipo, estado, laboratorio, línea, WhatsApp, fecha/hora esperada, última
  novedad, recorrido completo de transiciones y novedades con el laboratorio.

La identidad del trabajo no cambia en ningún punto: es la misma fila
cambiando de estado, sin listas separadas por etapa.

## Defecto adicional que encontró el smoke

El botón *Ver detalle* recibía la función como referencia directa, pero se
construye antes de que esa función exista: abrir la pestaña lanzaba
`UnboundLocalError`. La suite no podía verlo —no ejecuta la UI— y el smoke GUI
sí. Corregido envolviéndolo, con prueba que lo fija.

## Verificación

- Regresión canónica: **390 PASS, 0 FAIL**.
- Smoke GUI real en 1920×1080.
- Los 11 puntos de validación ejecutados **contra los 15 registros TEST
  reales**, sin sembrar datos nuevos.

## Escenario TEST

Se usó el existente y quedó **devuelto a su punto de partida**: los 15 pedidos
vuelven a ser candidatos, `tracked_works` en 0 y los tres laboratorios
conservados. `tools/cleanup_escenario_test.py --reset-circuito` hace ese
reinicio y sirve para repetir la prueba cuantas veces haga falta.

Sin impacto económico: no se tocaron ventas, cierres, arqueos, convenios ni
correo. `integrity_check=ok`.
