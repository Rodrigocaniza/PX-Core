# BC-OPTICA-COMMERCIAL-CORE-FOUNDATION-V1-001 — slice 1

**El catálogo canónico existe. Lo demás queda diseñado, no construido.**

BC Caja empieza a ser el sistema comercial de la óptica sin dejar de ser BC Caja: misma
base, mismo ejecutable, misma cadena de migraciones. No hay un sistema al lado.

## Lo que se decidió, que es lo que importa

**La naturaleza del ítem manda, y no hay una columna que la contradiga.** Hay cuatro
naturalezas cerradas, en `CHECK` de base y en `Enum` de dominio, y `tracks_stock` **no es
un campo**: se deriva de la naturaleza. Pasarle `tracks_stock` a un `Article` es un
`TypeError`, y hay una prueba que lo fija. Si moviera stock fuera editable, nada impediría
un armazón que no descuenta y una compostura que sí.

De ahí sale, gratis, lo que se pidió sobre composturas y cristales: una compostura es
`SERVICIO_NO_STOCKEABLE` y un cristal es `TRABAJO_BAJO_PEDIDO`. Ninguno genera unidades de
inventario, así que **no hay productos, facturas ni clientes ficticios que crear** — ni que
limpiar después.

**Se reutilizó en vez de duplicar, en los dos lugares donde era tentador no hacerlo:**

- `laboratories` ya es el catálogo canónico desde la 016. `suppliers.laboratory_id` lo
  referencia. Un laboratorio que además factura es un proveedor que apunta a su
  laboratorio, no una segunda ficha que alguien tenga que mantener sincronizada a mano.
- Los destinos son `ASUNCION` y `PILAR`, el mismo vocabulario de `cash_register_branches`,
  `tracked_works.origin_branch` y `orders.branch`. Quedó como `Destination` en el dominio,
  **sin tabla nueva**. Crear un catálogo de sucursales al lado del que ya funciona habría
  sido exactamente el sistema paralelo que se pidió evitar.

**La costura con lo que ya existe es una sola columna:** `sale_items.article_id`, nullable.
Las 10 líneas de venta que hay en producción no tienen artículo del catálogo y **no se les
inventó uno**. La UI no cambia en este slice.

**El importador no importa todavía.** `planificar_importacion()` calcula qué pasaría —altas,
actualizaciones, rechazos con motivo— y no escribe nada. Un plan con rechazos no es
aplicable: importar 900 de 1000 filas deja el catálogo en un estado que nadie sabe
describir. Cargar la base real hoy, sin ese ciclo, no habría sido reversible ni verificable.

## Verificación

| | |
| --- | --- |
| Suite completa | **714 passed, 4 subtests, exit 0** (682 baseline + 32 nuevas) |
| Migración sobre **copia de la base productiva real** | 0 tablas perdidas, 0 filas perdidas |
| `sale_items` tras migrar | 10 filas intactas, las 10 con `article_id` NULL |
| `integrity_check` · `foreign_key_check` | ok · 0 |
| Cadena de migraciones | 21 → 22 |
| Motivos de salida sembrados | 7 |
| `SUM(cash_entries.total)` | 6.400.000, sin cambios |
| Base productiva **real** | sin tocar, `sha256` idéntico |

La migración se probó contra una copia de la base de la Óptica, no contra una fixture. Es
la única forma de saber que 022 corre sobre datos reales y no sobre un esquema ideal.

## Contratos ajenos que hubo que mover, y por qué

Seis pruebas fijaban la cadena de migraciones en 21, repitiendo la lista de versiones a
mano. Su intención era *"este slice no agrega migraciones"*, no *"nunca habrá una 022"*.

Se preservó la intención sin diluirla: las de RC27 y Apertura ahora cuentan **la línea de
Caja hasta 021**, que es lo que realmente afirmaban; las que enumeraban versiones derivan la
lista de `tests/migration_chain.py`, así el próximo slice no rompe cinco pruebas ajenas.
`test_recovery_drill` además ganó una afirmación nueva: tras migrar, las líneas de venta
históricas quedan con `article_id` en NULL.

## Por qué esto no se promueve a `main`

Agrega la migración 022 y todavía no se empaquetó ni se instaló. `main` es lo que se
empaqueta: promoverlo ahora haría que la próxima RC arrastre un cambio de esquema que nunca
pasó por un gate de instalación. Queda en su rama, pusheada, hasta que haya decisión de
release.

## Lo que sigue, ya diseñado

Slices 2 a 6 —ledger de inventario, compras centralizadas con distribución por destino,
enlace venta→artículo, trabajos, y la reducción de FactuFácil a bandeja de confirmación—
están especificados en `IMPLEMENTATION_PACKET.md` con su vocabulario ya fijado acá
(`StockMovementKind`, `CostStatus`, `AdministrativeExitReason`, `Destination`,
`CONSUMIDOR_FINAL`), justamente para no tener que migrar dos veces.

Nada de eso se implementó. El slice que sigue es el **2, el ledger**.
