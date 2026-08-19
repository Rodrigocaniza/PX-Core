# Delta de arquitectura

La arquitectura del módulo no cambia: sigue vigente
`artifacts/BC-GESTION-CENTRAL-COMISIONES-001/ARCHITECTURE.md`. Aquí sólo lo que esta misión mueve.

## Módulo nuevo

`modulos/gestion_central/comision_policy.py` — la regla aprobada y su aritmética.

Existe como módulo propio por una razón concreta: la migración vive en `repository.py` y necesita
exactamente las mismas constantes que el cálculo, pero `comisiones.py` ya depende del repositorio.
Ponerlas ahí habría creado un ciclo de importación; ponerlas duplicadas habría creado dos verdades.

Contiene las constantes canónicas, los cuatro estados de política, la lista de etiquetas retiradas,
`PolicyDecision`, las funciones `Decimal`/`HALF_UP` (`apply_basis_points`, `agreement_discount`,
`commissionable_base`, `commission_for`), el formateo de porcentaje y `is_in_effect`.

`comisiones.py` reexporta lo que ya era su contrato público (`AGREEMENT_DISCOUNT_BP`,
`BASIS_POINTS`, `apply_basis_points`, `agreement_discount`, `commissionable_base`), así que ningún
consumidor previo se rompe.

## Reemplazos

| Antes | Ahora |
|---|---|
| `StoredCommissionPolicy.rate_for()` → `(rate, status)` | `CanonicalCommissionPolicy.decide()` → `PolicyDecision` |
| Cascada `VENDEDORA → LOCAL → GENERAL` | Única política `GENERAL`, resuelta por período |
| `set_policy(actor, scope, rate_bp, scope_value)` | `set_general_rate(actor, rate_bp, effective_from, note)` |
| `apply_basis_points` con enteros | `Decimal` + `ROUND_HALF_UP`, precisión 60 |
| `POLICY_PENDING` / `POLICY_ABSENT = SIN_POLITICA_CONFIGURADA` | cuatro estados en `comision_policy.py` |

Métodos nuevos del servicio: `current_policy()` y `policy_versions()`. En la política:
`catalogue()` y `in_force_for(period)`, que son las que hacen que el historial de versiones
participe del cálculo en vez de quedar como registro decorativo.

## Esquema

Aditivo. Nada se borra ni se reescribe salvo lo que la migración retira explícitamente.

- `commission_policies` **+** `code TEXT NOT NULL DEFAULT ''`, `version INTEGER NOT NULL DEFAULT 1`,
  `effective_from TEXT NOT NULL DEFAULT ''`.
- `commission_entries` **+** `policy_code`, `policy_version`, `policy_effective_from`,
  `policy_scope` (todas anulables: una liquidación aún sin recalcular no tiene traza).
- `commission_policy_versions` **(tabla nueva)** — historial append-only con
  `UNIQUE(policy_id, version)`.
- `commission_rated_periods` **(tabla de la generación 5, congelada en la 7)** — guardaba el
  *estado* de la fijación, una fila por período. Ya no se lee ni se escribe. No se borra —nada de
  lo que el sistema afirmó alguna vez se borra— pero un estado de una sola fila no puede expresar
  que una fijación se retiró, y eso es justamente lo que hacía falta.
- `commission_period_rate_events` **(tabla nueva, generación 7)** — libro append-only de la tasa de
  cada período. Dos eventos: `PINNED` cuando un hecho económico oficial la fija, `UNPINNED` cuando
  desaparece el último hecho vivo que la justificaba. Guarda la tasa, la traza de política, el
  origen, la liquidación causante, la razón, el actor y la fecha. **El estado vigente de un período
  es su último evento**; nada se actualiza y nada se borra, así que volver a fijar es un evento
  más y no una reescritura. Lo escribe un solo método —`_record_period_rate_event`— desde tres
  llamadores: `_pin_rated_period` (`approve`/`mark_paid`), `_reconcile_period_pin` (el boundary de
  salida) y la siembra de la migración. **Calcular no escribe aquí.**

## Invariantes que esta misión agrega

1. **Un solo porcentaje.** Después de migrar, `commission_policies` contiene exactamente una fila,
   de alcance `GENERAL`. No hay ruta de código que escriba otro alcance.
2. **La traza es completa o vacía, nunca a medias.** Completa cuando una política evaluó la
   liquidación: `CANONICA_APROBADA` con importe, `FUERA_DE_VIGENCIA` sin importe que respaldar.
   Vacía cuando ninguna la evaluó: `POLITICA_HISTORICA_PREVIA` y `SIN_POLITICA_APLICADA`. La
   ausencia afirma que ninguna política aprobada produjo ese importe; la migración no la inventa
   porque no sabe con qué versión se calculó.
   Lo verifica `test_a_complete_trace_means_a_policy_evaluated_it_and_an_empty_one_means_none_did`,
   con los cuatro estados conviviendo en una misma base y una liquidación pagada que conserva
   importe sin traza.
3. **Idempotencia con traza.** La comparación de `recalculate` incluye los cinco campos de política,
   así que el primer recálculo tras migrar corrige la traza y el siguiente ya no cambia nada. Una
   `REVISADA` o `APROBADA` cuyo importe ya es el oficial no se toca y conserva su aval.
