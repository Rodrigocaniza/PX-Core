# Artifact Consistency — BC-OPTICA-PROMO-LIMPIA-CRISTAL-V1-013

## Base canónica y estado

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `main` = `7db56a0`, detrás del linaje productivo | `git rev-parse`, V1-010 no es ancestro de main | ✔ |
| Base elegida `09532f7` | tip de V1-010, contiene el código de rc.32 | ✔ |
| Estado productivo sin drift | 3.595 / 2.829 / 4.439 / 6.376 / 2.776 y `sha256 d307e017…` | ✔ las 7 cifras |

## Investigación

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `000037` tiene 726 unidades ficticias | 210 ASU + 516 PIL | ✔ |
| Sus únicos movimientos son de la carga inicial | 2, ambos `CARGA_INICIAL` de V1-008 | ✔ |
| **Ninguna venta lo referencia** | `sale_items` por `article_id` y `lens_article_id` | ✔ **0** |
| `000010` tiene 100 ASU / 10 PIL | suma por destino | ✔ |
| `no_cost` existe y hoy no se usa | 0 de 10 líneas | ✔ |
| No hay motor promocional | búsqueda en el módulo | ✔ no existe |
| Retirarlo no rompe historia | corolario de las 0 ventas | ✔ |

## El hallazgo que cambió el alcance

**El mecanismo ya estaba entero en el producto.** Se verificó leyendo el código,
no suponiendo:

- `SaleItem.subtotal` → `0` si `no_cost` *(`models.py:191-194`)*
- `_lineas_con_stock` filtra por `articulo.tracks_stock` y **no mira `no_cost`**
  *(`ventas.py:480-493`)* — por eso una línea bonificada descuenta
- `buscar_para_venta` usa `solo_activos=not incluir_inactivos` → un retirado no
  aparece
- `_verificar_stock` bloquea cualquier línea que deje el depósito en negativo,
  bonificada o no
- la UI ya tenía «Artículo sin costo»

Las 14 pruebas dirigidas **pasaron sin cambiar una línea de código de producto**.
Lo que se agregó después fue comodidad, no capacidad: un botón, dos constantes y
un método público `destino_de_unidad` en el controlador para no leer un privado
desde la UI.

## Pruebas dirigidas — 14 PASS

Escritas antes de tocar nada. Cubren que el regalo descuenta stock real, que no
cobra ni suma al total, que el movimiento dice que fue obsequio, que sin
promoción no se mueve nada, que vender cobrando sigue funcionando, que no se
regala sin stock, que dos regalos piden dos unidades, que anular devuelve el
frasco sin borrar el movimiento original, que el retirado no aparece para vender,
que retirar no borra la historia, y que no se puede retirar con stock encima.

## Dry-run — PASS, 0 fallas, 10 escenarios

Sobre copia de la base real, con un armazón real de Asunción:

| Escenario | Resultado |
| --- | --- |
| compensación 210 + 516 | ✔ `000037` a **0** en las dos sucursales |
| `000010` no recibe las unidades ficticias | ✔ sigue 100 / 10 |
| retiro | ✔ `active=0`, activos 2.829 → 2.828, 0 artículos borrados |
| venta bonificada | ✔ cobra 530.000, `000010` ASU 100 → 99, PIL sin cambios |
| nota del movimiento | ✔ contiene `PROMO_CRISTAL_ARMAZON_LIMPIA` |
| línea marcada | ✔ `no_cost = 1` con el artículo real |
| anulación | ✔ vuelve a 100 por `AJUSTE_POSITIVO`; el `VENTA` no se borra |
| venta sin promoción | ✔ no mueve el limpia-cristal |
| retirado no vendible | ✔ `000037` fuera del buscador, `000010` dentro |
| regalar sin stock | ✔ `StockInsuficiente` |
| idempotencia | ✔ el segundo retiro se rechaza y no escribe |

Integridad ok · FK 0 · negativos 0 · huérfanos 0 · efectos sin hecho 0 · stock en
retirados 0 · Caja histórica intacta · V1-008 intacta · movimientos de V1-010
intactos · base productiva con el mismo `sha256`.

## Suite y UI

`tests/comercial`: **268 passed**. El ciclo de ventana de Caja
(`BC_CAJA_WINDOW_LIFECYCLE_OK`, 2 ciclos) confirma que la ventana sigue
construyéndose y cerrándose con el botón nuevo, sin ventanas fantasma ni lock.

## Un método inventado, corregido

La primera versión del botón llamaba a `comercial.destino_de_unidad(...)`, que
**no existía**. En vez de leer el privado `_integrador._destino_opcional` desde la
UI, se agregó ese método al controlador como puerta pública de lectura. Es la
diferencia entre que la UI conozca la ligadura caja→sucursal y que la adivine.

## Lo que NO se verificó, y hay que decirlo

- **No se escribió nada en producción.** El retiro está preparado, no aplicado.
- **Las ventas del dry-run son de la copia.** No van a producción: lo único que
  se escribiría es la compensación y el retiro.
- **Las 100 unidades de `000010` en Asunción siguen siendo una estimación** de
  V1-010, no un conteo. El regalo las descuenta igual, y así debe ser: el frasco
  sale del mostrador exista o no un conteo exacto detrás.
- **No se definió si el obsequio debe ser automático.** La política no está
  cerrada como «siempre», así que el mecanismo lo hace fácil de agregar y no lo
  impone.
- **No se construyó un motor promocional.** Esta misión resuelve una promoción
  concreta con el modelo que ya existía.
- **El botón no se probó a mano con un clic real.** Se verificó que la ventana
  construye y cierra, y que el circuito que dispara está cubierto por las 14
  pruebas dirigidas y el dry-run.
