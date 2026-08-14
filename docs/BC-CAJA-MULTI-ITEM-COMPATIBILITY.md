# BC Caja Multi-Item — compatibilidad histórica

La misión `BC-CAJA-MULTI-ITEM-001` conserva `cash_entries` como cabecera de venta y agrega
`sale_items` como tabla hija. La migración incremental `006_sale_items.sql` no modifica ni
elimina filas históricas.

Las ventas anteriores que no poseen filas en `sale_items` siguen siendo legibles mediante
`CashEntry.effective_items`: una venta histórica se expone como un único ítem implícito,
con código, tipo, precios de armazón/cristal, laboratorio y receta ya guardados en la
cabecera legacy. No se duplica la cabecera ni se reescriben datos existentes.

Las ventas nuevas multi-item guardan una cabecera y N filas hijas de forma transaccional.
Pedidos y cobros continúan vinculados a la cabecera, por lo que una venta genera como
máximo un Pedido y un movimiento diario.

La compatibilidad está cubierta por:

- `test_historical_single_product_is_transparently_one_item`;
- `test_three_items_are_one_header_one_order_and_total_1850000`;
- las pruebas de migración desde esquema `001`;
- la regresión completa de BC Caja.
