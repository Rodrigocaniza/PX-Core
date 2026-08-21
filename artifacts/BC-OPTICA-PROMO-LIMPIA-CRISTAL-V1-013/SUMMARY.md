# BC-OPTICA-PROMO-LIMPIA-CRISTAL-V1-013

**El regalo se hace sobre el frasco que existe. Y resulta que el sistema ya sabía
hacerlo.**

## Lo que había

Cuando la óptica regalaba un limpia-cristal, lo representaba con
`000037 LIMPIA CRISTAL OBSEQUIO`: un artículo inventado, con precio cero clavado
en el catálogo y **726 unidades de stock propio** — 210 en Asunción y 516 en
Pilar. Dos mentiras a la vez: un producto que no existe, y un depósito que no se
corresponde con el mostrador.

## Lo que encontré

**El mecanismo correcto ya estaba entero en el producto.** No hizo falta cambiar
una línea para que funcione:

- una línea con `no_cost` **vale cero** — lo dice `SaleItem.subtotal`
- pero **sí descuenta stock**, porque quien decide eso es la *naturaleza del
  artículo*, no si se cobró. `_lineas_con_stock` ni mira `no_cost`
- un artículo inactivo ya no aparece en el buscador de la venta
- ya es imposible regalar dejando el depósito en negativo
- la UI ya tenía la casilla «Artículo sin costo»

Las 14 pruebas dirigidas —escritas antes de tocar nada— **pasaron sin tocar
código de producto**. Lo que faltaba no era capacidad: era usarla y sacar de en
medio el artículo inventado.

## Lo que agregué

Un botón: **«Limpia-cristal de regalo»**. Busca `000010`, mira que haya stock en
la sucursal de esa caja, avisa si la venta ya lleva un obsequio, y agrega la
línea con el artículo real, `no_cost`, precio cobrado 0 y el motivo
`PROMO_CRISTAL_ARMAZON_LIMPIA` escrito en la descripción — que viaja como nota
del movimiento, así que dentro de un año se puede saber por qué faltaba ese
frasco.

No es automático. La política no está definida como «siempre», así que el
mecanismo lo hace fácil, no obligatorio.

## Lo que se retiraría

Las 726 unidades de `000037` se compensan a cero —**no se trasladan a `000010`**,
porque no eran frascos— y recién entonces el artículo se desactiva. No se borra
nada: sus dos movimientos originales quedan, la compensación es un hecho nuevo, y
las ventas viejas que lo referenciaran seguirían siendo legibles. Hoy no hay
ninguna: **cero ventas lo usan**.

| | antes | después |
| --- | ---: | ---: |
| activos | 2.829 | 2.828 |
| stock ASUNCION | 6.376 | 6.166 |
| stock PILAR | 2.776 | 2.260 |
| **total** | 9.152 | **8.426** |

Las 726 unidades que se van del total nunca fueron frascos. El inventario no
pierde nada: deja de contar algo que no existía.

## Verificado

Dry-run **PASS** con 10 escenarios sobre copia real, incluida una venta bonificada
de verdad (cobra 530.000, el limpia-cristal baja de 100 a 99), su anulación (vuelve
a 100, sin borrar el movimiento original) y el intento de usar el retirado.
14 pruebas dirigidas · 268 en la suite comercial · la ventana de Caja abre y
cierra con el botón nuevo.

## Aplicado

Autorizado y hecho. **PASS, 0 fallas, sin rollback.**

Las 726 unidades ficticias se compensaron —**−210 en Asunción, −516 en Pilar**—,
se verificó que quedara en cero, y recién entonces `000037` se desactivó. Sus dos
movimientos originales siguen donde estaban; las compensaciones son hechos nuevos
al lado. No se borró nada y ninguna unidad se trasladó a `000010`, que quedó
exactamente como estaba: 100 en Asunción y 10 en Pilar.

| | antes | después |
| --- | ---: | ---: |
| activos | 2.829 | **2.828** |
| movimientos | 4.439 | **4.441** |
| stock ASUNCION | 6.376 | **6.166** |
| stock PILAR | 2.776 | **2.260** |
| **total** | 9.152 | **8.426** |

`sha256`: `d307e017…` → `d9a88e9f…`

El circuito bonificado se verificó **sobre una copia del estado ya retirado**, no
sobre producción: comprobar que una venta funciona exige crear una venta, y una
venta de prueba en producción sería justo el hecho sin causa que este sistema no
admite. Sobre esa copia cobra 530.000, el limpia-cristal baja de 100 a 99, el
movimiento lleva `PROMO_CRISTAL_ARMAZON_LIMPIA`, y anular devuelve el frasco sin
borrar nada. Contra producción sí se verificó lo que se puede mirar sin escribir:
`000037` ya no aparece para vender y `000010` sí.

Caja histórica, V1-008 y V1-010 intactas. Un segundo retiro se detiene en las
guardas sin escribir.

## Lo que sigue

Dos slices, sin empezar: **011** Delivery y **012** laboratorio por defecto.
