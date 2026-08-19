# BC-OPTICA-DELIVERY-SERVICE-V1-011

**El envío ya se podía cobrar. Lo que faltaba era el concepto y un botón.**

## Lo que encontré

Antes de agregar nada, miré cómo el sistema representa servicios. Ya hay 13, y
las dos piezas que un envío necesita estaban las dos:

- **el precio vive en la línea de venta**, no en el artículo. `sale_price` del
  catálogo es una sugerencia; lo que se cobra es de esa venta y de ninguna otra
- **la naturaleza decide el stock.** `_lineas_con_stock` filtra por
  `tracks_stock`, y para un `SERVICIO_NO_STOCKEABLE` eso es falso. No hay caso
  especial que escribir

Las 17 pruebas dirigidas —escritas antes de tocar nada— **pasaron sin cambiar
código de producto**. No se creó un segundo modelo de servicios porque el primero
ya alcanzaba.

## Lo que se agregó

**Un artículo:** `SERV-DELIVERY`, «Delivery / Envío», `SERVICIO_NO_STOCKEABLE`,
categoría *Servicios*, precio sugerido **20.000**. **Sin una sola unidad de
stock** — ni cero inventado, ni centinela.

**Un botón:** «Delivery / Envío», que pregunta el importe con 20.000 ya puesto y
deja cambiarlo. 15.000, 25.000 o lo que se haya acordado. Rechaza lo que no es un
número y lo negativo.

## Por qué el precio no está en el catálogo

Un envío cuesta distinto según a dónde va. Poner 20.000 como tarifa haría que
cobrar 15.000 pareciera un error, y que subirla mañana reescribiera lo que se
cobró ayer. Está verificado que no: cambiar el sugerido a 30.000 deja en 15.000
la venta que cobró 15.000.

## Verificado

Delivery a 20.000, a 15.000 y a 25.000 · producto + envío · cristal + envío ·
servicio + envío · sólo envío · **cero movimientos de stock** · **no aparece en
`stock_actual`** (no tiene fila: un envío no se cuenta) · anular no compensa
inventario por el envío · el concepto no se duplica.

**Stock antes y después del alta: idéntico.** ASUNCION 6.166, PILAR 2.260, total
8.426. Caja histórica intacta.

17 pruebas dirigidas · 285 en la suite comercial · la ventana de Caja abre y
cierra con el botón nuevo · BC Caja arranca sobre la base ya modificada.

## Un defecto propio que encontré de paso

Comparando contra el backup previo a V1-010 vi que **cinco artículos perdieron su
categoría y su marca**: `000010`, `2000056`, `2000070`, `2000071` y `2000072`.

La causa es mía: `guardar_articulo` reconstruye el registro entero, y lo llamé
pasando sólo `sku`, `name`, `nature` y `notes` para cambiar la naturaleza y las
notas. Categoría y marca quedaron vacías.

Son etiquetas: no afecta stock, dinero, naturaleza ni movimientos, y los precios
sobrevivieron porque eran nulos. **No lo corregí** — está fuera de este slice y
la orden pide no asumir autorización. Es restaurable desde
`bc-caja-preconciliacion-20260819-155227.sqlite3`.

## Lo que sigue

`BC-OPTICA-LABORATORIO-POR-DEFECTO-V1-012`, sin empezar.
