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

---

# Generación 2 — el retiro, aplicado en producción

## Pre-guard

| Guarda | Resultado |
| --- | --- |
| base con `sha256 d307e017…` | ✔ coincide |
| HEAD `049c59a`, worktree limpio | ✔ |
| `000037` activo, 210 ASU + 516 PIL | ✔ |
| 0 ventas históricas lo referencian | ✔ |
| `000010` en 100 / 10 | ✔ |
| BC Caja cerrada, WAL en 0 | ✔ |

## Aplicación

| Afirmación | Resultado |
| --- | --- |
| Backup verificado antes de escribir | ✔ `3e92ba65…` |
| `AJUSTE_NEGATIVO` −210 ASUNCION, −516 PILAR | ✔ |
| Causa `RECONCILIACION_STOCK_FICTICIO / PROMO_OBSEQUIO_LEGACY` en la nota | ✔ |
| Stock a cero **verificado antes** de retirar | ✔ |
| `active = 0` | ✔ activos 2.829 → 2.828 |
| Ningún artículo borrado | ✔ 3.595 |
| Rollback | ✔ **NO** hizo falta |

`sha256`: `d307e017…` → `d9a88e9f…`

## Los seis totales del plan, exactos

activos **2.828** · movimientos **4.441** · ASUNCION **6.166** · PILAR **2.260** ·
total **8.426** · artículos **3.595**.

## `000037` después

Inactivo, stock **0** en las dos sucursales, y **4 movimientos**: los dos
originales de V1-008 sin tocar y las dos compensaciones al lado. Sigue existiendo
—no hay hard-delete— y ya no aparece en el buscador de la línea de venta.
Una entrada `PROMO_OBSEQUIO_LEGACY_RETIRED` en la bitácora guarda las unidades
compensadas por sucursal, la causa, que no se trasladaron a `000010` y qué lo
reemplaza.

## `000010` después

**100 ASUNCION / 10 PILAR, con sus mismos 2 movimientos.** Ninguna de las 726
unidades ficticias se le trasladó. Verificado explícitamente.

## Por qué el circuito bonificado se verificó sobre copia

Comprobar que una venta bonificada funciona exige **crear una venta**. Hacerlo en
producción dejaría una venta que nunca ocurrió: un hecho sin causa, que es
exactamente lo que este sistema no admite.

Así que se hizo sobre una copia **del estado ya retirado** —no del anterior—, para
que lo verificado sea el sistema tal como quedó: la venta cobra 530.000, `000010`
baja de 100 a 99, el movimiento lleva `PROMO_CRISTAL_ARMAZON_LIMPIA`, la línea
queda `no_cost`, y anular devuelve el frasco por `AJUSTE_POSITIVO` sin borrar el
`VENTA` original.

Lo que sí se verificó **contra producción** es que `000037` ya no aparece para
vender y `000010` sí.

## Invariantes e historia

`integrity_check` ok · FK 0 · negativos 0 · huérfanos 0 · efectos sin hecho 0 ·
**stock operativo en retirados 0** · Caja 12 / 6.400.000 / 10 / 2 / 8 · V1-008
intacta (3.583 movimientos, 8.748 unidades) · movimientos de V1-010 intactos.

## Idempotencia

El segundo retiro se detiene en las guardas —«ya fue retirado», «ya no está
activo»— y **no escribe nada**. Se reporta como falla, y es correcto: retirar dos
veces no debería parecer rutina.

## Lo que NO se verificó, y hay que decirlo

- **No hubo una venta bonificada real en producción.** El circuito está
  verificado sobre copia del estado final y por 14 pruebas dirigidas; que la
  operadora aprete el botón es otra cosa, y pasará cuando pase.
- **Las 100 unidades de `000010` en Asunción siguen siendo una estimación** de
  V1-010. El regalo las descuenta igual, y así debe ser.
- **La política del obsequio no está cerrada.** El mecanismo lo hace fácil de
  agregar; nadie definió que sea siempre.
