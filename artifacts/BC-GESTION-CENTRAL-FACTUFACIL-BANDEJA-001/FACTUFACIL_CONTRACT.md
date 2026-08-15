# Contrato preparatorio FactuFácil v1

Orden estable: cliente, CI/RUC, número de boleta, fecha, número de caja, número de sobre, observaciones/receta, artículos con precio individual, total, forma de cobro, pagado, saldo, sucursal y vendedora.

El export local usa `contract_version=1`, `sale_id`, `identity_key`, `content_hash` y `fields` en ese orden. Un adaptador futuro podrá consumirlo, pero esta misión no implementa navegación web, autenticación ni envío externo.

La identidad combina sucursal, identificador fuente y sobre. La carga exige responsable y comprobante. Repetir exactamente la misma confirmación es idempotente; otra confirmación sobre una venta ya cargada se rechaza mostrando el registro previo. Los cambios posteriores conservan versión y pasan a `OBSERVADO` si la venta estaba cargada.
