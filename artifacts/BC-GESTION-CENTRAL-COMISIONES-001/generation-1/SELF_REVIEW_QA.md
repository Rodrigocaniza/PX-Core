# QA

**Verdict: PASS (SELF_REVIEW)** — emitido por la misma ejecución que implementó la misión.
**No cuenta como revisión independiente.** Ver `INDEPENDENCE.md`.

## Cobertura obligatoria

| Requisito | Prueba |
|---|---|
| Venta común con saldo | `test_common_sale_with_balance_is_not_commissionable_yet` |
| Cancelación posterior | `test_cancellation_enters_the_period_of_its_settlement` |
| Entrada en el período correcto | `test_cancellation_enters_the_period_of_its_settlement` (abril 0, mayo 400.000) |
| Cobro parcial no pagable | `test_partial_payment_stays_informative_and_never_pays` |
| Convenio con deducción exacta del 5% | `test_agreement_deducts_exactly_five_percent_and_creates_no_client_balance` |
| Convenio sin saldo cliente | mismo test (`register_payment` rechaza el cobro) |
| Venta anulada | `test_voided_sale_never_generates_commission` |
| Reversión de cancelación | `test_reverting_a_cancellation_reverts_the_commission_effect_and_keeps_history` |
| Duplicado rechazado | `test_duplicate_registration_is_rejected_and_identity_is_stable`, `test_duplicate_payment_key_is_idempotent` |
| Recálculo idempotente | `test_recalculation_is_idempotent` (2ª pasada: `changed = 0`) |
| Múltiples vendedoras y locales | `test_multiple_saleswomen_locals_and_monthly_filters` |
| Filtros mensuales | mismo test + `test_navigation_filters_and_state_reasons` |
| Aprobación | `test_approval_flow_blocks_payment_without_approval` |
| Pago | mismo test |
| Intento de pago sin aprobación | mismo test (bloqueado desde `CALCULADA` y desde `REVISADA`) |
| Observación | `test_observation_and_motivated_reversal_require_reason` |
| Reversión motivada | mismo test |
| Historial append-only | `test_state_contract_and_append_only_history` |
| Persistencia y reapertura | `test_persistence_survives_reopening` |
| Importes enteros | `test_amounts_stay_integers_end_to_end` |
| Integración con supervisión | `test_review_sales_integration_skips_non_sale_rows` |
| Liquidación pagada no modificable en silencio | `test_paid_settlement_is_never_modified_silently` |
| Smoke visual 1920×1080 | `test_full_hd_layout_keeps_every_control_visible` + captura |

## Resultados

- Dominio de comisiones: **25/25 PASS**.
- Interacción Tk y Full HD: **4/4 PASS**.
- Regresión completa: **280/280 PASS** en 33.08 s (base heredada 251 + 29 nuevas).
- `compileall`: PASS.
- `git diff --check`: PASS.
- Escaneo heurístico de secretos: PASS (coincidencias sólo en el test de prohibición).

## Casos límite verificados a mano y luego fijados en prueba

- Recálculo repetido tres veces sobre un convenio: el 5% se aplica **una sola vez**.
- Cobro que supera el saldo: rechazado con mensaje explícito.
- Corrección de origen tras aprobación: produce `OBSERVADA`, no una modificación silenciosa.
