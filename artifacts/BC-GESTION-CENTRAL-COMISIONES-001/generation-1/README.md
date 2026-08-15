# Generación 1 — evidencia histórica preservada

Snapshot: `c24b4f19c66dc685d1679ed266eb887f2dbfe773` / tree `d296c6384885176399dceeeda103a4acb397e43d`.
**Generación INVALIDADA** por dos FAIL de revisores independientes. Se conserva íntegra como evidencia.

## Contenido

| Archivo | Origen | Verdict |
|---|---|---|
| `VERDICT_LIBRARIAN.md` | runner independiente `LIBRARIAN-IND-COMISIONES-001` | PASS |
| `VERDICT_QA.md` | runner independiente `QA-IND-COMISIONES-001` | **FAIL** (bloqueante Q1) |
| `VERDICT_AUDITOR.md` | runner independiente `AUDITOR-IND-COMISIONES-001` | **FAIL** (bloqueantes A1, A2, A3) |
| `SELF_REVIEW_LIBRARIAN.md` | autorrevisión de la ejecución implementadora | PASS (SELF_REVIEW, no independiente) |
| `SELF_REVIEW_QA.md` | autorrevisión de la ejecución implementadora | PASS (SELF_REVIEW, no independiente) |
| `SELF_REVIEW_AUDITOR.md` | autorrevisión de la ejecución implementadora | PASS (SELF_REVIEW, no independiente) |

Los tres `SELF_REVIEW_*` se movieron aquí **sin modificar una sola línea de su contenido**.
Estaban en la raíz del paquete durante la generación 1.

## ERRATA sobre `SELF_REVIEW_AUDITOR.md`

Ese documento afirmaba: «Ninguna ruta lleva `PAGADA` a `REVERTIDA`».
**La afirmación era falsa** contra el snapshot de generación 1, y el auditor independiente la
refutó por ejecución real (bloqueante A3 en `VERDICT_AUDITOR.md`). Es exactamente el tipo de
error que una autorrevisión no puede detectar y que justifica exigir independencia real.

El defecto fue corregido en la generación 2. La afirmación se conserva aquí sin retocar
precisamente para dejar registro de que la autorrevisión falló.

## Por qué se invalidó

- **Q1** — `_month()` no validaba la fecha: `"2099-4-10"` producía el período `"2099-4-"` y la
  comisión desaparecía de todos los reportes mensuales sin ningún error.
- **A1/A2** — `observe()` seguido de `revert()` llevaba una liquidación `PAGADA` a `REVERTIDA`,
  liberando el índice de unicidad y habilitando un segundo pago de la misma venta mientras el
  reporte ocultaba el primero.
- **A3** — `ARCHITECTURE.md` y `SELF_REVIEW_AUDITOR.md` afirmaban un invariante que el código
  no cumplía.
