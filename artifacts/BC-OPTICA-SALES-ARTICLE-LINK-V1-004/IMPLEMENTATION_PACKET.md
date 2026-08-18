# IMPLEMENTATION PACKET — BC-OPTICA-SALES-ARTICLE-LINK-V1-004

Base: `ecc0c7b` = slice 3 (`feature/bc-optica-purchases-providers-v1-003`), sobre `54f5f06`
(slice 2), sobre `ed0dbba` (slice 1), sobre `origin/main` = `7db56a0` = BC Caja
1.0.0-rc.31. Worktree: `.worktrees/sales-link-004`. Rama:
`feature/bc-optica-sales-article-link-v1-004`.

## Lo primero que hubo que averiguar

**Una línea de venta de BC Caja no es un artículo.** Los datos productivos reales lo
dejan claro:

```
description        code     frame_price  lens_price  laboratory
Armazon/org uvx    104256   280.000      250.000     Optilab
armazones          222555   300.000      —           asasa
cadenilla          —         70.000      —           —
```

Una fila de `sale_items` lleva **dos componentes**: el ítem físico (`frame_price`) y el
trabajo de laboratorio (`lens_price`). Es un par de anteojos, no un producto.

Eso decide todo el vínculo. La 022 había agregado `article_id` asumiendo un artículo por
línea; faltaba el segundo. Partir la venta en dos filas para que cada una tuviera un solo
artículo habría sido **reescribir el subsistema de ventas**, que es exactamente lo que este
slice no hace. La forma de la línea es la que la operación real tiene, y el vínculo se
adapta a ella:

| Columna | Qué es | De dónde viene |
| --- | --- | --- |
| `article_id` | artículo del componente físico | 022 |
| `lens_article_id` | artículo del trabajo de laboratorio | **025** |

`tracks_stock` **no es una columna de la línea**. Se deriva de la naturaleza del artículo
en el catálogo, igual que en los slices 1 a 3. Ni la descripción, ni el código, ni el
laboratorio, ni `item_type` entran en la decisión: si entraran, un texto mal tipeado movería
stock.

## Lo segundo: cuándo se integra

BC Caja no tiene un paso de «finalizar venta». Una entrada nace `ACTIVE` y la única
transición posterior es `VOIDED`, así que **`ACTIVE` es finalizada** según su propio modelo
económico.

Pero además hace falta que la venta **tenga un artículo vinculado**, y ahí está la clave de
seguridad del slice: vincular un artículo es un acto nuevo, que hoy no ocurre en ninguna
parte. Por eso **nada de lo que ya existe empieza a mover stock por sí solo**. Una venta sin
vínculo se comporta exactamente como hoy.

A eso se suma que el integrador es **opcional y por defecto no está**:
`SQLiteCashDayRepository(ruta)` guarda exactamente como guardaba antes de que existiera el
núcleo comercial. Instalar esto no cambia nada hasta que alguien lo conecte.

## Atomicidad: una sola transacción

`save()` ya abría `BEGIN IMMEDIATE` para todo el día. La integración corre **adentro**, no
al lado:

```
BEGIN IMMEDIATE
  guardia de edición   ← antes de escribir nada
  cash_days upsert
  auditoría de entradas
  cash_entries upsert
  sale_items refresh   ← saltea las ventas ya integradas
  integración          ← SALE_COMPLETED + efectos + movimientos VENTA
COMMIT
```

El integrador **recibe** la conexión y nunca abre una propia. Está verificado
mecánicamente: su código no contiene `BEGIN` ni `COMMIT`. Una segunda transacción
independiente es exactamente la forma de terminar con la venta guardada y el stock no.

## El hecho, y sus efectos

`SALE_COMPLETED` se registra **antes** que sus efectos — la misma corrección que el slice 3
tuvo que hacer, aplicada de entrada. Una venta de puros servicios se completa igual y su
hecho queda registrado aunque no mueva una unidad. Un hecho no depende de tener efectos.

Cada línea con artículo que mueve stock produce **un** movimiento `VENTA` de cantidad 1.
`SaleItem` no tiene cantidad y nunca la tuvo: una línea es una unidad. Inventar una cantidad
sería inventar un dato.

