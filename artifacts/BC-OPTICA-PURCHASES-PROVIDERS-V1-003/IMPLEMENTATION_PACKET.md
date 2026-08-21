# IMPLEMENTATION PACKET — BC-OPTICA-PURCHASES-PROVIDERS-V1-003

Base: `54f5f06` = slice 2 (`feature/bc-optica-inventory-ledger-v1-002`), que sale de
`ed0dbba` = slice 1, que sale de `origin/main` = `7db56a0` = BC Caja 1.0.0-rc.31,
instalada y validada en la Óptica. Worktree: `.worktrees/purchases-003`. Rama:
`feature/bc-optica-purchases-providers-v1-003`.

## La idea que ordena todo el slice

**Una factura real se registra una sola vez** y sus consecuencias se derivan.

El stock que aparece después de confirmar una compra no se carga: es la consecuencia de un
hecho que quedó registrado. Y como quedó registrado, se puede ir desde cualquier unidad en
el depósito hasta la factura, la línea, el proveedor y la persona que confirmó.

## Lo que se reutilizó en vez de crear de nuevo

| Ya existía | Cómo se usa |
| --- | --- |
| `suppliers` (022) | **Se extiende** con `address`, `email`, `contact_name`. Crear una tabla `proveedores` al lado sería el sistema paralelo que se viene evitando |
| `articles` + naturaleza (022) | La línea no lleva bandera de stock: se deriva de la naturaleza, igual que en el slice 1 |
| `domain_events` / `event_effects` (023) | `PURCHASE_CONFIRMED` es un hecho más del mismo spine. Cero cambios al spine |
| `stock_movements` (023) | Los `INGRESO_COMPRA` son movimientos normales. **Cero cambios al ledger** |
| Referencia durable del movimiento (023) | `supplier_id`, `document_kind`, `document_id`, `document_line_id`, `document_number` ya estaban previstos y se llenan ahora, sin migrar el ledger |
| `Destination` ASUNCION/PILAR | Mismo vocabulario. Sin tabla de sucursales |

Del ledger sólo se necesitó **exponer** lo que ya hacía: `registrar_en(connection, …)`,
`asegurar_evento_en(…)` y `marcar_evento_procesado_en(…)`. La lógica no cambió; lo que
cambió es que ahora el dueño de la transacción puede ser otro, que es lo que hace posible
que confirmar sea atómico.

## Modelo

### Proveedor

`suppliers` con identidad, razón social, RUC/CI, teléfono, dirección, email, contacto,
activo/inactivo y auditoría. **No es un CRM.**

El duplicado se bloquea **sólo cuando hay identidad fiscal fiable**: índice único parcial
sobre `document` donde el documento no está vacío. Dos proveedores sin RUC conviven sin
problema, porque inventarles una identidad para poder compararlos sería peor que no
compararlos.

No hay baja. Un proveedor se desactiva: borrarlo dejaría facturas apuntando a nadie, y esas
facturas explican stock que existe.

### Compra

`purchases` representa la factura **a nivel empresa**, una sola vez. Índice único
`(supplier_id, document_number)`: la misma factura del mismo proveedor no entra dos veces.
Cargarla una vez por sucursal sería la misma factura existiendo dos veces, con dos verdades
posibles.

`document_total` es lo que dice el papel; la suma de las líneas es derivada. Se guardan los
dos y se contrastan **al confirmar**: que no coincidan es un hecho a mostrar, no uno que el
sistema deba arreglar solo.

`due_date` es derivado de la fecha y el plazo. No se recibe —pasarlo es `TypeError`— y un
trigger verifica que la fila guardada no contradiga su origen. Un `CHECK` ata plazo y
vencimiento a la condición: existen si y sólo si hay crédito.

Dos estados: `BORRADOR` y `CONFIRMADA`. **No hay `ANULADA`** — ver *Boundary* más abajo.

### Líneas

`purchase_lines` referencia el artículo canónico y guarda cantidad, costo unitario y la
descripción que traía la factura. No hay columna de total —es cantidad por costo— ni
columna que diga si mueve stock: eso se deriva de la naturaleza.

Una línea no-stock **pertenece legítimamente a la factura**: el laboratorio factura
cristales, y esa línea conserva su costo y su documentación. Lo único que no hace es
generar unidades.

### Distribución física