4. **Sólo la política vigente llega al pago.** `review`, `approve` y `mark_paid` rechazan una
   liquidación sin importe, una cuyo `policy_status` no sea `CANONICA_APROBADA`, y una cuyo
   porcentaje y versión grabados no coincidan con la política que rige hoy su período. El sello se
   graba al calcular y puede quedar atrás: comprobar sólo el sello no alcanza.
5. **Un período fijado conserva su tasa mientras algún hecho oficial la sostenga.** La tasa se
   fija cuando una liquidación alcanza `APROBADA` o `PAGADA` —el boundary económico oficial—: ahí
   se escribe un `PINNED`, y `decide()` resuelve ese período contra el último evento del libro
   antes que contra el catálogo. `set_general_rate` ya **no** bloquea: publicar siempre es posible
   y no reescribe lo fijado. La protección no se apoya en el estado de **una** liquidación
   concreta —con dos aprobaciones en el mes, revertir una no suelta nada— ni en una frontera
   global: es el conjunto de períodos hoy fijados, de modo que una fecha errónea aprobada protege
   su propio mes y no congela ningún otro. `paid_at IS NULL` sigue colgando del `WHERE` entero de
   `recalculate`, así que nada que haya movido dinero es alcanzable aunque su estado se hubiera
   alterado por otra vía.
6. **La resolución es por período, no por «última publicada».** Cada liquidación se calcula con la
   versión de vigencia más reciente que no supera su período. Programar el porcentaje del mes que
   viene no puede reescribir el mes en curso.
7. **Todo importe retirado queda asentado, por cualquiera de las dos rutas que lo retiran.**
   `recalculate` escribe el bloque `replaced` —con `rate_bp`, `commission_amount` y `policy_status`
   anteriores— en **toda** rama que anule o reemplace un importe previo, no sólo al reparar una
   `REVISADA` o una `APROBADA`; y `_apply_source_update` escribe **el mismo bloque, con el mismo
   nombre**, en su asiento `SOURCE_UPDATED` cuando la corrección de origen retira una tasa o un
   importe. Auditar no depende de por dónde se anuló. Importa porque
   hay un caso sin reparación posible: si el período es anterior a la vigencia, la liquidación queda
   `FUERA_DE_VIGENCIA` sin porcentaje y el importe heredado se retira sin sustituto. El asiento es
   lo único que lo conserva, y es idempotente: recalcular otra vez no lo repite.
8. **La comisión oficial no se mezcla.** `report` y el export separan `commission_amount` —sólo
   `CANONICA_APROBADA`— de `non_official_amount`. Ningún agregado rotulado «oficial 1,00%» incluye
   un importe calculado con otra política.
9. **Lo provisional es corregible; lo avalado, mientras el aval siga en pie.** `ELEGIBLE`,
   `CALCULADA` y `REVISADA` no fijan nada. `APROBADA` y `PAGADA` sí, y desde ese momento ninguna
   publicación, recálculo ni migración reinterpreta su importe. La frontera es un solo predicado
   —`RATING_BOUNDARY_STATES`, en `comision_policy.py` porque la migración necesita exactamente el
   mismo— y el SQL de ambos lados se arma desde `BOUNDARY_SQL_IN`, de modo que no puede divergir.
10. **La fijación se retira cuando se retira su justificación.** Si un período se queda sin ningún
    hecho oficial vivo, `_reconcile_period_pin` escribe un `UNPINNED` y el período vuelve a ser
    resoluble. Se invoca desde `_set_status`, por donde pasa toda transición de estado, así que las
    cuatro rutas de `AB1-g6` —y cualquiera futura— quedan cubiertas por construcción y no una por
    una. **Una `PAGADA` viva nunca desfija**: `paid_at` cuenta como hecho vivo aunque la
    liquidación se observe después o la venta se anule.
11. **Migrar y operar dan el mismo resultado.** La siembra usa la misma definición de hecho vivo
    que el código en caliente. En la generación 6 no era así —la migración excluía las `REVERTIDA`
    y el código conservaba el pin de una aprobación revertida— y esa divergencia era media
    `AB1-g6`.
12. **La migración nunca inventa ni desempata, ni siquiera retiradas.** La siembra sólo lee
    liquidaciones con un hecho vivo y política canónica; ante evidencia ausente o discrepante deja
    el período **sin fijar** y lo asienta. **No escribe un solo `UNPINNED`**: afirmar que una
    fijación fue retirada sería inventar un hecho que nadie produjo. No escribe una sola vez sobre
    `commission_entries`.
13. **Fijar y soltar dejan traza.** `COMMISSION_PERIOD_RATE_PINNED` y
    `COMMISSION_PERIOD_RATE_UNPINNED` en caliente, `COMMISSION_PERIOD_RATE_SEEDED` y
    `COMMISSION_PERIOD_RATE_SEED_SKIPPED` en la migración. Todos idempotentes: no se re-asientan si
    su asiento ya existe.
14. **Una venta anulada no llega al pago.** `review`, `approve` y `mark_paid` rechazan una
    liquidación cuya venta de origen está anulada. Por ruta pública no se llega ahí —`void_sale`
    mueve la liquidación— pero una base legada de procedencia externa sí puede traer esa fila, y
    hasta la generación 7 el sistema la pagaba.

## Límites que se mantienen

Sin nómina, sin bancos, sin BC-Finanzas, sin proveedor externo, sin red, sin datos de clientes.
El módulo no altera las reglas de BC Caja. `register_payment` y `sync_review_sales` siguen sin
llamador productivo: es el cableado pendiente que ya registraba el handoff anterior.
