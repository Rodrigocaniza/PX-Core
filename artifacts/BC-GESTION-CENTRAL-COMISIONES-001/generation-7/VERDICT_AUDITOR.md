# Auditor independiente — Generación 7

- RUNNER_ID: `AUDITOR-IND-COMISIONES-007`
- SNAPSHOT_COMMIT: `cfc43718d85fdbb260f0f6d2663eb025991643eb`
- SNAPSHOT_TREE: `0ad165244ed475e3aaa21b4013de7a5386323eb4`
- TIMESTAMP_UTC: 2026-08-16T01:35:44Z
- SCOPE_DIFF vs base: 46 archivos, +4635/-0. vs generación 6: 14 archivos, +396/-64.
- ISOLATION / MAIN_UNTOUCHED / FORCE_PUSH / REMOTE_SYNC: PASS / PASS / NO / 0 ahead · 0 behind

## VERDICT: PASS

**BLOCKERS: NONE.**

### Invariantes verificados por ejecución, no por lectura

- **PAID_INVARIANT: PASS.** Las tres únicas sentencias que escriben `REVERTIDA` atacadas con
  liquidaciones efectivamente pagadas, incluida la ruta nueva de la generación 7 (corrección a la
  baja de un convenio pagado). Control negativo confirmado: sin pago sí revierte, o sea la guarda
  discrimina de verdad. Barrido global: cero transiciones `PAGADA→REVERTIDA`.
- **DOUBLE_PAYMENT_POSSIBLE: NO.** Intento explícito de fabricar una segunda liquidación pagable
  reabriendo el saldo: siguió habiendo una sola entrada activa.
- **SOURCE_CORRECTION_INVARIANT: PASS.** Siete correcciones encadenadas al alza y a la baja: en las
  siete el libro cerró, el descuento fue exactamente 5 % half-up y la base = total − descuento.
  Corrección por debajo de lo realmente cobrado: rechazada **y el libro queda byte-idéntico**.
- **PAYMENT_LEDGER_INTEGRITY: PASS.** Identidad contable, no negatividad, append-only real y
  migración aditiva sobre el esquema anterior sin pérdida.
- **PACKAGE_TRUTHFULNESS: PASS con observaciones.** 300/300, 45 + 4 = 49, manifest 44/44, ZIP 45/45,
  18 verdicts = 6 PASS + 12 FAIL. Ningún documento afirma la revisión de generación 7.
- `AccessDenied` hereda de `PermissionError`, no de `ValueError`: el `except` de
  `sync_review_sales` **no** puede tragarse un fallo de permisos. Verificado explícitamente.

134 comprobaciones adversariales propias, más la regresión completa.

## Observaciones no bloqueantes

1. `HANDOFF.md` ítem 4 sólo es cierto para la `OBSERVADA` ya pagada; para la no pagada hay dos
   salidas reales. El documento se contradice con su propio ítem 15.
2. `ARCHITECTURE.md` sostiene que `paid_amount` «nunca se asigna por fuera del libro», pero en el
   alta se escribe directo. El invariante **de resultado** sí se cumple: imprecisión de mecanismo.
3. `ARCHITECTURE.md` sigue sin documentar `_reverse_agreement_settlement`, que en la generación 7
   dejó de ser un caso de borde para ejecutarse en **toda** corrección de un convenio. Por esa
   omisión, la viñeta sobre el rechazo se lee como una prohibición más fuerte de la real.
4. `COMMISSION_RULES.md` sigue afirmando que al convertir un convenio en venta común «no existían
   cobros que arrastrar»; falso en el camino COMÚN→CONVENIO→COMÚN, que el código maneja bien.
5. Persiste la aserción casi tautológica, y la prueba nueva repite el patrón.
6. `main` local 82 commits detrás de `origin/main`: preexistente, ajeno a la rama.
7. La atribución de rutas a `REVERTIDA` por función en la máquina de estados es laxa; el conjunto
   de estados de origen sí es completo.
