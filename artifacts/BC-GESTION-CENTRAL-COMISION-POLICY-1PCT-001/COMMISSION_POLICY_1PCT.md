# Política canónica de comisión — 1% general

Contrato económico del porcentaje. Las reglas de elegibilidad, estados y convenio ya son canónicas
y están en `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/COMMISSION_RULES.md`: aquí sólo se define
el porcentaje, que era lo único que quedaba pendiente de aprobación.

## Cláusulas superadas del contrato anterior

De `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/COMMISSION_RULES.md` quedan **superadas**, y sólo
ellas:

- **Regla 5**, «No inventar un porcentaje general de comisión». El porcentaje ya está aprobado.
  Los estados `SIN_POLITICA_CONFIGURADA` y `SINTETICA_PENDIENTE_APROBACION` que esa regla describe
  ya no se producen, y la prueba que cita como evidencia
  (`test_policy_is_synthetic_pending_approval_and_optional`) fue eliminada.
- **Sección «Configuración pendiente de aprobación»**, que declara que el porcentaje «no es una
  regla productiva». Hoy lo es.
- La fórmula de redondeo allí documentada, `(importe * puntos_basicos + 5000) // 10000`. Da el
  mismo resultado que la implementación actual para enteros no negativos, pero la implementación
  es `Decimal` con `ROUND_HALF_UP`.

Las reglas 1 a 4 y 6 a 9 de ese documento siguen vigentes sin cambio alguno. Su encabezado lleva la
anotación con estas mismas tres cláusulas; su cuerpo se conserva sin retocar como evidencia de su
misión.

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

Cada liquidación se resuelve contra la versión que gobierna **su propio período**: la de vigencia
más reciente que no lo supera. No contra «la última publicada». Esa distinción es lo que impide que
programar el porcentaje del mes que viene reescriba el mes en curso.

Un período anterior a toda vigencia no recibe porcentaje hacia atrás: queda `FUERA_DE_VIGENCIA`,
con la base informada, el motivo visible en pantalla y sin poder revisarse ni pagarse.

La comparación es por período de liquidación —el mes en que la venta quedó cancelada— porque es la
misma unidad con la que se agrupa, se reporta y se exporta todo el módulo. Consecuencia conocida:
una vigencia fijada a mitad de mes rige el mes completo.

## Versionado

Cambiar el porcentaje es un hecho versionado, no una edición:

- `set_general_rate(actor, rate_bp, effective_from, note)` publica una versión nueva.
- La versión anterior queda íntegra en `commission_policy_versions`, que es append-only, y **sigue
  gobernando los períodos que le corresponden**: el historial se consulta en cada cálculo.
- **Una tasa publicada gobierna hacia adelante, y eso no se sostiene bloqueando la publicación.**
  La única guarda que queda en `set_general_rate` es que la vigencia **no puede retroceder**
  respecto de la última publicada, que ordena el historial.
- **Un período que alguna vez recibió una tasa queda fijado a ella.** La primera vez que se tarifa
  un período se graba una fila en `commission_rated_periods` —una por período, escrita una sola vez,
  nunca actualizada ni borrada— y `decide()` resuelve ese período contra esa fila, no contra el
  catálogo de versiones. Una versión nueva no lo reescribe aunque su vigencia lo abarque.
- **La protección no depende del estado de la liquidación.** Observar, revertir, anular la venta o
  corregir el origen cambian el estado; la evidencia sigue ahí. Ésa era la falla de la defensa
  anterior, que miraba `CALCULADA/REVISADA/APROBADA/PAGADA` y se desarmaba con `observe()` sobre una
  pagada.
- **Tampoco hay una frontera global.** La protección es el conjunto de períodos tarifados, no un
  techo: `2099-07` tarifado no impide publicar para `2099-08` ni para un futuro lejano, y una venta
  con fecha errónea en `2136` protege sólo `2136-04` sin congelar ningún mes intermedio. La defensa
  anterior tomaba `MAX(period)` global y bloqueaba todo lo anterior a la fecha equivocada.
- **Un período liquidado pero sin tasa no protege nada.** Un mes anterior a la vigencia queda
  `FUERA_DE_VIGENCIA` con la base informada y sin porcentaje: nunca fue tarifado, así que no fija
  nada y sigue siendo resoluble.
- Publicar **nunca es silencioso**: cada publicación asienta en `central_audit` la lista de períodos
  ya tarifados que quedan fuera de su alcance real.
