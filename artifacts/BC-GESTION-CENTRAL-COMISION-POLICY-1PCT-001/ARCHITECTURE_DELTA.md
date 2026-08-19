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
  *estado* de la fijación, una fila por período. **No se escribe ni se borra.** Sí se lee, en un
  único sitio: la migración la consulta para asentar como descartada toda fijación heredada que hoy
  no tenga un hecho vivo detrás. Un estado de una sola fila no podía expresar que una fijación se
  retiró, y eso es justamente lo que hacía falta.
- `commission_period_rate_events` **(tabla nueva, generación 7)** — libro append-only de la tasa de
  cada período. Dos eventos: `PINNED` cuando un hecho económico oficial la fija, `UNPINNED` cuando
  desaparece el último hecho vivo que la justificaba. Guarda la tasa, la traza de política, el
  origen, la liquidación causante, la razón, el actor y la fecha. **El estado vigente de un período
  es su último evento**; nada se actualiza y nada se borra, así que volver a fijar es un evento
  más y no una reescritura. Lo escribe un solo método, `CentralRepository.record_period_rate_event`
  —hay **un único `INSERT`** sobre esta tabla en todo el código de producción, y ningún `UPDATE` ni
  `DELETE`—, invocado desde un solo sitio, `reconcile_period_rate`. Los fixtures de prueba sí
  borran, para construir bases legadas; la propiedad append-only es del producto. **Calcular no
  escribe aquí.**

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
4. **Sólo la política vigente llega al pago, y sólo con el importe que esa política produce.**
   `review`, `approve` y `mark_paid` rechazan una liquidación sin importe, una cuyo `policy_status`
   no sea `CANONICA_APROBADA`, una cuyo porcentaje y versión no coincidan con la política que rige
   hoy su período, y una **cuyo importe no sea el que esa tasa produce sobre esa base**. El sello se
   graba al calcular y puede quedar atrás: comprobar sólo el sello no alcanza. Comprobar tasa y
   versión tampoco: una fila de procedencia externa con la tasa correcta y el importe inventado
   pasaba las tres puertas, y eran 8.900.000 Gs. Lo halló el Auditor de la generación 10 como
   `O8-g10` y lo declaró no bloqueante por no ser alcanzable desde ninguna ruta pública; se cerró
   igual, porque esta guarda existe justamente para lo que llega de fuera.
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
10. **La fijación se retira cuando se retira su justificación.** `reconcile_period_rate` lleva el
    libro del período al estado que sus hechos vivos justifican: fija, suelta o refija a otra tasa,
    según la diferencia entre lo que el libro dice y lo que la regla dice. La invocan **los cuatro
    sitios que escriben un estado** —`_set_status`, `recalculate`, `_apply_source_update` y la
    promoción a elegible— y la apertura de la base. `_set_status` **no** es el único punto de paso:
    afirmarlo era falso (`L3-g9`), y decirlo bien en el documento mientras las docstrings lo seguían
    afirmando era `L1-g10`. Lo que sostiene la garantía sobre las rutas futuras no es esta frase
    sino una prueba estructural que recorre el **árbol sintáctico** de todos los módulos y falla si
    una función que escribe `commission_entries` —con `UPDATE` o con `INSERT`— no reconcilia. Las
    dos únicas exenciones están declaradas con su motivo, y la prueba **se autocomprueba**: los
    tres casos que evadían la versión textual —el literal SQL partido en dos, la mención en un
    comentario y el `INSERT`— tienen que ser detectados para que la suite pase.
    **Una `PAGADA` viva conserva la tasa con la que se pagó**: sostiene su mes a **esa** tasa
    aunque la liquidación se observe después o la venta se anule, y no se reinterpreta con la
    política vigente. Lo que no sostiene es una tasa distinta de la suya, que era `AB1-g8`.
11. **Migrar y operar son la misma operación.** No es que coincidan: la apertura de la base llama a
    `reconcile_period_rate`, exactamente la misma función que cada transición, sobre cada período
    con hechos o con libro. La consulta de hechos vivos —columnas, `JOIN`, `WHERE` y clave de
    período— sale entera de `comision_policy.live_official_facts_sql`, y la decisión de
    `resolve_period_rate`. No queda ningún texto «equivalente» que pueda separarse, que es lo que
    falló tres generaciones seguidas: en la 6 la migración excluía las `REVERTIDA` y el código no;
    en la 7 exigía política canónica y el código no; en la 8 exigía coherencia de tasa y el código
    no. Cada corrección había unificado la mitad que ya coincidía.
12. **La migración no inventa hechos, pero sí aplica la regla.** Que un período no tenga ningún
    hecho vivo, o que su pin no lo lleve ninguno, es **observable**, no fabricado: aplicar la regla
    a esa observación es lo mismo que hace cada transición, y no hacerlo dejaba a la pantalla
    declarando fijado un mes que ningún hecho justificaba. Los retiros de la apertura llevan
    `origin='MIGRACION'` para distinguirse de los operativos. Lo que la migración sigue sin hacer es
    **elegir**: ante evidencia discrepante no fija nada y lo asienta. Y **no escribe una sola vez
    sobre `commission_entries`** —lo que sí hace otro paso, `_migrate_commission_policy`, es
    reemplazar la *etiqueta* de política retirada, sin tocar `rate_bp` ni `commission_amount`.
13. **Fijar y soltar dejan traza, por las dos rutas y con el mismo nombre.**
    `COMMISSION_PERIOD_RATE_PINNED` y `COMMISSION_PERIOD_RATE_UNPINNED` cubren tanto las
    transiciones como la apertura de la base, y el `origin` dice cuál fue; la migración usaba antes
    un nombre propio y desactivaba el asiento, de modo que quien contara fijaciones por la auditoría
    no veía las suyas. `COMMISSION_PERIOD_RATE_SEED_SKIPPED` registra la evidencia discrepante y la
    fijación heredada sin respaldo, una sola vez por período.
14. **Una venta anulada no llega al pago.** `review`, `approve` y `mark_paid` rechazan una
    liquidación cuya venta de origen está anulada. Por ruta pública no se llega ahí —`void_sale`
    mueve la liquidación— pero una base legada de procedencia externa sí puede traer esa fila, y
    hasta la generación 7 el sistema la pagaba.

## Límites que se mantienen

Sin nómina, sin bancos, sin BC-Finanzas, sin proveedor externo, sin red, sin datos de clientes.
El módulo no altera las reglas de BC Caja. `register_payment` y `sync_review_sales` siguen sin
llamador productivo: es el cableado pendiente que ya registraba el handoff anterior.
