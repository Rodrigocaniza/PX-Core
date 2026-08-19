# BC-OPTICA-ARTICLE-METADATA-RESTORE-V1-014

Cinco artículos habían quedado sin categoría y sin marca. Volvieron a tenerlas, y
la forma de perderlas dejó de existir.

## Qué pasó

`guardar_articulo` no modifica un artículo: lo reemplaza. Reconstruye el registro
entero con lo que se le pasa, y lo que no se le pasa queda en su valor por
defecto. Para `category_id` y `brand_id` ese valor es `None`.

En V1-010 se corrigió la naturaleza de cuatro artículos de Compostura nombrando
cuatro campos —`sku`, `name`, `nature`, `notes`— y en la adenda de V1-010 se le
agregó a `000010` la nota de la estimación de la misma manera. Los dos llamados
hicieron exactamente lo que la operación promete. El problema no fue que fallara:
fue que no era la operación que hacía falta.

No se perdió stock, ni dinero, ni movimientos, ni naturaleza, ni una sola línea
de Caja. Se perdieron etiquetas. Los precios sobrevivieron nada más que porque
eran nulos: si esos artículos hubieran tenido precio, hoy no lo tendrían.

## Qué se restauró

De `bc-caja-prerecuento-20260819-142306.sqlite3`, la última foto en la que los
cinco todavía tenían sus etiquetas. Leídos de ahí, no de ningún mensaje.

| SKU | artículo | categoría | marca | naturaleza (se conservó) |
|---|---|---|---|---|
| `000010` | LIMPIA CRISTAL | Limpia Cristales | Óptica Puppilent\`s | `PRODUCTO_STOCKEABLE` |
| `2000056` | Par de patillas | Compostura | Optica San Cayetano | `SERVICIO_NO_STOCKEABLE` |
| `2000070` | Hilo | Compostura | Laboratorio Optilab | `SERVICIO_NO_STOCKEABLE` |
| `2000071` | Tornillo | Compostura | Optica San Cayetano | `SERVICIO_NO_STOCKEABLE` |
| `2000072` | Plaqueta | Compostura | Optica San Cayetano | `SERVICIO_NO_STOCKEABLE` |

El backup fue fuente de dos campos y de nada más. El artículo productivo de hoy
es el bueno: tiene la naturaleza corregida, las notas con la evidencia del
recuento y sus movimientos. Restaurar la fila entera hubiera deshecho dos
misiones para arreglar una etiqueta.

## Que no vuelva a pasar

`actualizar_articulo` lee lo que hay y reemplaza sólo lo que se le nombra. Pasar
`None` explícitamente sigue vaciando el campo: la diferencia está entre no
nombrar un campo y nombrarlo en blanco, y sin eso no habría forma de sacarle la
marca a un artículo mal clasificado.

`guardar_articulo` se queda como está —es un reemplazo, y está bien que lo sea
cuando el formulario trae todo— pero ahora su docstring lo dice.

Dos cosas más se apoyaron en la operación nueva:

- `desactivar_articulo` enumeraba los trece campos a mano. Correcto hoy, y roto
  el día que alguien agregue el catorce.
- El formulario de artículo no muestra proveedor ni unidad, y sin embargo los
  reescribía en cada edición. Hoy no había ningún artículo con proveedor y todos
  estaban en UNIDAD, así que no hubo daño: era el mismo defecto esperando su
  turno.

## Alcance verificado, no supuesto

Se comparó campo por campo los 3.554 artículos que existían antes del daño contra
la producción. Exactamente cinco perdieron categoría y marca; ninguno perdió
ningún otro campo; ninguna categoría cambió a otra distinta. Los otros dos
cambios del período son legítimos y conocidos: 767 bajas de V1-010 y V1-013, y
las cuatro correcciones de naturaleza.

## Resultado

Stock, movimientos y Caja idénticos: ASUNCION 6.166, PILAR 2.260, total 8.426,
4.441 movimientos, 12 entradas por 6.400.000. Diez campos tocados, diez
esperados, cero inesperados. `integrity_check` ok, FK 0, negativos 0, huérfanos
0, efectos sin hecho 0. Rollback no usado.

14 pruebas dirigidas, suite completa en 981. Dry-run PASS, idempotencia PASS,
smoke de la UI PASS.

## Lo que quedó abierto

`2000070 Hilo` tiene como marca «Laboratorio Optilab». Se restauró tal cual
porque es el dato legítimo anterior, pero un laboratorio como marca de un insumo
de compostura huele a arrastre de la carga inicial. Vale revisarlo en V1-012, que
justamente trata de laboratorios.
