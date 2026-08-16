# QA independiente — Generación 5

- RUNNER_ID: `QA-IND-COMISIONES-005`
- SNAPSHOT_COMMIT: `0f735f714aab454f714a9af45beb7bda13c301cc`
- SNAPSHOT_TREE: `76f475e975a9768a474a0d00e06d1ac3a69bc66e`
- WORKTREE_CLEAN_BEFORE / AFTER: YES / YES
- TIMESTAMP_UTC: 2026-08-16T00:58:08Z
- REGRESSION: 294 passed / 0 failed (25.11 s) · DOMAIN 39/39
- COMPILEALL / GIT_DIFF_CHECK / SECRET_SCAN: PASS / PASS / PASS
- INDEPENDENT_CHECKS: 31 escenarios propios, 28 OK / 3 FALLA

## VERDICT: FAIL

### Los nueve bloqueantes históricos: 9/9 CERRADOS, verificados por ejecución propia

### LEDGER_CONSISTENCY: aritmética sólida

`paid_amount == COBRO + CONVENIO − REVERSA` se cumplió en el 100 % de las secuencias: fuzz de 60
escenarios × 6 operaciones (360 puntos de control, 0 desvíos), más `paid + balance == total` y
`0 ≤ paid ≤ total` en cada paso. **El defecto no es aritmético sino de atribución: el libro cuadra
con una fila que no representa dinero real.**

### MIGRATION_CHECK: PASS · REGRESSION_FROM_FIXES: NINGUNA respecto de los nueve históricos

### BLOQUEANTE 1 — comisión sobre dinero jamás cobrado, por la vía de ingesta documentada

Al corregir una venta de CONVENIO a COMÚN, la rama COMÚN nunca neutralizaba la fila `CONVENIO`
previa. Reproducido vía `sync_review_sales`: el origen informa `agreement=total` y luego corrige a
`agreement=0, cash=0`. Resultado: `sale_kind=COMUN`, `paid_amount=1.000.000`, `balance=0`, entry
**ELEGIBLE**, comisión liquidable 30.000 Gs. El cliente debe el total y la caja no recibió nada.
Agravantes: el saldo fantasma era **irreversible** (`revert_payment` filtra `kind='COBRO'`) y el
cobro real posterior se rechazaba por «supera el saldo pendiente», dejando la venta permanentemente
incobrable en el sistema.

### BLOQUEANTE 2 — subfacturación de 400.000 Gs. tras reversa, con residuo CONVENIO

Venta COMÚN 1.000.000, cliente paga 600.000 → origen corrige a CONVENIO → vuelve a COMÚN → se
revierte el cheque de 600.000. Libro final `[COBRO 600.000, CONVENIO 400.000, REVERSA 600.000]`,
`paid_amount=400.000`, `balance=600.000`. La caja no tenía un guaraní de ese cliente pero el
sistema le reclamaba 600.000 en vez de 1.000.000.

### BLOQUEANTE 3 — el KPI «Cobros parciales» informaba dinero ya revertido

La consulta excluía correctamente las filas `CONVENIO` pero **no** los cobros con `REVERSA`. Seña
de 300.000 revertida → KPI 300.000 con caja real 0. Es la cifra de portada de la pantalla principal.

## Observaciones no bloqueantes

- Las liquidaciones OBSERVADA suman a `commissionable_base` y `commission_amount`: la comisión de
  portada incluye lo que el sistema marcó como erróneo (45.600 Gs. visibles en la captura).
- `_apply_source_update` rechazaba toda corrección de un CONVENIO a la baja, impidiendo una
  corrección legítima del total de un convenio.
- `_month()` acepta formas ISO no canónicas que `date.fromisoformat` admite en Python 3.13.
