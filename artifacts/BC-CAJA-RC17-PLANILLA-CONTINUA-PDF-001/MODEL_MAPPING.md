# Model mapping

- Cliente/Descripción, sobre, código, armazón, cristal y doctor: campos existentes de `CashEntry`/`SaleItem`; la columna Doctor muestra solamente el nombre.
- Total y pagos: se muestran una vez por venta; filas adicionales sólo muestran artículos.
- Convenio, cuotas y saldo: campos existentes; saldo cero se presenta como `Cancelado`.
- Caja inicial: `CashDay.opening_cash`; salidas: `GASTO` y `ENTREGA_ADMINISTRACION` existentes.
- Totales: exclusivamente `CashDay.totals()` más suma visual de convenio y saldo ya calculado.
- Anulaciones: visibles y excluidas por el estado de dominio existente.
- No se infiere `s/c`; sólo se conservaría si ya estuviera en el dato real.
- Receta, graduación, observaciones y firmas no se renderizan; no se eliminan ni modifican en el modelo o SQLite.
