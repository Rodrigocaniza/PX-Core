# SUMMARY — BC-OPTICA-SALES-ARTICLE-LINK-V1-004

Slice 4 de 6. El circuito queda cerrado:

```
Compra → PURCHASE_CONFIRMED → INGRESO_COMPRA → stock
Venta  → SALE_COMPLETED     → VENTA          → stock restante
```

Y en sentido inverso, con una consulta: `stock_origen_compra` explica de dónde entró cada
unidad y `stock_origen_venta` por dónde salió.

## El hallazgo que definió el slice

Antes de diseñar nada hubo que leer cómo representa BC Caja una línea de venta **hoy**,
incluyendo los datos productivos reales. Y una línea **no es un artículo**:

```
description        code     frame_price  lens_price  laboratory
Armazon/org uvx    104256   280.000      250.000     Optilab
cadenilla          —         70.000      —           —
```

Lleva dos componentes en la misma fila, porque es un par de anteojos. La 022 había agregado
`article_id` asumiendo un artículo por línea; faltaba el segundo.

Partir la venta en dos filas para que cada una tuviera un solo artículo habría sido
reescribir el subsistema de ventas — lo que esta misión tenía prohibido. Así que el vínculo
se adapta a la forma que la operación real tiene: `article_id` para el ítem físico,
`lens_article_id` para el trabajo de laboratorio.

`tracks_stock` no es una columna de la línea. Se deriva de la naturaleza del artículo, igual
que en los tres slices anteriores. Hay prueba con una línea cuya descripción dice
«Armazon/org uvx»: el texto no decide nada.

## Nada empieza a moverse solo

Dos candados, no uno:

1. Una venta **sin artículo vinculado** se comporta exactamente como hoy — y vincular un
   artículo es un acto nuevo que hoy no ocurre en ninguna parte.
2. El integrador es **opcional y por defecto no está**. `SQLiteCashDayRepository(ruta)`
   guarda como guardaba antes de que existiera el núcleo comercial.

Esa es la condición para que rc.31 siga siendo rc.31.

## Una sola transacción

`save()` ya abría `BEGIN IMMEDIATE` para todo el día. La integración corre **adentro**: el
integrador recibe la conexión y nunca abre una propia — verificado mecánicamente, su código
no contiene `BEGIN` ni `COMMIT`. Una segunda transacción independiente es exactamente la
forma de terminar con la venta guardada y el stock no.

Rollback probado con fallo inyectado en el segundo movimiento de una venta de dos líneas: 0
entradas, 0 eventos, 0 efectos, 0 movimientos, stock intacto.

## El hecho, aunque no tenga efectos

`SALE_COMPLETED` se registra antes que sus efectos. Una venta de puros servicios y una de
puro trabajo de laboratorio emiten el hecho y cero movimientos. Es la misma corrección que
el slice 3 tuvo que hacer sobre la marcha, aplicada de entrada.

Cada línea con artículo que mueve stock produce **un** movimiento `VENTA` de cantidad 1.
`SaleItem` no tiene cantidad y nunca la tuvo: una línea es una unidad. Inventar una cantidad
sería inventar un dato.

## Sucursal

Sale de `cash_register_branches`, el vínculo canónico de las migraciones 018 y 020. Se lee,
no se duplica. La operadora no elige de dónde sale el stock: sale de donde está parada, y no
hay parámetro ni setter para pedir otra cosa.

Una caja sin vínculo no puede vender stock — adivinarle una sucursal sacaría mercadería del
local equivocado, y eso no se nota hasta que alguien busca físicamente algo que el sistema
dice tener. Sí puede vender servicios: sin efecto de inventario, la sucursal no hace falta.

## Stock insuficiente, avisado a tiempo

La comprobación va **sobre la misma conexión de la transacción**. Preguntarlo por otra
devolvería lo que había antes de empezar, y en una venta de dos líneas del mismo artículo le
daría el visto bueno a las dos. El trigger de la 023 sigue debajo para cualquier escritor.

`faltantes_de_stock()` contesta antes de intentar guardar, para que el rechazo no llegue
cuando la operadora ya cargó toda la venta.

Una venta nunca puede pedir la excepción administrativa de stock negativo.

## Idempotencia durable

Tabla `sale_stock_integrations`, más las claves `VENTA:{entrada}` del hecho y
`VENTA:{entrada}:{línea}` de cada movimiento. Probado guardando tres veces, reabriendo desde
la base, y con un repositorio nuevo sin nada en memoria — que es el caso después de un
corte.

## Edición postventa: el límite, explícito

| | |
| --- | --- |
| **Bloqueado** | cambiar, agregar o borrar líneas de una venta integrada; anularla |
| **Permitido** | teléfono, observaciones, cliente, vendedora — todo lo de `cash_entries` |

La entrada no queda congelada entera; sólo lo que decide el inventario. Cuatro triggers lo
hacen cumplir para cualquier escritor.

**No hay reversión y no se improvisó.** Necesita el movimiento compensatorio de la 023 atado
al circuito de negocio de la anulación. Media reversión sería peor que bloquear — y es el
boundary más urgente de los que quedan abiertos.

## Histórico y dinero

El backfill planifica y no escribe: una línea vieja identifica lo que alguien escribió esa
tarde, no un artículo del catálogo. Elegir uno por parecido lo inventaría **y además
cambiaría el stock de hoy** con una inferencia sobre el pasado.

Una salida `VENTA` mueve una unidad y no mueve un guaraní. Totales y arqueo sin cambios,
verificado contando filas y comprobando que el módulo no escribe en ninguna tabla de Caja.

## Verificación

- 42 pruebas dirigidas escritas antes de la implementación.
- Suite completa: **848 passed, 4 subtests, exit 0** (806 baseline + 42).
- Cadena 022…025 sobre una **copia** de la base real: 12 `cash_entries` y 10 `sale_items`
  intactos, 0 filas cambiadas, `integrity ok`, `foreign_key_check 0`, totales sin cambios.
- Los invariantes se probaron con una venta **real** de la Óptica marcada como integrada:
  las seis mutaciones prohibidas rechazadas, y una venta no integrada sigue editable y
  borrable como siempre.
- Base productiva real sin tocar: `sha256 1c4fcc40…98ec` antes y después.
- Gates: Librarian PASS, QA PASS, Auditor PASS, Artifact Consistency PASS.

El flake heredado `BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001` volvió a aparecer una vez y pasa
aislado. Segunda misión consecutiva: ya conviene atacarlo.

## Producción, intacta

21 migraciones. Ninguna de las cuatro instalada. Sin PR, sin merge, sin empaquetar. `main`
sigue en `7db56a0` — y ahora son **cuatro** migraciones acumuladas esperando release: ese
gate ya no es trámite.