El movimiento referencia venta, línea, artículo, destino, evento, actor y momento. La vista
`stock_origen_venta` cierra el camino inverso, espejo de `stock_origen_compra` de la 024:
entre las dos, cualquier unidad que entró o salió del depósito se explica con una consulta.

## Sucursal

Sale de `cash_register_branches`, el vínculo canónico caja → sucursal de las migraciones
018 y 020. Se **lee**, no se duplica ni se reinterpreta. La operadora no elige de dónde sale
el stock: sale de donde está parada.

Una caja sin vínculo **no puede vender stock** — adivinarle una sucursal sacaría mercadería
del local equivocado, y eso no se nota hasta que alguien busca físicamente algo que el
sistema dice tener. Sí puede vender servicios: sin efecto de inventario, la sucursal no hace
falta para nada.

## Stock insuficiente

Se comprueba **sobre la misma conexión de la transacción**, no por otra: preguntarlo por
fuera devolvería lo que había antes de empezar, y en una venta de dos líneas del mismo
artículo daría el visto bueno a las dos. El trigger de la 023 sigue debajo como respaldo
para cualquier escritor.

Para que el rechazo no llegue tarde, `faltantes_de_stock(entry, unidad)` contesta antes de
intentar guardar: artículo, disponible, pedido y destino.

Una venta **nunca** puede pedir la excepción administrativa de stock negativo. Las únicas
siguen siendo las del slice 2, sobre movimientos administrativos explícitos.

## Edición después de que la venta movió stock

El guardado de Caja borra y reinserta las líneas de cada entrada en cada `save`. Eso está
bien para una venta que todavía no sacó nada del depósito y es inaceptable para una que sí:
el movimiento que la sacó apunta a esa fila.

| | |
| --- | --- |
| **Bloqueado** | cambiar, agregar o borrar líneas de una venta integrada; anularla |
| **Permitido** | teléfono, observaciones, cliente, vendedora — todo lo que vive en `cash_entries` y no cambia la causalidad del inventario |

La entrada **no** queda congelada entera. Cuatro triggers lo hacen cumplir para cualquier
escritor, y un chequeo previo devuelve `VentaIntegradaNoEditable` con un mensaje entendible
en vez de una violación de constraint a mitad del guardado.

**No hay reversión, y no se improvisó.** Revertir necesita el movimiento compensatorio —que
existe desde la 023— atado al circuito de negocio de la anulación. Media reversión sería
peor que bloquear.

## Histórico

`planificar_backfill_de_ventas()` calcula y no escribe. Las líneas viejas dicen
«Armazon/org uvx» y un código de proveedor: eso identifica lo que alguien escribió esa
tarde, no un artículo del catálogo. Elegir uno por parecido lo inventaría **y además
cambiaría el stock de hoy** con una inferencia sobre el pasado.

## Dinero

Una salida `VENTA` mueve una unidad y no mueve un guaraní. Totales, arqueo y convenios
quedan igual, verificado contando filas y mecánicamente: el módulo no inserta ni actualiza
`cash_entries`, `cash_days`, `cash_counts` ni `cash_day_corrections`.

## Preparado, no implementado

FactuFácil, Trabajos, revisión, Gestión Central y estadísticas van a colgar del mismo hecho.
Su payload ya lleva día, fecha, unidad, total y todas las líneas con su artículo y su
`tracks_stock`. Este slice **no deriva ninguna**: el único `effect_kind` que existe es
`STOCK_MOVEMENT`, y hay prueba de eso.

## UX

No se cambió la UI. Lo que se entregó es lo que la UI va a necesitar —
`articulos_vendibles()`, `stock_disponible()`, `faltantes_de_stock()` — con una decisión
que importa: `stock_disponible()` devuelve `None` para un servicio, no cero. Un servicio no
tiene stock cero: no tiene stock, y mostrarlo como cero haría pensar que falta algo.

## Migración 025

Aditiva: un `ALTER TABLE ADD COLUMN` nullable sobre `sale_items`, una tabla nueva, seis
triggers, una vista y un índice. Cadena 24 → 25.

## Pruebas dirigidas primero

`tests/comercial/test_sales_article_link.py`, 42 pruebas escritas antes de la
implementación, cubriendo los 12 grupos pedidos.
