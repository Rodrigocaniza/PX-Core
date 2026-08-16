# Contrato de reglas económicas implementadas

Sólo se implementan las reglas ya aprobadas. Nada se infiere ni se inventa.

| # | Regla aprobada | Implementación | Prueba |
|---|---|---|---|
| 1 | La venta común comisiona sólo al quedar totalmente cancelada | `register_payment` promueve a `ELEGIBLE` únicamente cuando `balance_amount` llega a 0 | `test_cancellation_enters_the_period_of_its_settlement` |
| 2 | Los cobros parciales son informativos y no generan comisión pagable | La liquidación permanece en `PENDIENTE_SALDO`; el cobro se registra como `PARTIAL_PAYMENT_INFORMATIVE` y sólo suma al KPI informativo | `test_partial_payment_stays_informative_and_never_pays` |
| 3 | El convenio se considera venta finalizada aunque la empresa pague después | `register_sale` deja el convenio `ELEGIBLE` en el período de la venta | `test_agreement_deducts_exactly_five_percent_and_creates_no_client_balance` |
| 4 | Base del convenio = total − 5% | `agreement_discount()` con puntos básicos enteros (`AGREEMENT_DISCOUNT_BP = 500`) | `test_amounts_stay_integers_end_to_end`, `test_agreement_discount_applies_exactly_once_even_after_repeated_recalculation` |
| 5 | No inventar un porcentaje general de comisión | Sin política configurada la liquidación informa `rate_bp = NULL`, `commission_amount = NULL` y `policy_status = SIN_POLITICA_CONFIGURADA`; con política, `SINTETICA_PENDIENTE_APROBACION` | `test_policy_is_synthetic_pending_approval_and_optional` |
| 6 | El convenio no crea saldo cliente ni altera BC Caja | El convenio nace con `balance_amount = 0`; `register_payment` lo rechaza; no se tocó ningún módulo de BC Caja | `test_agreement_deducts_exactly_five_percent_and_creates_no_client_balance` |
| 7 | Gastos y entregas a administración no comisionan | `CommissionSaleInput` exige total positivo y `sync_review_sales` descarta filas sin total ni vendedora | `test_expenses_and_administration_deliveries_never_enter_the_ledger`, `test_review_sales_integration_skips_non_sale_rows` |
| 8 | Las ventas anuladas no generan comisión | `void_sale` lleva la liquidación abierta a `REVERTIDA` (o a `OBSERVADA` si ya estaba pagada) | `test_voided_sale_never_generates_commission` |
| 9 | Toda edición, anulación, reversión o recálculo conserva auditoría | Cada transición escribe en `commission_entry_history` (append-only) | `test_state_contract_and_append_only_history` |

## Período de comisión

- **Venta común**: período del mes en que el saldo llega a cero (`cancelled_date`), no el de la venta.
- **Convenio**: período de la venta finalizada.
- **Venta con saldo**: `PENDIENTE_SALDO`, sin período asignado; visible en el mes de su venta.
- **Reversión de una cancelación**: la liquidación pasa a `REVERTIDA` conservando su período e historial, y se abre una nueva liquidación `PENDIENTE_SALDO`. Nunca se mueve una comisión de período en silencio.

## Cobros, reversas y convenio

- La idempotencia de un cobro la decide el llamador con `idempotency_key`. Sin clave, cada llamada
  es un cobro real distinto: dos cobros genuinos idénticos el mismo día son dos cobros.
- Una reversa deshace el hecho: el mismo cobro puede volver a cargarse con su fecha real, y la
  comisión vuelve al período que le corresponde.
- Un convenio nunca registra un cobro de cliente. Por eso, si una corrección de origen convierte un
  CONVENIO en venta común, el saldo se reabre por completo: no existían cobros que arrastrar. Es
  coherente con la regla aprobada 6 y queda documentado aquí para que no sorprenda.

## Redondeo y enteros

Todos los importes son enteros de guaraníes. Los porcentajes se expresan en puntos básicos
enteros y se aplican con `apply_basis_points`, redondeo half-up sin floats:

```
resultado = (importe * puntos_basicos + 5000) // 10000
```

Ejemplo aprobado: total 500.000 → descuento 25.000 → base 475.000.

## Configuración pendiente de aprobación

El porcentaje de comisión **no** existe canónicamente. Se implementó un puerto
(`CommissionPolicyPort`) con una configuración sintética separada (`commission_policies`),
marcada siempre como `SINTETICA_PENDIENTE_APROBACION`. La bandeja calcula y muestra la base
comisionable aunque no haya porcentaje. Esta configuración **no es una regla productiva**.
