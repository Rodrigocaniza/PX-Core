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
5. **Un cambio de política no mueve dinero pasado.** `set_general_rate` no recalcula; su vigencia no
   puede retroceder **ni gobernar un período ya liquidado** —`CALCULADA`, `REVISADA`, `APROBADA` o
   `PAGADA`—; y `paid_at IS NULL` cuelga del `WHERE` entero de `recalculate`, de modo que nada que
   haya movido dinero es alcanzable aunque su estado se hubiera alterado por otra vía. La segunda
   guarda hace falta porque la vigencia se resuelve por mes: una fecha *igual* a la última publicada
   gobierna los mismos períodos que ella, y con sólo la primera guarda se re-tarifaba lo ya
   liquidado. Con las dos, el re-tarifado retroactivo no tiene ruta pública, ni directa ni indirecta.
6. **La resolución es por período, no por «última publicada».** Cada liquidación se calcula con la
   versión de vigencia más reciente que no supera su período. Programar el porcentaje del mes que
   viene no puede reescribir el mes en curso.
7. **Todo importe retirado queda asentado.** `recalculate` escribe el bloque `replaced` —con
   `rate_bp`, `commission_amount` y `policy_status` anteriores— en **toda** rama que anule o
   reemplace un importe previo, no sólo al reparar una `REVISADA` o una `APROBADA`. Importa porque
   hay un caso sin reparación posible: si el período es anterior a la vigencia, la liquidación queda
   `FUERA_DE_VIGENCIA` sin porcentaje y el importe heredado se retira sin sustituto. El asiento es
   lo único que lo conserva, y es idempotente: recalcular otra vez no lo repite.
8. **La comisión oficial no se mezcla.** `report` y el export separan `commission_amount` —sólo
   `CANONICA_APROBADA`— de `non_official_amount`. Ningún agregado rotulado «oficial 1,00%» incluye
   un importe calculado con otra política.

## Límites que se mantienen

Sin nómina, sin bancos, sin BC-Finanzas, sin proveedor externo, sin red, sin datos de clientes.
El módulo no altera las reglas de BC Caja. `register_payment` y `sync_review_sales` siguen sin
llamador productivo: es el cableado pendiente que ya registraba el handoff anterior.
