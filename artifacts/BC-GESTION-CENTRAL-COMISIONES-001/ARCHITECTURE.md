# Arquitectura

## Separación

- `modulos/gestion_central/comisiones.py` — dominio y cálculo. Sin Tk, sin red, sin proveedor externo.
- `modulos/gestion_central/comisiones_ui.py` — sólo presentación y llamadas al servicio.
- `modulos/gestion_central/repository.py` — migraciones idempotentes (`CREATE TABLE IF NOT EXISTS`).
- `modulos/gestion_central/ui.py` — un botón «Comisiones» en la barra existente; el dashboard no se recarga de información.

## Persistencia durable (SQLite local, WAL)

| Tabla | Rol |
|---|---|
| `commission_sales` | Venta con identidad estable `UNIQUE(branch, source_sale_id)`; total, liquidado, saldo, fecha de cancelación, anulación |
| `commission_payments` | Libro append-only de cobros (`COBRO`), liquidaciones de convenio (`CONVENIO`) y reversas (`REVERSA`); `idempotency_key` es la identidad interna única y `client_key` la clave opcional del llamador |
| `commission_entries` | Liquidación por venta y período, con base, descuento, porcentaje y estado |
| `commission_entry_history` | Historial append-only de transiciones |
| `commission_policies` | Configuración sintética de porcentaje, pendiente de aprobación |

### Integridad a nivel de motor

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_commission_entry_active
  ON commission_entries(sale_id) WHERE status<>'REVERTIDA';
CREATE UNIQUE INDEX IF NOT EXISTS idx_commission_entry_period
  ON commission_entries(sale_id,period) WHERE period IS NOT NULL AND status<>'REVERTIDA';
```

Una venta no puede tener dos liquidaciones vivas ni duplicarse en la misma liquidación,
aunque el llamador se equivoque. Toda escritura corre bajo `BEGIN IMMEDIATE`.

## Máquina de estados

```
PENDIENTE_SALDO ──cancelación total──▶ ELEGIBLE ──recálculo──▶ CALCULADA
                                                                  │
                                                          revisar │
                                                                  ▼
                                                              REVISADA ──aprobar──▶ APROBADA ──pagar──▶ PAGADA
