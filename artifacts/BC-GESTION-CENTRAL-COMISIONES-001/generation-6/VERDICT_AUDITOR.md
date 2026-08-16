# Auditor independiente — Generación 6

- RUNNER_ID: `AUDITOR-IND-COMISIONES-006`
- SNAPSHOT_COMMIT: `aed7bb2e4b370aeaa884008efab31dec16a965b2`
- SNAPSHOT_TREE: `f4f8aead7692f81cecd3ee9b466263d2745f1823`
- TIMESTAMP_UTC: 2026-08-16T01:20:00Z
- SCOPE_DIFF vs base: 43 archivos, +4303/−0. vs generación 5: 14 archivos, +408/−62.
- ISOLATION / MAIN_UNTOUCHED / FORCE_PUSH / REMOTE_SYNC: OK / OK / ninguno / 0 ahead · 0 behind

## VERDICT: PASS

BLOCKERS: NONE

### Invariantes verificados por ejecución real

- **PAID_INVARIANT: 79 aserciones, 0 fallos.** Las tres únicas sentencias que escriben `REVERTIDA`
  atacadas con una liquidación pagada. Fuzz de 120 secuencias × 35 operaciones: 0 entries con
  `paid_at` en REVERTIDA, 0 ventas con dos entries con `paid_at`.
- **DOUBLE_PAYMENT_POSSIBLE: NO.**
- **SOURCE_CORRECTION_INVARIANT: cerrado.** El descenso CONVENIO→COMÚN ejecutado con la liquidación
  en los **cinco** estados alcanzables: en todos, `settled == 0` —no queda dinero jamás cobrado
  sosteniendo la venta— y el cobro real posterior se acepta y liquida la venta de verdad. El
  descenso no destruye cobros reales y no duplica reversas.
- **PAYMENT_LEDGER_INTEGRITY: cumplido.** `paid == COBRO + CONVENIO − REVERSA` sin un solo desvío;
  cero `UPDATE`/`DELETE` sobre el libro y el historial; migración aditiva idempotente.
- **PACKAGE_TRUTHFULNESS: cumplido.** La afirmación de `COMMISSION_RULES.md` sobre el descenso
  CONVENIO→COMÚN, falsa en la generación 5, ya no contradice al código.

## Observaciones no bloqueantes

1. `COMMISSION_RULES.md` afirma sin condición que al convertir un CONVENIO en venta común «el saldo
   se reabre por completo: no existían cobros que arrastrar». Cierto para la venta nacida CONVENIO,
   pero impreciso en el camino COMÚN→CONVENIO→COMÚN, donde sí hay cobros previos y el código,
   correctamente, los conserva. La imprecisión va en la dirección segura.
2. `HANDOFF.md` hallazgo 4 sostiene que OBSERVADA «no tiene salida de corrección ni en la API ni en
   la UI»; `revert()` acepta OBSERVADA cuando no hubo pago y la UI expone el botón «Revertir». El
   documento subestima una capacidad existente.
3. `ARTIFACT_CONSISTENCY.md` se titula «PASS (generación N)»; el cuerpo aclara que no hubo revisión,
   pero un rótulo «PASS» autoemitido puede confundirse con un verdict de revisor.
4. `test_downgrading_an_agreement_to_a_common_sale_reopens_the_balance` cierra con una aserción casi
   tautológica que pasaría ante una regresión; la propiedad real la cubren las líneas anteriores.
5. Las liquidaciones OBSERVADA siguen sumando a los KPIs informativos. Ya declarado como hallazgo
   abierto.
6. `ARCHITECTURE.md` afirma que `paid_amount` «nunca se asigna por fuera del libro»; en el alta el
   valor se escribe directo, aunque la misma transacción asienta la fila por el mismo importe.
   Holgura de redacción, no divergencia de datos.
7. `ARCHITECTURE.md` no documenta `_reverse_agreement_settlement`, la corrección central de esta
   generación. Omisión, no falsedad.
8. `origin/main` = 098a9fb frente a `main` local = d88f5956: divergencia preexistente ajena a la
   misión, que conviene que el propietario conozca.
