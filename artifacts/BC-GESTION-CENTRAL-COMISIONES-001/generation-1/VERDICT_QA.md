# QA independiente — Generación 1

- RUNNER_ID: `QA-IND-COMISIONES-001`
- ROLE: QA
- SNAPSHOT_COMMIT: `c24b4f19c66dc685d1679ed266eb887f2dbfe773`
- SNAPSHOT_TREE: `d296c6384885176399dceeeda103a4acb397e43d`
- WORKTREE_CLEAN_BEFORE / AFTER: YES / YES
- TIMESTAMP_UTC: 2026-08-15T23:41:08Z
- REGRESSION: 280 passed / 0 failed (25.71 s)
- DOMAIN_TESTS: 25/25 · UI_TESTS: 4/4
- COMPILEALL: PASS · GIT_DIFF_CHECK: PASS · SECRET_SCAN: PASS
- INDEPENDENT_CHECKS: 23 verificaciones propias ad-hoc, todas OK

## VERDICT: FAIL

### BLOQUEANTE Q1 — `_month()` no valida la fecha y corrompe el período de liquidación

`modulos/gestion_central/comisiones.py:57-62` aceptaba cualquier cadena de largo >= 7 con un
guion en la posición 4 y devolvía `text[:7]` como período.

Impacto verificado por ejecución: una venta de 900.000 cancelada con `sale_date="2099-4-10"`
—fecha sin cero a la izquierda, entrada humana o de Excel plenamente plausible— queda ELEGIBLE →
CALCULADA con base 900.000 y comisión 27.000, pero con período `"2099-4-"`. **No aparece en el
reporte de 2099-04 ni en ningún mes real.** No hay error, no hay estado OBSERVADA, no hay señal
alguna para la operadora: la comisión se pierde en silencio. Por la vía del cobro,
`register_payment(..., "2099-5-03")` fija `period="2099-5-"` y `report("2099-05")` devuelve 0 filas
y base 0, rompiendo exactamente la regla central de la misión.

Alcanzabilidad real, no hipotética: `sync_review_sales` pasa `payload["date"]` sin validar a
`CommissionSaleInput.sale_date`, y ese valor es `cash_days.business_date` leído crudo del snapshot
SQLite externo en `real_sync.py:158`, sin validación de formato en toda la cadena de importación.

Agravante de consistencia: todos los demás campos de `CommissionSaleInput` se validan con rigor
y el resto del paquete ya usa `date.fromisoformat`. La fecha era la única brecha, y es la que
determina el período de liquidación.

Criterios de aceptación afectados: «período correcto» y «filtros mensuales».

## Observaciones no bloqueantes registradas

1. **Cobros reales idénticos deduplicados.** La clave de idempotencia de `register_payment`
   incluye monto + fecha + referencia, y la referencia es opcional con default vacío. Dos cobros
   genuinos del mismo monto, el mismo día y sin referencia hacen que el segundo se descarte en
   silencio: el saldo nunca llega a cero y la venta nunca comisiona. Exposición actual baja
   (el panel no ofrece alta de cobros; entran por `sync_review_sales`).
2. **Las liquidaciones OBSERVADA suman a los KPIs monetarios** del período y del resumen por
   vendedora, pese a estar marcadas «requiere corrección manual». No hay fuga de dinero
   (`paid_amount` sólo cuenta PAGADA y el pago exige APROBADA), pero el KPI «Comisión calculada»
   sobreestima lo realmente liquidable.
3. **Ventas mixtas (convenio parcial) mal clasificadas** en `sync_review_sales`: usa
   `kind = "CONVENIO" if agreement >= total else "COMUN"` e ignora la porción de convenio cuando
   es parcial. La dirección del error es conservadora —nunca paga de más— y las reglas aprobadas
   no definen la venta mixta.
4. `revert` admite OBSERVADA → REVERTIDA incluso cuando la observación provino de un pago
   efectuado. **Coincide con el bloqueante A1 del Auditor.**
5. Índice redundante: `idx_commission_entry_period` es subsumido por `idx_commission_entry_active`.
   Sin impacto funcional.

## Lo que sí verificó como correcto

Las diez verificaciones exigidas pasaron: período de cancelación, 5 % aplicado una sola vez,
convenio sin saldo cliente, recálculo idempotente, gate de pago, reversión, congelamiento de
PAGADA frente a reversión de cobro, duplicado rechazado, enteros de punta a punta y persistencia.
Inspección visual de la captura: aritmética de KPIs y de cada fila verificada sin doble conteo.
