# Artifact Consistency — BC-OPTICA-DELIVERY-SERVICE-V1-011

## Base canónica y estado

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `main` = `7db56a0`, detrás del linaje productivo | V1-013 no es ancestro de main | ✔ |
| Base elegida `3d03dcf` | tip de V1-013 | ✔ |
| Estado sin drift | 3.595 / 2.828 / 4.441 / 6.166 / 2.260 y `d9a88e9f…` | ✔ las 6 cifras |

## El modelo, antes de tocarlo

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Ya hay servicios representados | 13 con `SERVICIO_NO_STOCKEABLE` | ✔ |
| El precio es de la línea, no del artículo | `reference_subtotal` suma `frame_price`+`lens_price`; `articles.sale_price` sólo sugiere | ✔ |
| Un servicio queda fuera del inventario | `_lineas_con_stock` filtra por `articulo.tracks_stock` | ✔ |
| No existía concepto de Delivery | búsqueda por *deliver*, *envio*, *env?o*, *flete* | ✔ **0** |
| No se creó un segundo modelo de servicios | se reutilizó el existente | ✔ |

## Pruebas dirigidas — 17 PASS

Escritas antes de tocar nada, y **pasaron sin cambiar código de producto**. Cubren
los tres precios pedidos (20.000 / 15.000 / 25.000), que cambiar el sugerido no
reescriba lo cobrado, que no haya movimiento de stock ni fila en `stock_actual`,
las combinaciones con producto, cristal y servicio, sólo-envío, anulación sin
compensación de inventario, y que el concepto no se duplique.

## El concepto

| Afirmación | Resultado |
| --- | --- |
| `SERV-DELIVERY`, «Delivery / Envío» | ✔ |
| `SERVICIO_NO_STOCKEABLE` | ✔ |
| precio sugerido 20.000, editable por venta | ✔ |
| activo y seleccionable en el buscador | ✔ |
| **sin una sola unidad de stock** | ✔ 0 movimientos, 0 filas en `stock_actual` |
| una sola fila, sin duplicar | ✔ |

## Alta productiva

| Afirmación | Resultado |
| --- | --- |
| Backup verificado antes de escribir | ✔ `5409588e…` |
| artículos 3.595 → 3.596, activos 2.828 → 2.829 | ✔ |
| **movimientos 4.441, sin cambios** | ✔ |
| **stock ASUNCION 6.166 y PILAR 2.260, sin cambios** | ✔ |
| Caja histórica 12 / 6.400.000 / 10 | ✔ |
| integridad, FK, negativos, huérfanos, efectos | ✔ 0 |
| Idempotencia | ✔ el segundo alta no escribe y lo dice sin marcarlo como falla |
| Rollback | ✔ **NO** hizo falta |

`sha256`: `d9a88e9f…` → `ff6b2b6a…`

### Por qué se aplicó sin un HUMAN_GATE aparte

La orden lo autoriza expresamente cuando el concepto puede darse de alta «sin
cambiar datos económicos existentes». Se verificó punto por punto: stock, Caja y
movimientos quedaron idénticos. Lo único que cambió es una fila de catálogo y una
categoría.

## Verificado sobre copia con datos reales

Venta de armazón + envío editado a 25.000: cobra **305.000**, el armazón
descuenta, **Delivery no genera un solo movimiento**. Al anular, el armazón vuelve
y el envío sigue sin movimientos — no hay nada que devolver, porque no salió de
ningún lado.

## Un defecto propio, encontrado y no corregido

Comparando contra `bc-caja-preconciliacion-20260819-155227.sqlite3` aparecieron
**5 artículos que perdieron `category_id` y `brand_id`**: `000010`, `2000056`,
`2000070`, `2000071` y `2000072`.

**La causa es mía.** `guardar_articulo` reconstruye el `Article` entero a partir
de los argumentos; en V1-010 y en la adenda de V1-013 lo llamé pasando sólo
`sku`, `name`, `nature` y `notes` para corregir naturaleza y anotar, y todo lo
demás quedó en su valor por defecto.

Alcance real: sólo etiquetas. No afecta stock, dinero, naturaleza ni movimientos,
y los precios no se perdieron porque ya eran nulos.

**No lo corregí**: está fuera de este slice y la orden pide no asumir
autorización. Queda propuesto, con el backup identificado.

## Lo que NO se verificó, y hay que decirlo

- **El botón no se probó con un clic real.** Se verificó que la ventana construye
  y cierra, y el circuito que dispara está cubierto por las 17 pruebas y por la
  verificación sobre copia.
- **No hubo una venta con Delivery en producción.** Crearla sería un hecho sin
  causa. Se verificó sobre copia del estado real.
- **El importe sugerido de 20.000 no se validó contra ninguna política escrita**:
  es el valor que indicó el dueño, y por eso quedó como sugerencia y no como
  tarifa.
