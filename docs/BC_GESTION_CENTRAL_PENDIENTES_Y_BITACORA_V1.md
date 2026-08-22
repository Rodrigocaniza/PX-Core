# BC Gestión Central — Pendientes y bitácora V1

Cierra un hueco propio de la revisión central: `require_correction` y
`create_branch_alert` encolan trabajo en `review_correction_outbox` y
`review_alert_outbox`, pero Sol no tenía dónde ver esa cola ni la historia de la
fila. Esta pantalla la muestra; no despacha nada.

Misión independiente: parte de la misma base canónica
`feature/bc-gestion-central-sync-receiver-v1-001` y no depende de la vista de
proyecciones Sync.

## Lo que agrega

`ReviewService.pending_alerts(actor, branch=None)` — el outbox de alertas no
tenía lectura; la de correcciones ya existía. Es un `SELECT` con `reviews.read`,
simétrico a `pending_corrections`.

`PendingPanel` muestra las dos colas con el contexto de la venta (sobre,
sucursal, fecha, campo, motivo, solicitante) y, al seleccionar un pendiente, la
bitácora append-only de esa fila: observaciones y eventos en una sola línea
temporal ordenada.

## Orden estable

Ambos outbox desempatan por `id`, que es un uuid aleatorio: varias solicitudes
del mismo segundo se listaban en orden distinto en cada recarga. La pantalla
reordena por `requested_at,business_date,source_entry_id` y por
`created_at,branch,identity`. El servicio compartido no se modificó; el arreglo
vive en la presentación y una prueba comprueba que recargar no altera el orden.

## Frontera

La pantalla sólo lee: `list_sales`, `pending_corrections`, `pending_alerts`,
`notes` y `events`. No marca revisiones, no crea correcciones ni alertas, no
cambia el estado del outbox y no tiene correo, Telegram, HTTP ni ningún
despacho; una prueba lo verifica sobre el propio fuente.

Entregar realmente esos pendientes a las sucursales sigue siendo trabajo futuro
y depende de decisiones humanas de canal; nada aquí lo adelanta.