`purchase_line_distributions`: cuántas unidades de la línea van a cada sucursal.

Invariantes, y dónde se hacen cumplir:

| Invariante | Dónde |
| --- | --- |
| Sólo se distribuye lo que mueve stock | Trigger, derivado de `articles.nature` |
| No se distribuye más de lo comprado | Trigger, acumulando lo ya repartido |
| Cantidades positivas | `CHECK` + dominio |
| Un destino no se repite en la línea | `UNIQUE` + dominio |
| Al confirmar, lo repartido **iguala** lo comprado | Servicio: un borrador puede estar incompleto, pero no puede generar stock estando incompleto |

Lo que no se determina, no se inventa: una línea stockeable sin reparto **no se confirma**,
en vez de mandar todo a Asunción por defecto.

## Confirmación

Todo en una sola transacción `BEGIN IMMEDIATE`:

1. se registra el hecho `PURCHASE_CONFIRMED`;
2. nace un `INGRESO_COMPRA` por cada (línea stockeable × destino), enlazado a proveedor,
   documento, línea y destino;
3. cada movimiento queda como `event_effect` del hecho;
4. el hecho pasa a `PROCESADO`;
5. la compra pasa a `CONFIRMADA` con quién y cuándo.

O no pasa nada de eso. Media factura confirmada sería peor que ninguna, porque el stock
parcial se ve igual que el correcto.

**El hecho se registra antes que sus efectos**, y eso no es un detalle de orden: una
factura de puros servicios se confirma igual y su `PURCHASE_CONFIRMED` tiene que quedar
registrado aunque no arrastre un solo movimiento. La primera versión lo insertaba como
efecto colateral del primer movimiento y esa factura fallaba con violación de clave
foránea; la prueba de línea no-stock lo encontró.

### Idempotencia

Tres claves, todas derivadas del camino:

- evento: `COMPRA:{purchase_id}`
- movimiento: `COMPRA:{purchase_id}:{line_id}:{destino}`
- compra confirmada: el propio estado

Reconfirmar devuelve el mismo hecho y los mismos movimientos sin escribir nada.

## Trazabilidad mecánica

La vista `stock_origen_compra` contesta con una consulta —no leyendo código— qué factura,
qué proveedor, qué línea, qué destino, qué evento, cuándo y quién confirmó, para cualquier
unidad que esté en el depósito.

## Dinero y stock, separados

Registrar o confirmar una factura **no toca Caja**. Una compra a crédito es una obligación,
no una salida de dinero de hoy. Hay pruebas que cuentan las filas de `cash_days`,
`cash_entries`, `cash_counts` y `cash_day_corrections` antes y después, y verificación
mecánica de que el módulo no nombra ninguna de esas tablas.

## Boundary explícito: lo que no se improvisó

**No hay anulación ni nota de crédito.** Exceden el slice, y media anulación improvisada
sería peor que ninguna. Lo que se hace mientras tanto es **impedir la mutación
destructiva**: nueve triggers hacen imposible editar o borrar una compra confirmada, sus
líneas o su reparto, desde cualquier escritor. La factura original nunca desaparece para
"corregir" el stock; para eso ya existe el movimiento compensatorio del slice 2.

**No hay Cuentas por Pagar.** El vencimiento se guarda y se indexa, que es lo necesario
para preservar la factura; la gestión de la deuda es otro slice.

**No hay UI.** El flujo es demostrable de punta a punta por el servicio y las 43 pruebas.
La consigna priorizaba exactitud de dominio, persistencia, trazabilidad, idempotencia e
integración spine → ledger, y ahí fue todo el esfuerzo.

**No hay transferencias entre sucursales.** El vocabulario quedó declarado en el slice 2 y
sigue sin usarse.

**No hay desglose de IVA.** La factura guarda su total; inventar una apertura impositiva
sin evidencia sería exactamente lo que el principio prohíbe.

## Migración 024

Aditiva. Lo único que toca de lo existente son tres columnas `ADD COLUMN` con default sobre
`suppliers`, tabla que la 022 crea y que en producción todavía no tiene ni una fila. No
reconstruye ni reescribe nada. Cadena 23 → 24.

## Pruebas dirigidas primero

`tests/comercial/test_purchases_providers.py`, 43 pruebas escritas antes de la
implementación, cubriendo los 16 puntos pedidos.
