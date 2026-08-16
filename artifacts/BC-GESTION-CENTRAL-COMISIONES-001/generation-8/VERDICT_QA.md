# QA independiente — Generación 8

- RUNNER_ID: `QA-IND-COMISIONES-008`
- SNAPSHOT_COMMIT: `c4f6ee64717ca43becc5986985040ff57d6ee9f2`
- SNAPSHOT_TREE: `6e6bc6a0c66f41ff050e0c256ef3a3493b4eaf6b`
- TIMESTAMP_UTC: 2026-08-16T02:06:29Z
- REGRESSION: 302 passed / 0 failed (24.79 s) · DOMAIN 47/47
- COMPILEALL / GIT_DIFF_CHECK / SECRET_SCAN: PASS / PASS / PASS

## VERDICT: PASS

**BLOCKERS: NONE.**

### Los quince bloqueantes financieros históricos: 15/15 CERRADOS con evidencia propia

Incluido el hueco del parseo de la generación 7, reproducido con el `ReviewService` **real** y
payloads round-trip por `review_sales.payload_json`: 5 filas (branch vacío + total con separador de
miles + 3 sanas) dieron `{registered: 3, rejected: 2}`, cobertura 5/5, sin truncar.

### CURRENT_FIX_RISKS

`AccessDenied` sigue propagando, verificado por tres vías. La guarda no oculta errores de
infraestructura. Ninguna fila válida se cuenta como `rejected` (30 filas heterogéneas dieron 30
registradas, 0 rechazadas). `skipped`, `invalid_date` y `rejected` se distinguen correctamente.
Atomicidad confirmada: un error posterior al asiento de la reversa no deja escritura parcial.

### LEDGER_CONSISTENCY: intacta

44 verificaciones y **1.920 pasos de fuzz sobre 12 bases independientes**: `paid_amount` igual al
neto del libro en toda venta, `paid + balance == total`, nunca negativo, nunca sobrecobro, una sola
entrada activa, 0 dobles reversas, 0 períodos malformados, 0 REVERTIDA con dinero pagado. 5 % exacto
half-up sin floats verificado en unos 420 importes.

## Observaciones no bloqueantes

1. `sync_review_sales` no permite conciliar el lote: una fila ya registrada y sin cambios no
   incrementa ningún contador, y ante una excepción fuera de la terna la función no devuelve nada.
2. `rejected` es sólo un número: no queda traza de qué filas no se ingirieron.
3. `CommissionSaleInput` valida obligatoriedad sobre `str(valor)`, así que `None`, `0` o `[]` pasan
   y el rechazo llega después como error de base. Sin impacto monetario.
4. El KPI `paid_amount` cae cuando una liquidación PAGADA pasa a OBSERVADA, pese a que ese dinero
   ya salió.
5. Los KPI de cobros parciales se calculan sobre el saldo actual: al cancelarse la venta, esos
   parciales dejan de figurar en el KPI del mes en que ocurrieron.
6. Ventas mixtas siguen clasificándose como COMUN; error conservador, sin regla aprobada.
7. Los botones de la UI no se deshabilitan por estado; el dominio rechaza la transición inválida y
   muestra el mensaje exacto.

### Residuo declarado, no alcanzable

La guarda enumera tres tipos y no garantiza el absoluto que su comentario afirmaba: `Infinity`, un
`envelope` como array o `branch=None` escapan por `OverflowError`, `sqlite3.ProgrammingError` e
`IntegrityError`. **Ninguno es alcanzable** por el pipeline BC Caja → `import_snapshot` →
`review_sales`, y `sync_review_sales` no tiene llamador productivo.
