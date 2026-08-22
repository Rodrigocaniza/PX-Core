# Auditor — PASS

- `pending_alerts` exige `reviews.read` y falla cerrado para operadores de
  sucursal; filtra por sucursal sin exponer otras.
- La pantalla no marca revisiones, no encola correcciones ni alertas y no altera
  el estado del outbox: una prueba verifica sobre el fuente que no invoca
  `create_branch_alert`, `require_correction`, `mark_*` ni `add_note`.
- Sin correo, Telegram, HTTP ni ningún despacho: la misma prueba lo comprueba.
  Los pendientes siguen `PENDING` después de mirarlos.
- Encolar dos veces la misma alerta no duplica la cola: la clave de
  idempotencia del servicio se mantiene y la pantalla la respeta.
- Orden estable comprobado: recargar tres veces no altera la secuencia aunque
  las solicitudes compartan segundo. El arreglo vive en la presentación; el
  servicio compartido no cambió de comportamiento.
- La bitácora es append-only y de lectura: observaciones y eventos se mezclan
  ordenados por fecha, mostrando actor, campo y transición de estado.
- No hay red, servicio, despliegue ni escritura hacia las sucursales.
