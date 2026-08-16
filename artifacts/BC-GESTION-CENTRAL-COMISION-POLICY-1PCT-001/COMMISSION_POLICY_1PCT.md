# Política canónica de comisión — 1% general

Contrato económico del porcentaje. Las reglas de elegibilidad, estados y convenio ya son canónicas
y están en `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/COMMISSION_RULES.md`: aquí sólo se define
el porcentaje, que era lo único que quedaba pendiente de aprobación.

## Decisión aprobada

| Propiedad | Valor |
|---|---|
| Código | `COMISION_GENERAL_1PCT` |
| Alcance | `GENERAL` — único, sin alcance por vendedora ni por local |
| Porcentaje | `1,00%` (`rate_bp = 100`) |
| Estado | `CANONICA_APROBADA` |
| Versión inicial | `1` |
| Vigencia desde | `2026-08-01` |
| Redondeo | `HALF_UP` a guaraní entero |
| Moneda | `GS` |

Fuente única: `modulos/gestion_central/comision_policy.py`. La leen tanto el cálculo
(`comisiones.py`) como la migración (`repository.py`), así que no puede haber dos verdades.

## Orden de aplicación

1. **Convenio**: descontar primero el 5% del total. Base = total − 5%.
   Venta común: base = total.
2. Aplicar el 1% sobre la base resultante.
3. Redondear con `HALF_UP` a guaraní entero.

Nunca al revés, y el 5% se aplica exactamente una vez.

```
Convenio 500.000 → 5% = 25.000 → base 475.000 → 1% = 4.750
Común    400.000 → base 400.000 → 1% = 4.000
```

## Cuándo se paga

El 1% se calcula sobre toda liquidación elegible, pero sigue rigiendo la regla ya canónica: la
venta común sólo es elegible **al quedar totalmente cancelada**. Con saldo pendiente la base es 0,
no hay porcentaje aplicado y la comisión pagable es 0. Los cobros parciales siguen siendo
informativos. Las ventas anuladas no comisionan. Gastos y entregas a administración no intervienen.

## Vigencia

La política rige para las liquidaciones cuyo **período** no es anterior al mes de su vigencia. Un
período anterior no recibe el porcentaje hacia atrás: queda `FUERA_DE_VIGENCIA`, con la base
informada, el motivo visible en pantalla y sin poder revisarse ni pagarse.

La comparación es por período de liquidación —el mes en que la venta quedó cancelada— porque es la
misma unidad con la que se agrupa, se reporta y se exporta todo el módulo.

## Versionado

Cambiar el porcentaje es un hecho versionado, no una edición:

- `set_general_rate(actor, rate_bp, effective_from, note)` publica una versión nueva.
- La versión anterior queda íntegra en `commission_policy_versions`, que es append-only.
- La operación es idempotente: repetir el mismo porcentaje y la misma vigencia no crea versión.
- Cada publicación se asienta en `central_audit` como `COMMISSION_POLICY_VERSION_PUBLISHED`.
- **Publicar una versión nueva no recalcula nada por sí sola** y jamás toca lo ya pagado.

No existe API para fijar un porcentaje por vendedora o por local. La decisión aprobada es el mismo
1% para todas, y la firma de `CanonicalCommissionPolicy.decide(branch=…, saleswoman=…)` recibe
ambos datos justamente para dejar explícito que no alteran el resultado.

## Estados de política de una liquidación

| Estado | Significado |
|---|---|
| `CANONICA_APROBADA` | Calculada con la regla aprobada vigente. |
| `FUERA_DE_VIGENCIA` | Período anterior a la vigencia: base informada, sin porcentaje. |
| `POLITICA_HISTORICA_PREVIA` | Importe calculado antes de la aprobación; se conserva por auditoría. |
| `SIN_POLITICA_APLICADA` | Todavía no recalculada. |

`SINTETICA_PENDIENTE_APROBACION` queda **retirada**. Ningún código la produce; sobrevive únicamente
como entrada de `RETIRED_POLICY_STATUSES`, que es la lista de lo que la migración elimina.

## Trazabilidad

Cada liquidación graba, en el momento del cálculo, la política con la que se calculó:
`policy_code`, `policy_version`, `policy_effective_from`, `policy_scope` y `policy_status`, junto a
`rate_bp` y `commission_amount`. No se reconstruye después: si la política cambia mañana, la
liquidación sigue explicando su propio importe con la versión que efectivamente usó.

Una corrección de origen que invalida el cálculo también borra la traza, porque la que había ya no
describe el importe que se va a recalcular.

## Aritmética

`Decimal` con `ROUND_HALF_UP`, con la precisión del contexto ampliada a 60 dígitos para que el
cociente por 10.000 sea exacto y el **único** redondeo del cálculo sea el `HALF_UP` final. No se
usan floats en ningún punto: la prueba `test_no_external_provider_or_secrets_in_module` sigue
verificándolo sobre el fuente.

Medio guaraní sube, no trunca ni redondea al par:

| Importe × tasa | Exacto | Resultado |
|---|---:|---:|
| 50 × 1% | 0,50 | **1** |
| 150 × 1% | 1,50 | **2** |
| 49 × 1% | 0,49 | **0** |
| 1.234.567 × 1% | 12.345,67 | **12.346** |
