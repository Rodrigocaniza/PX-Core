# Evidencia de pruebas

Regresión completa: **323/323 PASS** (`python -m pytest -q`, 28,74 s).
Línea base de la misión anterior: 302. Esta misión suma **21**: 20 de dominio y 1 de interfaz.

Suite del módulo: `tests/gestion_central/` **123/123 PASS**.
Los dos archivos de comisiones juntos (`test_comisiones.py` + `test_comisiones_ui_interactions.py`):
51 → **72** pruebas, 67 y 5 respectivamente.

Todas las cifras anteriores son **casos ejecutados**, que es lo que cuenta pytest. En funciones:
`test_comisiones.py` pasa de 47 a 65 —se agregan 19 y se elimina
`test_policy_is_synthetic_pending_approval_and_optional`, que afirmaba lo contrario de la decisión
aprobada—, y dos de las nuevas están parametrizadas sobre `REVISADA` y `APROBADA`, de donde salen
los 67 casos. La de interfaz agrega una función y un caso.

## Validaciones dirigidas exigidas por la misión

| Validación | Prueba |
|---|---|
| Venta común 400.000 cancelada → 4.000 | `test_a_cancelled_common_sale_of_400000_commissions_exactly_4000` |
| Venta común con saldo → comisión pagable 0 | `test_a_common_sale_with_balance_has_zero_payable_commission` |
| Convenio 500.000 → 25.000 / 475.000 / 4.750 | `test_an_agreement_of_500000_discounts_25000_and_commissions_4750` |
| Mismo 1% para toda vendedora y local | `test_the_same_one_percent_applies_to_every_saleswoman_and_branch` |
| Recalcular no duplica | `test_recalculating_never_duplicates_and_never_reapplies` |
| `PAGADA` no cambia en silencio | `test_a_paid_settlement_is_never_touched_by_a_policy_change` |
| Anulación/reversión conserva auditoría | `test_voiding_and_reverting_keep_the_audit_trail_of_the_policy` |
| Redondeo `HALF_UP` probado | `test_half_up_rounding_to_whole_guarani_is_explicit` |
| Persistencia y reapertura | `test_the_official_commission_survives_reopening_the_database` |
| Interfaz correcta | `test_the_screen_names_the_official_one_percent_policy` |
| Export correcto | `test_structured_export_has_stable_contract_and_no_customer_data` |

| Un porcentaje retirado nunca se paga | `test_a_retired_rate_can_never_be_paid_through_the_normal_flow` |
| La reparación existe y no destruye la comisión | `test_recalculating_repairs_a_retired_rate_and_withdraws_its_approval` |

## Pruebas nuevas de dominio (19 funciones, 21 casos)

1. `test_the_official_policy_is_the_approved_general_one_percent` — 1%, alcance único `GENERAL`,
   estado `CANONICA_APROBADA`, versión 1, vigencia, redondeo, moneda, y ninguna etiqueta retirada.
2. `test_a_cancelled_common_sale_of_400000_commissions_exactly_4000`.
3. `test_a_common_sale_with_balance_has_zero_payable_commission` — incluye el cobro parcial
   posterior, que sigue sin generar comisión.
4. `test_an_agreement_of_500000_discounts_25000_and_commissions_4750` — orden 5% → 1%.
5. `test_the_same_one_percent_applies_to_every_saleswoman_and_branch` — tres locales, tres
   vendedoras, un único `rate_bp` y un único importe.
6. `test_the_policy_used_is_traceable_on_every_settlement` — los cinco campos de traza, el bloque
   `policy` del desglose, la línea «Comisión oficial (1,00%…)» y la política en el historial.
7. `test_a_period_before_the_effective_date_never_applies_the_rate` — `FUERA_DE_VIGENCIA` y
   rechazo de `review`.
8. `test_half_up_rounding_to_whole_guarani_is_explicit` — 0,50→1; 1,50→2; 0,49→0; 12.345,67→12.346,
   más el mismo borde extremo a extremo por el servicio.
