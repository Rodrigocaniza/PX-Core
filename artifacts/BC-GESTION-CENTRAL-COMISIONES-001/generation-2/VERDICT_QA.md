# QA independiente — Generación 2

- RUNNER_ID: `QA-IND-COMISIONES-002`
- ROLE: QA
- SNAPSHOT_COMMIT: `5ba11bdbdbaaa826f16510fb07d08ffdbce17097`
- SNAPSHOT_TREE: `a03e20ed29ea0d583e89259013775f1de26b668c`
- WORKTREE_CLEAN_BEFORE / AFTER: YES / YES
- TIMESTAMP_UTC: 2026-08-16T00:01:35Z
- REGRESSION: 284 passed / 0 failed (24.62 s) · DOMAIN 29/29 · UI 4/4
- COMPILEALL / GIT_DIFF_CHECK / SECRET_SCAN: PASS / PASS / PASS
- INDEPENDENT_CHECKS: 108 verificaciones propias, 107 OK

## VERDICT: FAIL

### BLOCKER_Q1_STATUS (generación 1): CERRADO

`_month()` usa `date.fromisoformat` y rechaza `"2099-4-10"`, `"2099-13-45"`, `"9999-99-99"`,
`"abcd-ef-gh"`, `"2099-04"`, `""`, `"  "`, `"2099-04-31"` y `"2099-02-30"`, en el alta, en
`register_payment` y en `mark_paid`. Barrido de períodos persistidos: ninguno fuera de AAAA-MM/NULL.

### BLOCKER_A1_A2_STATUS (generación 1): CERRADO

PAGADA → `observe()` → OBSERVADA conservando `paid_at` y `payment_reference`; el `revert()`
posterior es rechazado por `_reject_paid`. La entrada es terminal: review/approve/mark_paid/revert
/observe rechazados y `recalculate` no la evalúa. No hay doble pago posible.

### REGRESSION_FROM_FIX: NINGUNA

### BLOQUEANTE NUEVO — comisión pagable calculada sobre una base congelada

`modulos/gestion_central/comisiones.py:288-297`. La guarda sólo protegía `FROZEN_STATES` (PAGADA)
y `APROBADA`; **REVISADA** caía al `UPDATE`, que reescribía `saleswoman`, `sale_kind` y
`gross_amount` pero **no** `agreement_discount`, `commissionable_base` ni `commission_amount`.
Como REVISADA no está en `RECALCULABLE_STATES`, `recalculate()` no la alcanzaba nunca, y
REVISADA → APROBADA → PAGADA es el camino directo de pago, sin compuerta de recálculo.

Verificado por ejecución:

- Convenio revisado de 500.000 corregido a 900.000: se pagaba 14.250 en vez de 25.650 →
  **11.400 Gs. de subpago**.
- Convenio revisado de 2.000.000 corregido a 100.000: se pagaba 57.000 sobre una venta real de
  100.000 → **54.150 Gs. de sobrepago**, con `gross=100.000` y `base=1.900.000`, combinación
  aritméticamente imposible.
- Venta COMUN revisada corregida a CONVENIO: `agreement_discount` quedaba en 0 → **el 5% del
  convenio (regla aprobada 4) nunca se aplicaba**.

Alcanzable de forma automática y sin intervención humana: `sync_review_sales` reejecuta
`register_sale` en cada sincronización. Defecto preexistente de la generación 1, no una regresión.

## Observaciones no bloqueantes

1. `date.fromisoformat` acepta ISO-8601 completo: `"20990410"` (formato básico) y `"2099-W15-3"`
   (semana ISO) pasan y se persisten crudos. El período derivado siempre queda bien formado, pero
   los consumidores que cortan la cadena (`substr(sale_date,1,7)`, el KPI `sales_in_period` y el
   desplegable de meses) no reconocen esas formas. No se pierde ni se duplica dinero, pero es el
   mismo patrón de desalineación que originó Q1. Normalizar al almacenar lo cerraría de raíz.
2. Una liquidación ya pagada que pasó a OBSERVADA quedaba expuesta al mismo `UPDATE` sin
   protección: una corrección de origen reatribuía `saleswoman` y `gross_amount` de dinero ya
   desembolsado. No habilitaba doble pago, pero corrompía la atribución.
3. El KPI `paid_amount` cuenta sólo `status == 'PAGADA'`: al observar una liquidación ya pagada,
   el «PAGADO» mensual cae a 0 aunque el dinero salió realmente.
4. Las liquidaciones OBSERVADAS suman a «Comisión calculada» sin exponer el contador `observed`
   que el propio KPI ya calcula.
