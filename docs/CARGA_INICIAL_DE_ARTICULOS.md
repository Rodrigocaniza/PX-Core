# Cargar el catálogo real de artículos

Son unos 2.000 artículos en Asunción y 1.000 y pico en Pilar. Se cargan desde un
archivo, no a mano.

## El archivo

CSV o Excel (`.xlsx`), con encabezado en la primera fila. `docs/PLANTILLA_ARTICULOS.csv`
es el modelo.

### Columnas obligatorias

| Columna | Qué va | Si falta |
| --- | --- | --- |
| `sku` | el código con el que la óptica identifica el artículo | se rechaza la fila |
| `name` | la descripción que se ve en la venta | se rechaza la fila |
| `nature` | qué es el ítem (ver abajo) | **se rechaza la fila** |

### Las cuatro naturalezas

Se escriben exactamente así:

| Valor | Qué es | ¿Mueve stock? |
| --- | --- | --- |
| `PRODUCTO_STOCKEABLE` | armazón, cadenilla, estuche, líquido comprado | **sí** |
| `PRODUCCION_INTERNA` | lo que la óptica arma y después vende | **sí** |
| `SERVICIO_NO_STOCKEABLE` | compostura, ajuste, consulta | no |
| `TRABAJO_BAJO_PEDIDO` | cristal recetado, insumo pedido para un trabajo | no |

**La naturaleza no se adivina.** Si la columna viene vacía, la fila se rechaza. No se
deduce del texto: el día que alguien escriba «armazón de cristal», el sistema estaría
poniendo a un cristal a descontar stock y nadie sabría por qué.

### Columnas opcionales

`category`, `brand`, `sale_price`, `location`, `min_stock`, `barcode`, `unit`, `notes`.

Las categorías y marcas se escriben **por nombre** y se crean solas al aplicar. Si dos
filas dicen «Armazones» y «armazones», es la misma.

Vacío significa **no sé**, no cero. Un `sale_price` en blanco queda sin precio y hay que
completarlo después; un `sale_price` en `0` significa que se regala.

**No hay columna de costo.** El costo de un artículo es lo que dijo la factura con que se
compró, y eso vive en la compra. La pantalla lo muestra derivado de la última factura, y
mientras no haya ninguna dice «pendiente» en vez de inventar un número.

## Cómo se carga

`Comercial → Artículos → Cargar desde archivo…`

Son dos pasos, y el primero **no escribe nada**:

1. **Elegir archivo.** El sistema lee, calcula qué pasaría y muestra: cuántas altas,
   cuántas actualizaciones, cuántas rechazadas y por qué, y qué le falta al archivo.
2. **Aplicar carga.** Sólo se habilita si no hay ninguna fila rechazada.

Un plan con rechazos no se aplica a medias. Cargar 1.999 de 2.000 dejaría un catálogo que
nadie sabe describir.

El mismo archivo no se puede cargar dos veces: queda registrado con su huella (sha256),
quién lo cargó y cuándo.

## Cargar el catálogo NO crea stock

**Catálogo no es stock.** Que un artículo exista no significa que haya unidades en el
depósito.

Las unidades entran por un **recuento**, que es otro hecho: alguien contó, un día, en un
local. Entra como `INGRESO_ADMINISTRATIVO` con motivo `INVENTARIO_INICIAL`, y queda
registrado con artículo, sucursal, cantidad, responsable, fecha, motivo y de qué recuento
salió.

No se falsea una compra para generar el stock inicial. Daría un stock correcto colgando de
un proveedor que nunca facturó eso, y esa mentira no se deshace después sin borrar
historia.

Si el recuento estuvo mal, **se compensa** con un movimiento que lo corrige. El movimiento
original queda: es lo que se contó ese día.