- Corregir la tasa de un período ya tarifado exige un flujo separado de corrección explícita y
  auditada, **que hoy no existe**. No es un cambio de política: es otra decisión.
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
| `POLITICA_HISTORICA_PREVIA` | Importe calculado antes de la aprobación. **No es pagable.** |
| `SIN_POLITICA_APLICADA` | Todavía no recalculada. |

## Sólo se paga la política vigente

`review`, `approve` y `mark_paid` exigen tres cosas, en ese orden: que haya importe, que su
`policy_status` sea `CANONICA_APROBADA`, y que **el porcentaje y la versión grabados coincidan con
la política que rige hoy el período de esa liquidación**. Lo tercero importa tanto como lo primero:
el sello se graba al calcular y puede quedar atrás, así que comprobar sólo el sello dejaría pasar
al pago un importe que ya no es el oficial.

Una liquidación **no pagada** cuyo importe no sea el oficial, y **cuyo período esté en vigencia**,
tiene salida y no destruye la comisión: `recalculate` la repara, sea cual sea la causa —política
retirada, política ausente o versión superada—. La lleva al porcentaje vigente con traza completa y
la devuelve a `CALCULADA` **retirando su revisión y su aprobación** —el importe cambió, así que el
aval anterior ya no lo respalda—, con el importe reemplazado asentado en el historial como
`COMMISSION_POLICY_REPAIRED`. Luego se rehace la cadena sobre el importe correcto.

**Si el período es anterior a la vigencia, no hay reparación posible.** La decisión es
`FUERA_DE_VIGENCIA` y la liquidación queda con la base informada y sin porcentaje: un importe
heredado de ese período se retira y no se sustituye, y ninguna ruta pública lo devuelve —publicar
una vigencia que alcance ese período está prohibido por la guarda de período liquidado. Lo que sí
está garantizado es que **el importe retirado queda asentado**: `recalculate` escribe el bloque
`replaced` en toda rama que anule o reemplace un importe anterior, no sólo al reparar una `REVISADA`
o una `APROBADA`. Recuperar ese importe exigirá el flujo de corrección explícita que hoy no existe.

Una que **sí** movió dinero conserva su importe histórico intacto: `recalculate` no la alcanza —la
guarda es `paid_at IS NULL` sobre el `WHERE` entero, no sobre una rama— y su nota lo dice. Junto
con las `OBSERVADA` y `REVERTIDA` heredadas, son los casos en que un importe no oficial permanece;
ninguno es pagable, y los agregados los informan aparte.

## La comisión oficial no se mezcla

`report` y el export separan `commission_amount` —sólo lo calculado con la política aprobada— de
`non_official_amount`, que agrupa los importes heredados de una política retirada. El KPI que la
pantalla rotula «Comisión oficial 1,00%» suma exclusivamente lo primero, y cuando hay importes de
la segunda clase la bandeja muestra un aviso con su total. Por la misma razón las columnas de las
tablas se titulan «Comisión» a secas: una fila puede arrastrar un importe que no es el 1%.

`paid_amount` sí incluye los importes históricos ya pagados: ese dinero salió, y ocultarlo sería la
mentira contraria.

`SINTETICA_PENDIENTE_APROBACION` queda **retirada**. Ningún código la produce; sobrevive únicamente
como entrada de `RETIRED_POLICY_STATUSES`, que es la lista de lo que la migración elimina.

## Trazabilidad

Cada liquidación graba, en el momento del cálculo, la política con la que se calculó:
`policy_code`, `policy_version`, `policy_effective_from`, `policy_scope` y `policy_status`, junto a
`rate_bp` y `commission_amount`. No se reconstruye después: si la política cambia mañana, la
liquidación sigue explicando su propio importe con la versión que efectivamente usó.

La traza está **completa o vacía, nunca a medias**. Completa cuando una política llegó a evaluar la
liquidación: `CANONICA_APROBADA` con su importe, o `FUERA_DE_VIGENCIA` sin importe que respaldar.
Vacía cuando ninguna la evaluó: `POLITICA_HISTORICA_PREVIA` —calculada antes de la aprobación— y
`SIN_POLITICA_APLICADA` —aún sin recalcular—. La ausencia no es una omisión: dice con precisión que
**ninguna política aprobada produjo ese importe**. La migración no la inventa, porque no sabe con
qué versión se calculó. Por eso ese importe tampoco es pagable.

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
