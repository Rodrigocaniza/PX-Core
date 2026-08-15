# Contratos preparatorios — sin implementación económica

## FactuFácil

Registro futuro: cliente, número de boleta, fecha, número de caja, observaciones/receta, artículos y precios, estado `PARA_CARGAR | CARGADO` y clave idempotente para control de duplicados. Esta misión no conecta FactuFácil ni crea pantallas completas.

## Comisiones

Reglas heredadas y no ampliadas: existe comisión cuando la venta queda cancelada; convenios se tratan como venta finalizada; base de convenio menos 5%; reporte futuro por vendedora, mes y local. Esta misión no calcula ni contabiliza comisiones.
