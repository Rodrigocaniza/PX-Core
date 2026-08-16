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
| Cascada `VENDEDORA → LOCAL → GENERAL` | Única política `GENERAL`, sin cascada |
| `set_policy(actor, scope, rate_bp, scope_value)` | `set_general_rate(actor, rate_bp, effective_from, note)` |
| `apply_basis_points` con enteros | `Decimal` + `ROUND_HALF_UP`, precisión 60 |
| `POLICY_PENDING` / `POLICY_ABSENT = SIN_POLITICA_CONFIGURADA` | cuatro estados en `comision_policy.py` |

Métodos nuevos del servicio: `current_policy()` y `policy_versions()`.

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
2. **Traza inseparable del importe.** Si `rate_bp` no es nulo en una liquidación calculada, su
   `policy_code`, `policy_version` y `policy_effective_from` describen la política que lo produjo.
3. **Idempotencia con traza.** La comparación de `recalculate` incluye los cinco campos de política,
   así que el primer recálculo tras migrar corrige la traza y el siguiente ya no cambia nada.
4. **Nada sin porcentaje llega al pago.** `review` y `mark_paid` rechazan una liquidación con
   `rate_bp` o `commission_amount` nulos.
5. **Un cambio de política no mueve dinero pasado.** `set_general_rate` no recalcula, y las
   liquidaciones fuera de `ELEGIBLE`/`CALCULADA` no son alcanzables por `recalculate`.

## Límites que se mantienen

Sin nómina, sin bancos, sin BC-Finanzas, sin proveedor externo, sin red, sin datos de clientes.
El módulo no altera las reglas de BC Caja. `register_payment` y `sync_review_sales` siguen sin
llamador productivo: es el cableado pendiente que ya registraba el handoff anterior.
