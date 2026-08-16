# QA independiente — Generación 9

- RUNNER_ID: `QA-IND-COMISIONES-009`
- SNAPSHOT_COMMIT: `114aee84745aa82293509f4d76be3c0bac381827`
- SNAPSHOT_TREE: `cdf46c8bac5c877aa1d7d8ba2a2c561581a213d6`
- TIMESTAMP_UTC: 2026-08-16T02:26:26Z
- REGRESSION: 302 passed / 0 failed (24.91 s) · DOMAIN 47/47 · UI 4/4
- COMPILEALL / GIT_DIFF_CHECK / SECRET_SCAN: PASS / PASS / PASS

## VERDICT: PASS

**BLOCKERS: NONE.**

### DIFF_IS_COMMENT_ONLY: confirmado con prueba más fuerte que la textual

El revisor comparó los **AST** de `comisiones.py` antes y después: **idénticos**. La generación 9 es
demostrablemente inerte y no pudo introducir regresión alguna.

### Los quince bloqueantes financieros históricos: 15/15 CERRADOS

Con escenarios propios, **sin reutilizar un solo caso del repositorio**.

### LEDGER_CONSISTENCY: PASS

**8.800 pasos de fuzz en cinco semillas independientes**, unas 1.960 ventas generadas, mezclando
altas, cobros con y sin clave, reversas, re-sync que cambia tipo/total/vendedora, anulaciones, flujo
de estados y recálculos con políticas de 0 % a 100 %. Invariantes revalidados en cada paso:
`paid_amount == ΣCOBRO + ΣCONVENIO − ΣREVERSA`, `paid + balance == total`, `0 ≤ paid ≤ total`,
`balance ≥ 0`, una sola reversa por cobro, una sola liquidación activa por venta y ninguna
`REVERTIDA` con `paid_at`. **Cero violaciones.**

### Verificación propia total: ~132.000 aserciones, 0 fallas

334 chequeos distintos más el fuzz. Las seis fallas iniciales del propio script fueron trianguladas
una por una y **las seis resultaron errores de expectativa del revisor, no del producto**.

### Caza adversarial de dinero

Atribución tras corrección de vendedora, reversa parcial, anulada que no resucita, identidad por
local, convenio→común sin doble liquidación, políticas 0 %/100 %/precedencia, ausencia de política
que no inventa comisión, y `descuento + base == total` exacto en 11 totales incluyendo 1, 3 y
999.999 Gs. **Sin un solo caso de dinero perdido, duplicado, pagado de más o de menos, o mal
atribuido.**

## Observaciones no bloqueantes

Ninguna nueva ni no documentada. Confirmó por reproducción los hallazgos 17 y 28 del backlog, ambos
correctamente descritos y correctamente clasificados como no bloqueantes, y señaló que
`commission_amount` incluye las OBSERVADAS por diseño y que los botones de la UI están siempre
habilitados con el gate en el servicio.
