# QA independiente — Generación 3

- RUNNER_ID: `QA-IND-COMISIONES-003`
- ROLE: QA
- SNAPSHOT_COMMIT: `4c4cf54215fd9e080b5793931524bf1e3e1cda61`
- SNAPSHOT_TREE: `5e5377c89aeaa2862823f461a3c7ae59f4292996`
- WORKTREE_CLEAN_BEFORE / AFTER: YES / YES
- TIMESTAMP_UTC: 2026-08-16T00:22:08Z
- REGRESSION: 287 passed / 0 failed (31.62 s) · DOMAIN 32/32 · UI 4/4
- COMPILEALL / GIT_DIFF_CHECK / SECRET_SCAN: PASS / PASS / PASS
- INDEPENDENT_CHECKS: 151 aserciones propias, 145 OK / 6 hallazgos

## VERDICT: FAIL

### Bloqueantes heredados: los tres CERRADOS y verificados por ejecución propia

- **G1-Q1 (fecha/período)**: 27/27 rechazos de fechas inválidas en alta, cobro y pago; todo
  `period` persistido cumple `\d{4}-(0[1-9]|1[0-2])`.
- **G1-A1/A2 (pagada → revertida)**: `revert` directo y `observe()`+`revert()` rechazados; una sola
  fila con `paid_at`; ninguna segunda liquidación pagable.
- **G2 (base congelada en REVISADA)**: los tres escenarios terminan en OBSERVADA con `approve` y
  `mark_paid` rechazados. Barrido de 20 combinaciones (4 escenarios × 5 estados): 0 filas con
  `commissionable_base > gross_amount`, 0 aritméticamente imposibles aprobables o pagables.

**REGRESSION_FROM_FIXES: NINGUNA.**

### BLOQUEANTE NUEVO 1 — la comisión de una venta realmente cobrada se pierde tras una reversión

`comisiones.py:356-360`. La clave de idempotencia de `register_payment` no contemplaba que el
cobro hubiera sido revertido, y el chequeo no excluía los cobros ya reversados.

Reproducción verificada: venta COMUN 400.000 → cobro de 400.000 el 2099-04-28 → ELEGIBLE período
2099-04 → `revert_payment` motivada → PENDIENTE_SALDO con saldo 400.000 → **re-cargar el mismo
recibo real devuelve `(None, False)`, sin excepción y sin asiento en el historial**, indistinguible
de un duplicado legítimo. Estado final: `paid_amount=0`, `balance_amount=400.000`, base del período
0. El dinero fue cobrado y la vendedora nunca cobra su comisión: **subpago del 100%**. El único
workaround era falsear la fecha, lo que además misatribuye el período (2099-05 en lugar del real
2099-04), moviendo la comisión de mes.

### BLOQUEANTE NUEVO 2 — dos cobros parciales legítimos idénticos se colapsan en uno

Venta de 400.000 con dos cobros reales de 200.000 el mismo día y misma referencia (opcional, con
default vacío): el segundo devolvía `(None, False)`, dejando `paid_amount=200.000` y un saldo
fantasma de 200.000 que mantenía la liquidación en PENDIENTE_SALDO indefinidamente. La API no podía
distinguir «ya lo registraste» de «es un segundo cobro genuino».

**Atenuante declarado por el propio revisor**: `register_payment`, `revert_payment` y `void_sale`
no tienen hoy llamador productivo fuera de los tests; el panel es de sólo lectura para el ciclo de
vida de la venta. El defecto es latente a nivel de API, no alcanzable desde la UI del piloto —
pero «cobro parcial» y «reversión motivada» están explícitamente en alcance de esta misión.

## Observaciones no bloqueantes

- **Fechas ISO alternativas persisten crudas** (residual acotado de G1-Q1). `date.fromisoformat`
  acepta `"20990410"` y `"2099-W15-1"`; el período sale correcto pero `list_entries`/`report`
  filtran por `substr(sale_date,1,7)`, de modo que una venta con esa forma no aparece en el
  período. No hay productor en el repo que la genere.
- La liquidación OBSERVADA es un callejón sin salida por diseño; no existe hoy vía de corrección
  manual en la API ni en la UI para las que el propio código manda a OBSERVADA con el texto
  «requiere corrección manual».
- Tras una corrección de origen post-pago, `commission_sales.saleswoman` refleja la vendedora nueva
  mientras la liquidación pagada conserva la anterior. Correcto contablemente, pero el panel no
  señala la discrepancia.
- Cosméticos de UI: badge piloto duplicado (shell + panel) y el signo «×» delante de un importe que
  ya es el producto.
