# SUMMARY — BC-OPTICA-COMERCIAL-UI-Y-CARGA-INICIAL-V1-005

Cuatro slices dejaron el circuito cerrado y sin una sola pantalla desde donde usarlo. Este
lo hace usable, y resuelve el prerrequisito duro de todo lo demás: poder cargar los ~3.000
artículos reales sin tipearlos y sin inventar lo que el archivo no diga.

## La regla que ordena la carga inicial

**Catálogo no es stock.**

Que un artículo exista no significa que haya unidades en el depósito. Aplicar el archivo
crea artículos y **cero** movimientos — verificado sobre la copia productiva. Las unidades
entran por un recuento, que es otro hecho: alguien contó, un día, en un local.

Ese recuento entra como `INGRESO_ADMINISTRATIVO` con motivo `INVENTARIO_INICIAL`, con
artículo, sucursal, cantidad, responsable, fecha, motivo y de qué recuento salió. **No se
falsea una compra** para generarlo: daría un stock correcto colgando de un proveedor que
nunca facturó eso, y esa mentira no se deshace después sin borrar historia. Si el recuento
estuvo mal, se compensa; el original queda, porque es lo que se contó ese día.

## La naturaleza no se adivina

Si la columna `nature` viene vacía, la fila se rechaza. Deducirla del texto pondría a un
cristal a descontar stock el día que alguien escriba «armazón de cristal».

Y un plan con rechazos no se aplica a medias: cargar 1.999 de 2.000 dejaría un catálogo que
nadie sabe describir. Planificar no escribe nada; el botón de aplicar sólo se habilita si no
hay ni un rechazo.

Vacío significa **no sé**, no cero: un precio en blanco queda sin precio, un `0` significa
que se regala. El plan reporta cuántas filas quedan pendientes de completar.

## Lo que no se agregó, y por qué

**No hay columna de costo en el artículo.** El costo es lo que dijo la factura con que se
compró, y eso ya vive en la línea de compra. Una columna en el maestro sería una segunda
verdad que puede contradecir al documento. La pantalla lo muestra derivado de la última
compra confirmada y, cuando no hay ninguna, dice «pendiente» en vez de inventar un número.

**No hay `tax_rate` por artículo.** El IVA de la óptica es 10% para todo y no hay evidencia
de una sola excepción. Una columna inventaría una variabilidad que el negocio no tiene.

De dominio, la 026 agrega exactamente tres columnas —`location`, `min_stock`, `barcode`— que
son datos propios del artículo sin ninguna otra fuente posible, y un motivo sembrado.

## La pantalla

Ventana `Comercial` con tres pestañas: **Artículos**, **Proveedores**, **Compras**. Mismo
CustomTkinter que Caja, mismos colores, mismos patrones.

Vive en su propia ventana y se importa dentro de la función que la abre: si el módulo
comercial faltara, Caja sigue abriendo igual. La operadora que cobra no se cruza con el ABM.

**Ninguna regla vive en la pantalla.** `revisar_compra()` devuelve los dos totales y los
problemas en castellano; la pantalla los muestra. Si la pantalla repitiera las reglas, el
día que el dominio cambie una seguiría diciendo la vieja. Verificado mecánicamente: ni la UI
ni el controlador nombran `PURCHASE_CONFIRMED`, `SALE_COMPLETED`, ni escriben en
`stock_movements`, `purchases` o `domain_events`.

Categoría y marca se crean con un `+ Crear` al lado del selector, sin salir del alta.

## En la venta

Un botón «Buscar artículo» junto a las acciones de la línea. Busca por código, descripción o
código de barras y muestra el stock **de esta sucursal**. Al elegir completa código,
descripción y precio, y guarda el vínculo.

Escribir a mano sigue funcionando igual que siempre — y no descuenta nada. La estructura de
`sale_items` no cambió: la venta óptica sigue siendo una fila con sus dos componentes.

El stock se muestra con estados, no con números ambiguos: `sin stock` para lo que es
stockeable y no hay, `—` para un servicio (no tiene stock cero: no tiene stock), `?` cuando
la caja no está vinculada a una sucursal. Esconder lo que no tiene stock haría pensar que el
artículo no existe y alguien lo crearía de nuevo.

## El circuito, ejercitado de verdad

Sobre una **copia** de la base real de la Óptica, 21 pasos verificados:

```
archivo → catálogo (0 stock) → recuento auditado → proveedor → factura a crédito
→ vencimiento derivado → reparto Asunción/Pilar → confirmar → stock 26/16
→ venta en Asunción → stock 25/16 → trazabilidad hasta la factura y el proveedor
```

Más: venta de puro servicio (hecho sí, movimientos no), venta sin stock rechazada, compra de
cristal sin generar stock, costo derivado de la factura, y las 10 líneas históricas de la
Óptica intactas sin artículo inventado.

## Verificación

- 57 pruebas dirigidas escritas antes de la implementación.
- Suite completa: **905 passed, 4 subtests, exit 0** (848 baseline + 57).
- Cadena 022…026 sobre copia productiva: 12 `cash_entries` y 10 `sale_items` intactos,
  `integrity ok`, `foreign_key_check 0`, totales sin cambios.
- Base productiva real sin tocar: `sha256 1c4fcc40…98ec` antes y después.
- Gates: Librarian PASS, QA PASS, Auditor PASS, Artifact Consistency PASS.

El Librarian verifica además que la plantilla que la guía describe **de verdad se lee y pasa
el planificador**: una guía que documenta un formato que el código rechaza es peor que no
tener guía.

## Lo que falta para que esto se use

El archivo real de los ~3.000 artículos **no existe en el repositorio**. Lo que este slice
entrega es el mecanismo seguro y el contrato del archivo —
`docs/PLANTILLA_ARTICULOS.csv` y `docs/CARGA_INICIAL_DE_ARTICULOS.md` — para que el dueño lo
produzca. Inventar los artículos habría sido exactamente lo que el principio prohíbe.

## Producción, intacta

21 migraciones. Ninguna de las **cinco** instalada. Sin PR, sin merge, sin empaquetar.
