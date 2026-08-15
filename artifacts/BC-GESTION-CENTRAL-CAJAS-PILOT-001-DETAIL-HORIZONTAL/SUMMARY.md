# Detalle horizontal Full HD

El detalle de cada unidad conserva sus callbacks y pasa de once filas verticales
a una composición de lectura izquierda a derecha:

1. Cabecera compacta con volver, negocio, sucursal, caja, fecha, última
   sincronización y actualizar.
2. Fila única con siete KPIs uniformes: ventas, efectivo, tarjeta/cheque,
   gastos, retiros, diferencia de arqueo y alertas.
3. Zona central en dos columnas: tabla económica amplia a la izquierda y
   sincronización/alertas a la derecha.

A 1920×1080 toda la información principal queda visible sin desplazamiento.
Por debajo de 1400 px la zona central cambia a orientación vertical como fallback.
No se modificaron reglas económicas, persistencia, auditoría ni sincronización.
