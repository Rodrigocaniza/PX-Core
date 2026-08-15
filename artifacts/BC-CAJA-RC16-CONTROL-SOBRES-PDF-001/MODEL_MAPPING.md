# Model mapping

- Venta: `CashEntry` activa sin `outflow_type`.
- Sobre: `CashEntry.envelope`.
- Cliente/teléfono/vendedora/entrega/observaciones: campos existentes de `CashEntry`.
- Artículos: `CashEntry.effective_items`; una cabecera de venta y N artículos.
- Convenio/cuotas: `orders`, `agreement_amount`, `installments`.
- Saldo: `client_balance_amount`, sin recalcular reglas nuevas.
- Salidas: `GASTO` y `ENTREGA_ADMINISTRACION` activas.
- Anulaciones: `CashEntryStatus.VOIDED`, excluidas por `CashDay.totals()`.
- FactuFácil: no existe en RC15; se declara “Dato no disponible en RC15”.
- Comprobante/boleta: no existe un campo separado en RC15; no se infiere desde referencias ambiguas.

El generador recibe objetos ya cerrados y no abre SQLite ni modifica cierre, outbox o correo.
