# BC Caja sobres, revisión y movimientos diarios V1

La misión completa el tramo que faltaba sobre F1: aprobar una venta revisada crea automáticamente un movimiento diario por origen; observarla crea una solicitud durable para la Caja; corregirla conserva la identidad y la historia; revalidarla genera una sola consolidación; cambiarla o anularla compensa el movimiento activo.

La consolidación conserva organización, sucursal, caja, día operativo, venta fuente, revisión, hash, total, efectivo, tarjeta/transferencia, convenio y saldo. Convenio no se suma a efectivo/tarjeta. Caja continúa siendo la única autoridad que edita la venta.

La migración 033 es aditiva e idempotente. No borra historia ni cambia inventario, comisiones, FactuFácil, Telegram, credenciales o producción.

Trabajo manual eliminado: volver a escribir en Movimientos diarios los importes ya nacidos en Caja.
