# Migración

`CentralRepository._migrate_commission_policy` corre dentro de `migrate()`, en la misma
transacción que el resto del esquema, cada vez que se abre la base. Es idempotente y **no toca
dinero**.

## Pasos

1. **Columnas aditivas** (`_add_missing_columns`). Siete columnas nuevas sobre dos tablas
   existentes, todas con `DEFAULT`, más la tabla `commission_policy_versions`. Una base ya
   migrada las tiene y el paso se saltea.
2. **Retiro de políticas superadas.** Toda fila de `commission_policies` con una etiqueta retirada
   o con alcance distinto de `GENERAL` se asienta en `central_audit` como
   `COMMISSION_POLICY_RETIRED`, con su `rate_bp` y su estado anteriores. Las de alcance
   `VENDEDORA` o `LOCAL` se eliminan: contradicen la decisión aprobada de un mismo 1% para todas.
   Nada desaparece en silencio — el valor previo queda en la auditoría.
3. **Instalación de la política canónica.** Si no hay una `GENERAL` con estado
   `CANONICA_APROBADA`, se inserta (o se actualiza por `ON CONFLICT(scope, scope_value)`) con
   `rate_bp = 100`, `code = COMISION_GENERAL_1PCT`, `version = 1`,
   `effective_from = 2026-08-01`, `created_by = MIGRACION`. La fila de versión se asienta con
   `INSERT OR IGNORE` sobre `UNIQUE(policy_id, version)`, de modo que reabrir la base no duplica
   versiones.
4. **Retiro de la etiqueta en las liquidaciones.** Una liquidación con etiqueta retirada y
   `rate_bp` no nulo pasa a `POLITICA_HISTORICA_PREVIA`; con `rate_bp` nulo, a
   `SIN_POLITICA_APLICADA`. **`rate_bp` y `commission_amount` no se tocan.**

## Qué le pasa a cada liquidación existente

| Estado previo | Efecto de la migración | Efecto del primer `recalculate` |
|---|---|---|
| `ELEGIBLE` / `CALCULADA` con 3% sintético | etiqueta → `POLITICA_HISTORICA_PREVIA`, importe intacto | pasa al 1% oficial con traza completa |
| `ELEGIBLE` / `CALCULADA` sin porcentaje | etiqueta → `SIN_POLITICA_APLICADA` | pasa al 1% oficial |
| `REVISADA` / `APROBADA` | etiqueta → `POLITICA_HISTORICA_PREVIA`, importe intacto | **no alcanzada**: fuera del `WHERE` |
| `PAGADA` | etiqueta → `POLITICA_HISTORICA_PREVIA`, importe intacto | **no alcanzada** |
| `OBSERVADA` / `REVERTIDA` | ídem | **no alcanzada** |

Una `REVISADA` o `APROBADA` con importe histórico queda visible como tal en la pantalla —el
desglose dice «Importe calculado con una política anterior a la regla aprobada»— y su corrección
es la vía manual que ya existía: observar o revertir y volver a calcular.

## Reversibilidad

El esquema es aditivo, así que una base migrada sigue siendo legible por el código anterior salvo
por las políticas de alcance eliminadas, cuyos valores quedaron en `central_audit`. No hay
`DROP`, no hay `ALTER` destructivo y no se reescribe ningún importe.

## Verificación

`test_migration_retires_the_synthetic_label_without_touching_money` reconstruye una base del
piloto anterior —3% sintético en la liquidación, política `GENERAL` sintética y una `VENDEDORA` al
5%—, la reabre y comprueba: una sola política `GENERAL` al 1%, el importe histórico de 14.250
intacto bajo `POLITICA_HISTORICA_PREVIA`, los dos retiros asentados en auditoría, y el recálculo
posterior trayéndola a 4.750 porque no estaba pagada.

`test_the_official_commission_survives_reopening_the_database` comprueba que reabrir vuelve a
migrar sin duplicar políticas ni versiones y sin cambiar nada (`changed == 0`).
