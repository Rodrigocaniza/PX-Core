# Auditor independiente — Generación 5

- RUNNER_ID: `AUDITOR-IND-COMISIONES-005`
- SNAPSHOT_COMMIT: `0f735f714aab454f714a9af45beb7bda13c301cc`
- SNAPSHOT_TREE: `76f475e975a9768a474a0d00e06d1ac3a69bc66e`
- TIMESTAMP_UTC: 2026-08-16T01:01:39Z
- SCOPE_DIFF vs base: 40 archivos, +3957/−0. vs generación 4: 15 archivos, código sólo en `comisiones.py`.
- ISOLATION / MAIN_UNTOUCHED / FORCE_PUSH / REMOTE_SYNC: PASS / PASS / PASS / PASS

## VERDICT: FAIL

### Invariantes verificados por ejecución real

- **PAID_INVARIANT: PASS.** Tres —y sólo tres— sentencias escriben `REVERTIDA`; las tres atacadas
  con una liquidación pagada; ninguna ruta la lleva a `REVERTIDA`.
- **DOUBLE_PAYMENT_POSSIBLE: NO.**
- **SOURCE_CORRECTION_INVARIANT: PASS.**
- **PAYMENT_LEDGER_INTEGRITY: PASS.** 125 aserciones; en toda secuencia
  `paid == COBRO + CONVENIO − REVERSA`, `paid + balance == total`, `0 ≤ paid ≤ total`. Append-only
  confirmado. Migración sobre esquema anterior: preserva datos y es idempotente.

### BLOQUEANTE B1 — comisión pagable sin un solo cobro del cliente

Una corrección de origen que convierte un CONVENIO en venta común dejaba la venta liquidada por
completo con dinero que el cliente nunca pagó, y sin salida correctiva. Ejecutado: convenio de
500.000 → el origen corrige a `kind=COMUN, initial_paid=0` → `paid_amount=500.000`, `balance=0`,
entry ELEGIBLE, y por el flujo normal llegaba a **PAGADA** con comisión de 25.000 sobre una venta
común con **cero** filas `COBRO`. El asiento `CONVENIO` era estructuralmente irreversible.
Viola la regla aprobada 1. Ninguna prueba cubría el descenso CONVENIO→COMÚN.

### BLOQUEANTE B2 — `COMMISSION_RULES.md` afirmaba lo contrario de lo que hacía el código

El documento decía: «si una corrección de origen convierte un CONVENIO en venta común, el saldo se
reabre por completo». Falso contra ese snapshot: el saldo quedaba en 0 y la venta seguía cancelada.
La afirmación describía el comportamiento de la generación 4 y no se actualizó al convertir el
libro en fuente de verdad.

## Observaciones no bloqueantes

- `HANDOFF.md` declaraba abierto un hallazgo (`revert_payment` y ventas anuladas) que el código ya
  cerraba: el paquete se contradecía, en la dirección segura.
- `ARCHITECTURE.md` dice que `paid_amount` «siempre es `_settled_amount()`»; en el alta el valor se
  asigna desde la entrada. El invariante sustantivo se cumple; la redacción literal es imprecisa.
- Una corrección de origen que declara **menos** cobrado se ignora en silencio (el libro nunca se
  reduce). Coherente con append-only, pero no documentado.
- `main` local está 82 commits detrás de `origin/main`: divergencia preexistente ajena a la misión.