```

- `OBSERVADA` se alcanza desde `ELEGIBLE`, `CALCULADA`, `REVISADA`, `APROBADA` y `PAGADA`, siempre con motivo.
- `REVERTIDA` se alcanza con motivo desde los estados abiertos y desde `OBSERVADA` vía `revert()`, y además desde `PENDIENTE_SALDO` vía `void_sale()` y `_revert_commission_effect()`.
- `mark_paid` sólo acepta origen `APROBADA`: no se paga sin revisión ni aprobación previas.

### Invariante de la corrección de origen

Una corrección de origen (`register_sale` sobre una venta ya registrada, camino que
`sync_review_sales` recorre en cada sincronización) **nunca recalcula en silencio algo que ya pasó
por revisión humana**. `REVIEWED_STATES = {REVISADA, APROBADA, PAGADA}` y cualquier entrada con
`paid_at` van a `OBSERVADA`; el resto recalcula **la base completa** —total, descuento de convenio
y base comisionable— y vuelve a `ELEGIBLE` si estaba `CALCULADA`, limpiando porcentaje y comisión
para que el recálculo los recomponga.

Esto cierra el escenario en que una liquidación `REVISADA` conservaba base y descuento del total
anterior y avanzaba a `APROBADA → PAGADA` pagando sobre una base congelada, en cualquiera de los
dos sentidos, y omitiendo el 5% del convenio cuando el tipo de venta cambiaba. Añadido en la
generación 3 tras el FAIL de QA independiente de la generación 2; cubierto por
`test_source_correction_after_review_never_pays_a_stale_base`,
`test_source_correction_before_review_recomputes_the_whole_base` y
`test_source_correction_cannot_reattribute_already_paid_commission`.

### Invariante del dinero ya pagado

**Una liquidación que alguna vez movió dinero nunca alcanza `REVERTIDA`**, ni siquiera pasando
por `OBSERVADA`. El invariante no depende del estado actual sino de `paid_at`, mediante
`_was_paid(entry)`, y se aplica en las tres únicas rutas que pueden producir `REVERTIDA`:

| Ruta | Guarda |
|---|---|
| `revert()` | `guard=_reject_paid` en `_transition` |
| `_revert_commission_effect()` (reversión de cobro, corrección de origen) | `if _was_paid(entry): → OBSERVADA` |
| `void_sale()` (anulación de venta) | `if _was_paid(entry): → OBSERVADA` |

Esto cierra además la consecuencia financiera: mientras la liquidación pagada no pueda pasar a
`REVERTIDA`, el índice parcial `idx_commission_entry_active` sigue bloqueando el nacimiento de una
segunda liquidación sobre la misma venta, de modo que **no puede pagarse dos veces**.

El invariante fue añadido en la generación 2 tras el FAIL del auditor independiente (bloqueantes
A1, A2 y A3 en `generation-1/VERDICT_AUDITOR.md`) y está cubierto por
`test_paid_settlement_can_never_reach_reverted_even_through_observed` y
`test_voiding_a_paid_sale_observes_instead_of_reverting`.

### El libro de cobros es la única fuente de verdad

`paid_amount` **nunca se asigna por fuera del libro**: siempre es `_settled_amount()`, es decir la
suma de `COBRO` y `CONVENIO` menos `REVERSA`. Toda diferencia declarada por el origen se asienta
como una fila más del libro append-only:

- Un convenio liquida la venta completa mediante una fila `CONVENIO`, no por asignación directa.
- Si una corrección de origen declara más cobrado que el libro, se asienta el cobro faltante.
- Si el total corregido es menor a lo ya liquidado, la corrección se rechaza.
- `revert_payment` recalcula desde el libro y rechaza ventas anuladas o ya convertidas en convenio.

Esto cierra estructuralmente toda la familia de defectos en que `paid_amount` divergía del libro:
cobro posterior del origen descartado en silencio (venta atrapada en `PENDIENTE_SALDO` para
siempre), `paid_amount` negativo, y dinero declarado como cobrado sin ningún asiento que lo
respalde. Añadido en la generación 5 tras los FAIL de QA y Auditor independientes de la
generación 4; cubierto por `test_resync_with_a_later_payment_settles_the_sale`,
`test_paid_amount_is_always_backed_by_the_ledger`,
`test_convenio_settlement_is_recorded_in_the_ledger` y
`test_reverting_a_payment_on_a_voided_sale_is_rejected`.

### Contrato de idempotencia de los cobros

La idempotencia de `register_payment` es **explícita y del llamador**, no inferida del contenido:

- Con `idempotency_key`, el reintento se descarta con `(None, False)`. El reconocimiento del
  reintento ocurre **antes** de validar importes, de modo que reintentar el cobro que cancela la
  venta se descarta limpiamente en vez de fallar por saldo insuficiente. Cubierto por
  `test_retrying_the_cancelling_payment_is_discarded_not_rejected`.
- Sin clave, **cada llamada es un cobro real distinto**: dos cobros genuinos del mismo monto, el
  mismo día y con la misma referencia son dos cobros, no un duplicado.
- Un cobro ya revertido **deja de bloquear su clave**: la reversa deshace el hecho que la clave
  representaba, de modo que el mismo recibo puede volver a cargarse con su fecha real.

La identidad interna (`idempotency_key`) es siempre nueva y la clave del llamador se guarda aparte
en `client_key`, de modo que el libro append-only nunca colisiona consigo mismo.

Antes, la clave se derivaba del contenido del cobro y el chequeo no excluía los cobros reversados.
Eso hacía que, tras una reversión motivada, el mismo cobro real se rechazara en silencio: la venta
quedaba con saldo fantasma y la vendedora nunca cobraba su comisión. Añadido en la generación 4
tras el FAIL de QA independiente de la generación 3; cubierto por
`test_a_reverted_payment_can_be_registered_again`,
`test_two_identical_genuine_payments_are_both_registered` y
`test_explicit_idempotency_key_protects_integration_retries`.

### Validación del período

`_month()` deriva el período de liquidación de la fecha, así que valida con `date.fromisoformat`
y rechaza en el borde cualquier cadena que no sea una fecha real. Una fecha mal formada jamás
produce un período: antes, `"2099-4-10"` generaba el mes inexistente `"2099-4-"` y la comisión
desaparecía de todos los reportes sin error alguno. `sync_review_sales` valida la fecha del
snapshot externo antes de ingerir y devuelve `invalid_date` para que la fila descartada sea
visible en vez de perderse. Añadido en la generación 2 tras el FAIL de QA independiente
(bloqueante Q1 en `generation-1/VERDICT_QA.md`); cubierto por
`test_invalid_dates_are_rejected_and_never_produce_a_period` y
`test_review_sync_reports_invalid_dates_instead_of_losing_them`.

## Puertos

- `CommissionPolicyPort` — política de porcentaje configurable a futuro (`GENERAL`, `LOCAL`, `VENDEDORA`).
- `sync_review_sales(actor, review_service)` — ingesta desde la revisión de ventas existente, reutilizando su contrato; descarta lo que no es venta.

## Límites deliberados

- Local-first: no hay red, nómina, banco ni liquidación contable externa.
- Modelo compatible con sincronización central futura (identidad estable, hash de contenido, versión, historial append-only).
- No se modificó ninguna regla ni módulo de BC Caja.
- El libro de comisiones no almacena datos del cliente: sólo local, vendedora, sobre e importes.
