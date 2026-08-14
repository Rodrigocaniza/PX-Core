# BC-CAJA-OPERATOR-UX-002

Base exacta: `0f6195eada4319477961e45871e49954f43825a9`.

La pantalla principal de BC Caja quedó reorganizada como tres paneles azules
independientes: Cliente y comprobante, Detalle de venta y Pago. Los campos se
leen como filas verticales. `+ Agregar artículo` pertenece exclusivamente a
Detalle de venta y `Guardar venta — F9` pertenece exclusivamente a Pago.

Venta en curso separa la tabla y las acciones secundarias de un resumen lateral
`TOTAL DE LA VENTA`. El flujo simple, multi-item, edición, eliminación,
recálculo y persistencia atómica conservan los controladores existentes.

No se modificó persistencia ni reglas de negocio.