9. `test_recalculating_never_duplicates_and_never_reapplies` — cuatro recálculos, dos asientos
   de historial.
10. `test_a_paid_settlement_is_never_touched_by_a_policy_change` — se publica la versión 2 al 2% y
    la `PAGADA` conserva importe, `rate_bp`, `policy_version` y hasta su `updated_at`.
11. `test_publishing_a_policy_version_is_audited_and_idempotent` — idempotencia, versionado,
    porcentaje y vigencia inválidos, y el asiento de auditoría.
12. `test_voiding_and_reverting_keep_the_audit_trail_of_the_policy`.
13. `test_the_official_commission_survives_reopening_the_database` — reabrir no duplica ni cambia.
14. `test_migration_retires_the_synthetic_label_without_touching_money`.
15. `test_a_retired_rate_can_never_be_paid_through_the_normal_flow[REVISADA]` y `[APROBADA]` — el
    paso siguiente de la cadena de pago se corta en cada punto de entrada posible, y el desglose no
    llama «oficial» a un porcentaje retirado.
16. `test_recalculating_repairs_a_retired_rate_and_withdraws_its_approval[REVISADA]` y `[APROBADA]`
    — 33.250 → 4.750, vuelta a `CALCULADA`, revisión y aprobación retiradas, importe reemplazado en
    el historial bajo `COMMISSION_POLICY_REPAIRED`, idempotencia, y la cadena rehecha hasta el pago
    con el importe correcto.
17. `test_a_paid_legacy_settlement_keeps_its_amount_and_is_never_repaired` — lo que ya movió dinero
    conserva su importe histórico y `recalculate` no lo alcanza.
18. `test_the_trace_is_complete_exactly_when_the_policy_is_the_canonical_one` — invariante de traza
    en su forma verificable, sobre los tres estados de política que conviven en una misma base.

Y la decimonovena, `test_the_retired_label_survives_only_as_the_thing_the_migration_removes`,
que verifica sobre el
fuente que `SINTETICA_PENDIENTE_APROBACION` no aparece en `comisiones.py`, `comisiones_ui.py` ni
`repository.py`, y que en `comision_policy.py` figura una sola vez, dentro de
`RETIRED_POLICY_STATUSES`. Reemplaza a `test_policy_is_synthetic_pending_approval_and_optional`,
que afirmaba lo contrario y ya no puede ser cierto.

## Prueba nueva de interfaz (1)

`test_the_screen_names_the_official_one_percent_policy` — encabezado con porcentaje, código,
versión, vigencia y redondeo; KPI `COMISIÓN OFICIAL 1,00%`; encabezados de columna `Comisión 1,00%`
en ambas tablas; y la fila de una venta cancelada mostrando base 300.000 y comisión 3.000 sin
abrir el desglose.

## Pruebas preexistentes actualizadas

- `test_amounts_stay_integers_end_to_end`: sin `set_policy`; el 1% sobre 316.666 da 3.167.
- `test_source_correction_before_review_recomputes_the_whole_base`: 855.000 → 8.550.
- `test_an_agreement_total_can_be_corrected_downwards`,
  `test_source_correction_after_review_never_pays_a_stale_base`: se retira el `set_policy` sintético.
- `test_structured_export_has_stable_contract_and_no_customer_data`: `contract_version: 2`, bloque
  `policy` completo y los cuatro campos de traza en cada entrada.
- `test_navigation_filters_and_state_reasons` y `test_observe_revert_recalculate_and_export`: el
  desglose del convenio ahora tiene cuatro líneas y el export lleva la política.

Todas las demás pruebas de la misión anterior siguen intactas y en verde: los quince bloqueantes
financieros históricos y los cinco invariantes económicos continúan cubiertos por sus pruebas
originales, sin retoques.

## Fuera de alcance

No se corrigieron los hallazgos no bloqueantes heredados del handoff anterior. Siguen abiertos y
registrados; ver `HANDOFF.md`.
