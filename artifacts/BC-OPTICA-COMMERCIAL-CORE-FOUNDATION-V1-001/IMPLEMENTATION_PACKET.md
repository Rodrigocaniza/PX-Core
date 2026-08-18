# IMPLEMENTATION PACKET — BC-OPTICA-COMMERCIAL-CORE-FOUNDATION-V1-001

Base: `origin/main` = `7db56a0` = BC Caja 1.0.0-rc.31, instalada y validada en la Óptica.
Worktree: `.worktrees/commercial-core-001`. Rama:
`feature/bc-optica-commercial-core-foundation-v1-001`.

## Qué es esto y qué no

BC Caja **evoluciona** hacia el sistema operativo/comercial de la óptica. No se crea un
sistema paralelo: mismo ejecutable, misma base SQLite, misma cadena de migraciones. El
nombre definitivo del producto queda pendiente y no se fuerza en el esquema.

El objetivo del bloque es que `Artículos → Compras → Stock → Ventas → Trabajos → Revisión →
Gestión Central` queden **enlazados desde el principio**. El objetivo de *esta misión* es
mucho más chico: la foundation canónica sobre la que esos slices se apoyan.

## Subdivisión en slices

El alcance completo es demasiado grande para una misión. Se subdivide así, y esta misión
ejecuta **sólo el slice 1**, que es el que desbloquea a todos los demás:

| # | Slice | Desbloquea | Estado |
| --- | --- | --- | --- |
| **1** | **Catálogo canónico: artículos, naturalezas, marcas, categorías, proveedores, destinos, motivos de salida** | todo lo demás | **esta misión** |
| 2 | Ledger de inventario auditable | Stock, salidas administrativas | diseñado acá, no implementado |
| 3 | Compras centralizadas con distribución por destino | Compras, costos | diseñado acá, no implementado |
| 4 | Enlace venta → artículo + Consumidor final | Ventas, Gestión Central | preparado acá (columna y constante), no activado en UI |
| 5 | Trabajos: cristales y composturas como no stockeables | Trabajos | vocabulario definido acá |
| 6 | FactuFácil reducido a bandeja de confirmación | salida de FactuFácil | contrato escrito acá |

Nada de los slices 2-6 se implementa en esta misión. Lo que sí se hace es **fijar el
vocabulario** para que cuando se implementen no haya que migrar dos veces.

## Slice 1 — alcance exacto

### Naturaleza del ítem, explícita

Cuatro, cerradas, en `CHECK` de base y en `Enum` de dominio:

| Naturaleza | Mueve stock | Ejemplo real |
| --- | --- | --- |
| `PRODUCTO_STOCKEABLE` | sí | armazón, líquido, estuche |
| `SERVICIO_NO_STOCKEABLE` | no | compostura, ajuste, consulta |
| `TRABAJO_BAJO_PEDIDO` | no | cristal recetado, insumo pedido para un trabajo |
| `PRODUCCION_INTERNA` | sí, por producción | lo que la óptica arma y luego vende |

**`tracks_stock` no es una columna.** Se deriva de la naturaleza en el dominio. Una columna
libre permitiría un armazón que no mueve stock y una compostura que sí, que es exactamente
el error que este modelo existe para impedir.

Consecuencia directa de lo pedido: **composturas y cristales no se representan con
productos, facturas ni clientes ficticios.** Una compostura es un `SERVICIO_NO_STOCKEABLE`
y un cristal es un `TRABAJO_BAJO_PEDIDO`. Ninguno genera unidades en el inventario, así que
no hay nada ficticio que crear ni que después limpiar.

### Catálogos

`article_categories`, `brands`, `suppliers`, `articles`, `administrative_exit_reasons`.

Se **reutiliza**, no se duplica:

- `laboratories` (migraciones 003 y 016) ya es el catálogo canónico de laboratorios.
  `suppliers.laboratory_id` lo referencia; no se crea un catálogo paralelo.
- Los destinos son `ASUNCION` y `PILAR`, el mismo vocabulario que ya usan
  `cash_register_branches`, `tracked_works.origin_branch` y `orders.branch`. Se expresa
  como `Destination` en el dominio, **sin tabla nueva**: inventar una tabla de sucursales
  al lado de la que ya funciona sería el sistema paralelo que se pidió evitar.

### Motivos de salida administrativa

