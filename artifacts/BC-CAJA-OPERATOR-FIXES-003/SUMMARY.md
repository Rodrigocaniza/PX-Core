# BC-CAJA-OPERATOR-FIXES-003

Misión correctiva aislada sobre `d053e8e0b7de756a663d48e9e8c97ddb2d173b86`.

- Venta en curso renderiza cada item con producto, código, tipo, armazón, cristal y subtotal.
- Movimientos usa una especificación única para orden y alineación de encabezados/filas.
- Pago recupera Orden / Convenio y Cuotas, conservando su persistencia existente.
- Pedidos muestra y recupera el teléfono del cliente mediante migración aditiva `009`.
- Sin cambios a reglas de negocio, chrome nativo, SQLite existente ni módulos ajenos.
