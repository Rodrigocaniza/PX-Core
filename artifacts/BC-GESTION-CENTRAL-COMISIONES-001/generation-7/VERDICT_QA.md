# QA independiente — Generación 7

- RUNNER_ID: `QA-IND-COMISIONES-007`
- SNAPSHOT_COMMIT: `cfc43718d85fdbb260f0f6d2663eb025991643eb`
- SNAPSHOT_TREE: `0ad165244ed475e3aaa21b4013de7a5386323eb4`
- WORKTREE_CLEAN_BEFORE / AFTER: YES / YES
- TIMESTAMP_UTC: 2026-08-16T01:46:51Z
- REGRESSION: 300 passed / 0 failed (26.81 s)
- COMPILEALL / GIT_DIFF_CHECK / SECRET_SCAN: PASS / PASS / PASS

## VERDICT: FAIL

### Los catorce bloqueantes históricos: 13 CERRADOS, 1 cerrado sólo parcialmente

### LEDGER_CONSISTENCY: 160 secuencias × 14 operaciones, 13 invariantes duros, cero desvíos

`paid_amount` == libro neto; `0 ≤ neto ≤ total`; `balance == total − paid` ≥ 0; una reversa por
objetivo y nunca de una reversa; ≤ 1 convenio vivo y ninguno en venta común; convenio siempre
liquidado por su total; ≤ 1 liquidación viva por venta; ninguna liquidación con `paid_at` termina
REVERTIDA; períodos AAAA-MM; `cancelled_date` si y sólo si el saldo es 0.

### CURRENT_FIX_RISKS: todos PASS

Ocho correcciones encadenadas de un convenio al alza y a la baja: libro exacto en cada paso. Seis
correcciones con cobros reales previos: los IDs de COBRO vivos y su suma permanecen idénticos.
Corrección rechazada: **la reversa del convenio no persiste** —atomicidad confirmada—. Convenio ya
PAGADO: OBSERVADA con `paid_at` intacto y sin recálculo. `AccessDenied` no se degrada a `rejected`.

### BLOQUEANTE — la guarda del lote no cubría el parseo ni la construcción de la fila

`int(payload.get("total"))`, el resto del parseo y `CommissionSaleInput(...)` se evaluaban **antes**
del `try`, de modo que un `ValueError` nacido ahí seguía propagándose fuera de `sync_review_sales`,
truncaba el lote y hacía desaparecer en silencio todas las filas posteriores, sin sumar a
`registered`, `skipped`, `invalid_date` ni `rejected`. Es el bloqueante de la generación 6
desplazado una línea. Reproducido dos veces por ejecución: (a) con el `ReviewService` **real**, una
fila con `branch` vacío dejó 1 de 3 ventas aplicables ingeridas y 2 perdidas sin rastro; (b) un
`total` con formato de miles, plausible viniendo de la fuente SQLite legacy, dejó 1 de 2.

## Observaciones no bloqueantes

- Una corrección de origen que cambia `sale_date` conserva el `cancelled_date` anterior y no
  actualiza el período. **No alcanzable por la ingesta real** (la identidad incorpora
  `business_date`); defecto de contrato de la API, latente.
- `_month()` acepta formatos ISO no canónicos que luego no casan con `substr(sale_date,1,7)`.
  No alcanzable por la ingesta.
- El KPI «Comisión calculada» incluye las liquidaciones OBSERVADA. No mueve dinero.
- Una corrección puramente no financiera sobre un convenio dispara igualmente la
  reversión-y-reasiento: 30 correcciones producen 61 filas. El neto siempre queda exacto.
- Una venta hoy CONVENIO no admite `revert_payment` sobre sus cobros reales previos.
