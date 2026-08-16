# QA independiente — Generación 4

- RUNNER_ID: `QA-IND-COMISIONES-004`
- SNAPSHOT_COMMIT: `88a3f74e0d507f20917ef5d650dd92a3e56e8202`
- SNAPSHOT_TREE: `f58a3b7196ae8645360cfe5faa70a9656df50819`
- WORKTREE_CLEAN_BEFORE / AFTER: YES / YES
- TIMESTAMP_UTC: 2026-08-16T00:40:29Z
- REGRESSION: 289 passed / 0 failed (25.12 s) · DOMAIN 34/34
- COMPILEALL / GIT_DIFF_CHECK / SECRET_SCAN: PASS / PASS / PASS
- MANIFEST verificado por el propio revisor: 35/35 OK
- INDEPENDENT_CHECKS: 69 verificaciones propias, 66 OK

## VERDICT: FAIL

### Bloqueantes históricos: los cinco CERRADOS y verificados por ejecución propia

Fechas inválidas (9 formas rechazadas en alta, cobro y pago); `PAGADA → observe → revert`
rechazado; corrección de origen sobre `REVISADA` → OBSERVADA no aprobable ni pagable; recobro tras
`revert_payment` funcionando con y sin clave; dos cobros parciales legítimos idénticos registrados
ambos.

### NEW_CONTRACT_RISKS: ninguna vía de doble conteo abierta

Fuzz de 500 cobros de 1.000 sobre saldo 400.000 se detiene exactamente en 400; nunca
`paid_amount > total_amount` ni saldo negativo por esa vía; `paid + balance == total` sostenido en
las 12 secuencias probadas; el reporte no duplica.

### MIGRATION_CHECK: PASS

Base construida con el esquema anterior (sin `client_key`): `migrate()` añade la columna sin perder
datos, crea el índice, y la segunda invocación es idempotente.

### BLOQUEANTE 1 — `sync_review_sales` descartaba en silencio un cobro posterior del origen

`_apply_source_update` calculaba `paid` desde el libro e **ignoraba por completo**
`sale.initial_paid`, mientras que el alta sí lo honraba. Reproducción ejecutada: día 1 la sucursal
reporta venta de 400.000 con `cash=100.000` → PENDIENTE_SALDO, saldo 300.000. Día 5 reporta la
misma venta con `cash=400.000`: `sync_review_sales` devuelve `registered: 1` —éxito— y sin embargo
la venta queda `paid=100.000, balance=300.000, cancelled=NULL`, la liquidación sigue en
PENDIENTE_SALDO sin período, el libro conserva un solo COBRO de 100.000 y el historial sólo anota
`SOURCE_UPDATED`: **ni error, ni observación, ni asiento del cobro**. Reintentar no autocorrige.
El único camino a ELEGIBLE era `register_payment`, que no tiene llamador productivo ni botón en la
bandeja. Resultado: toda venta común ingerida con saldo y cobrada después quedaba atrapada para
siempre en PENDIENTE_SALDO. Contradice la regla aprobada 1. Ningún test cubría el re-sync con cobro
modificado.

### BLOQUEANTE 2 — `revert_payment` sin guarda de tipo dejaba `paid_amount` sin respaldo

Venta COMÚN con cobro de 100.000 → corrección de origen a CONVENIO → `revert_payment` del cobro
previo: quedaba `paid=300.000` con libro neto 0, rompiendo la correspondencia entre `paid_amount` y
el libro append-only, y `register_payment` rechazaba la venta por convenio, cerrando la única
puerta hacia ELEGIBLE.

## Observaciones no bloqueantes

- El KPI «Comisión calculada» incluye las liquidaciones OBSERVADAS; el rótulo puede leerse como
  importe liquidable.
- `register_payment` con la misma clave y monto distinto devuelve `(None, False)` sin traza;
  convendría un asiento de historial en el descarte.
- Ni `register_payment` ni `sync_review_sales` tienen llamador productivo: hoy la bandeja sólo se
  puebla con el capturador sintético. Hueco de cableado esperable en un piloto.
