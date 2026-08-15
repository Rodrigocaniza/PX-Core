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
- `REVERTIDA` se alcanza desde los estados abiertos y desde `OBSERVADA`, siempre con motivo. **`PAGADA` nunca pasa a `REVERTIDA`**: una corrección posterior al pago produce `OBSERVADA`.
- `mark_paid` sólo acepta origen `APROBADA`: no se paga sin revisión ni aprobación previas.

## Puertos

- `CommissionPolicyPort` — política de porcentaje configurable a futuro (`GENERAL`, `LOCAL`, `VENDEDORA`).
- `sync_review_sales(actor, review_service)` — ingesta desde la revisión de ventas existente, reutilizando su contrato; descarta lo que no es venta.

## Límites deliberados

- Local-first: no hay red, nómina, banco ni liquidación contable externa.
- Modelo compatible con sincronización central futura (identidad estable, hash de contenido, versión, historial append-only).
- No se modificó ninguna regla ni módulo de BC Caja.
- El libro de comisiones no almacena datos del cliente: sólo local, vendedora, sobre e importes.
