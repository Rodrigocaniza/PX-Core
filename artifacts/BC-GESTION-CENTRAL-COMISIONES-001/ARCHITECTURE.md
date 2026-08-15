# Arquitectura

## Separación

- `modulos/gestion_central/comisiones.py` — dominio y cálculo. Sin Tk, sin red, sin proveedor externo.
- `modulos/gestion_central/comisiones_ui.py` — sólo presentación y llamadas al servicio.
- `modulos/gestion_central/repository.py` — migraciones idempotentes (`CREATE TABLE IF NOT EXISTS`).
- `modulos/gestion_central/ui.py` — un botón «Comisiones» en la barra existente; el dashboard no se recarga de información.

## Persistencia durable (SQLite local, WAL)

| Tabla | Rol |
|---|---|
| `commission_sales` | Venta con identidad estable `UNIQUE(branch, source_sale_id)`; total, cobrado, saldo, fecha de cancelación, anulación |
| `commission_payments` | Libro append-only de cobros y reversas, con `idempotency_key` única |
| `commission_entries` | Liquidación por venta y período, con base, descuento, porcentaje y estado |
| `commission_entry_history` | Historial append-only de transiciones |
| `commission_policies` | Configuración sintética de porcentaje, pendiente de aprobación |

### Integridad a nivel de motor

```sql
CREATE UNIQUE INDEX idx_commission_entry_active
  ON commission_entries(sale_id) WHERE status<>'REVERTIDA';
CREATE UNIQUE INDEX idx_commission_entry_period
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
- `REVERTIDA` se alcanza desde los estados abiertos y desde `OBSERVADA`, siempre con motivo.
- `mark_paid` sólo acepta origen `APROBADA`: no se paga sin revisión ni aprobación previas.

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
