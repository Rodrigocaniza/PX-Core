# Evidencia visual

- `screenshots/comisiones-1920x1080.png`, validada **1920×1080 RGB**.
- SHA-256: `dbf0462416eeb0184f3ca34438d5a9cfba0c1eae420cedebbb780f2733008467`.
- Datos exclusivamente sintéticos (período 2099-04, tres locales, tres vendedoras).

## Inspección visual

- Fondo off-white, azul/celeste cómodo, cabecera marina; sin sobrecargar el dashboard principal.
- Ocho KPIs en una fila: ventas del período, canceladas, cobros parciales, convenios, base comisionable, comisión calculada, pendiente de aprobación y pagado. Todos los importes con formato de guaraníes.
- «Resumen por vendedora» sobre la tabla principal: local, vendedora, ventas, con saldo, canceladas, convenios, total vendido, descuento de convenio, base comisionable y comisión.
- Tabla principal con las doce columnas completas y visibles, importes alineados a la derecha.
- Colores de estado legibles y distinguibles: `PAGADA` verde, `APROBADA` verde claro, `REVISADA`/`CALCULADA` azul, `PENDIENTE_SALDO` ámbar, `OBSERVADA` naranja, `REVERTIDA` rojo suave.
- Panel de detalle con el motivo en lenguaje llano sobre banda del color del estado, desglose línea por línea (total → − descuento de convenio 5% → = base comisionable → × porcentaje configurado), nota de política y las cinco acciones.
- Historial auditable visible con fecha, acción, estado y responsable.
- La cabecera advierte de forma permanente «PILOTO · DATOS SINTÉTICOS · SIN NÓMINA NI BANCOS» y el porcentaje aparece rotulado como sintético pendiente de aprobación.

## Contenido de la captura

Fila seleccionada: convenio S-103 de 500.000 Gs. El desglose muestra
`500.000 − 25.000 = 475.000` y, con la política sintética del 3 %, `14.250 Gs.`
La aritmética de la pantalla es verificable a simple vista.

El smoke finaliza limpiamente y cierra el log temporal.