Catálogo sembrado y cerrado: `ROTO`, `RAYADO`, `PERDIDA`, `DETERIORO`, `USO_INTERNO`,
`ERROR_INVENTARIO`, `OTRO`. Es catálogo, por eso entra en este slice; el *movimiento* que
los usa es el slice 2. Cada salida exigirá motivo, observación, usuario, fecha y cantidad.

### El enganche con lo que ya existe

`sale_items.article_id`, **nullable**, referenciando `articles(id)`. Es la costura entre la
venta que hoy se escribe a mano y el catálogo. Nullable a propósito: las 10 líneas de venta
que ya existen en producción no tienen artículo y **no se les inventa uno**. La UI no cambia
en este slice.

### Importador

Se deja **contrato y modelo**, no carga masiva. `planificar_importacion()` calcula un plan a
partir de filas crudas y lo devuelve sin escribir nada: cuántas altas, cuántas
actualizaciones, cuántas rechazadas y por qué. Recién con un plan limpio y explícitamente
aplicado se escribe. Cargar la base real de artículos hoy, sin ese ciclo, no sería
reversible ni verificable.

## Diseño de los slices siguientes, para no migrar dos veces

**Ledger (slice 2).** Tabla append-only `stock_movements` con
`kind IN ('INGRESO_COMPRA','INGRESO_PRODUCCION','VENTA','SALIDA_ADMINISTRATIVA','AJUSTE_POSITIVO','AJUSTE_NEGATIVO','TRANSFERENCIA')`,
por artículo y destino, con usuario, fecha, motivo y referencia al documento de origen. El
stock es la suma del ledger, nunca un contador editable. **Nunca se modifica ni se borra
una compra histórica para sacar stock**: se registra el movimiento que corresponda —salida
administrativa o ajuste auditado— y la compra queda intacta.

**Compras (slice 3).** La factura del proveedor pertenece a Gestión Central/empresa **una
sola vez**. Para productos físicos, una línea distribuye cantidades a Asunción y Pilar y la
suma distribuida debe igualar la comprada; confirmar la factura genera los movimientos de
stock por destino. Para laboratorio y costos consolidados se admite factura de empresa
Asunción+Pilar sin reparto manual, porque la fuente no permite atribución fiable, y el costo
del cristal queda en `PENDIENTE_DE_CONCILIACION` mientras no haya dato real. **No se
inventa costo.**

**FactuFácil (slice 6).** Es temporal. Su bandeja queda reducida a: ver lo pendiente de
cargar, confirmar que fue cargado, registrar el N.º de factura y habilitar la condición de
comisión recién después de esa confirmación. **No modifica ventas.** Hoy FactuFácil no
existe en `CajaDiaria.py` —hay un test que lo verifica— y sólo aparece como
`factufacil_status` en `gestion_central`. Esta misión no lo toca.

**Gestión Central.** Todo lo que nace de compras, ventas, stock, trabajos, facturas y
proveedores lleva `created_at`/`updated_at` e identidad estable desde el día uno,
exactamente como ya hacen `tracked_works` y `laboratories`, para que la alimentación sea
incremental y no una recarga manual posterior.

**Consumidor final.** Constante de dominio `CONSUMIDOR_FINAL`, no un cliente en tabla. Una
venta sin cliente identificado normaliza a esa constante; **no se crea un cliente ficticio
por caso**.

## Restricciones que se respetan

- Migración **aditiva**: sólo `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS` y
  un `ALTER TABLE ADD COLUMN` nullable. No altera ni reconstruye ninguna tabla existente.
- Ninguna fila productiva se modifica. Los 12 movimientos, 8 pedidos y 10 líneas de venta
  quedan como están.
- Reglas económicas de Caja: sin cambios.
- `main` no se toca directamente; se trabaja en rama y worktree aislados.
- La migración lleva la cadena de 21 a 22. Es un cambio de esquema real sobre producción y
  se declara como tal: el rollback sigue siendo restaurar el archivo de base desde el
  backup, como con la 015.

## Pruebas dirigidas primero

`tests/comercial/test_commercial_core_foundation.py`, escritas antes que la implementación:
naturalezas cerradas, `tracks_stock` derivado y no seteable, catálogos con unicidad
insensible a mayúsculas, motivos de salida sembrados completos, `Destination` reusando el
vocabulario existente, plan de importación que no escribe, `CONSUMIDOR_FINAL` normalizando
vacío, y compatibilidad: la base de rc.31 migra a 022 sin perder una sola fila.
