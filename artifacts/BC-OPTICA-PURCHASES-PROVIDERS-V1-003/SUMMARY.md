# SUMMARY — BC-OPTICA-PURCHASES-PROVIDERS-V1-003

Slice 3 de 6. La factura del proveedor se registra una sola vez y el stock de las dos
sucursales sale de ahí.

## El circuito, completo

```
Factura real → proveedor → líneas → distribución física → confirmar
            → PURCHASE_CONFIRMED → event_effects → INGRESO_COMPRA por línea y destino
            → stock derivado
```

Y en sentido inverso, con una sola consulta: de cualquier unidad en el depósito a la
factura, el proveedor, la línea, el destino, el evento, cuándo y quién confirmó.

## Lo que este slice **no** tuvo que construir

El ledger no se rediseñó. El spine no cambió de forma. La referencia durable
(`supplier_id`, `document_kind`, `document_id`, `document_line_id`, `document_number`) que
el slice 2 dejó preparada se llena ahora **sin una sola migración del ledger**, que es
exactamente lo que ese slice había prometido.

De `SQLiteStockLedgerRepository` sólo hizo falta **exponer** lo que ya hacía —
`registrar_en(connection, …)`, `asegurar_evento_en(…)`, `marcar_evento_procesado_en(…)` —
para que el dueño de la transacción pueda ser Compras. La lógica de inserción,
idempotencia, stock negativo y append-only no cambió una línea.

`suppliers` se extendió con `address`, `email` y `contact_name` en vez de crear una tabla
de proveedores al lado.

## Las decisiones que importan

**El duplicado de proveedor se bloquea sólo cuando hay con qué.** Índice único parcial
sobre el RUC: dos proveedores sin identidad fiscal conviven, porque inventarles una para
poder compararlos sería peor que no compararlos.

**Una factura real existe una sola vez.** Índice único `(supplier_id, document_number)`.
Cargarla una vez por sucursal sería la misma factura con dos verdades posibles.

**El total del papel y la suma de las líneas se guardan los dos.** Uno es un dato con
origen, el otro es derivado. Que no coincidan es un hecho a mostrar al confirmar, no uno
que el sistema deba arreglar solo.

**El vencimiento no se carga.** Se deriva de la fecha y el plazo; pasarlo es `TypeError` y
un trigger verifica que la fila guardada no contradiga su origen.

**Lo que la factura no determina, no se inventa.** Una línea stockeable sin reparto no se
confirma — en vez de mandar todo a Asunción por defecto.

**Una línea no-stock pertenece a la factura.** El laboratorio factura cristales: esa línea
conserva su costo y su documentación, y no genera unidades.

## Confirmar es todo o nada

Una sola transacción `BEGIN IMMEDIATE`: el hecho, los movimientos, los efectos, el estado
del hecho y el estado de la compra. Con un fallo inyectado en el segundo movimiento no
queda nada — la compra sigue en `BORRADOR`, cero eventos, cero efectos, cero movimientos.

Reintentar no duplica: mismas claves de idempotencia derivadas del camino completo, y
reconfirmar devuelve el mismo hecho y los mismos movimientos sin escribir nada.

### Un defecto real que encontraron las pruebas

`PURCHASE_CONFIRMED` se insertaba como efecto colateral del primer movimiento de stock. Una
factura de puras líneas no-stock —laboratorio, servicios— fallaba al confirmar con
violación de clave foránea, porque la compra apuntaba a un evento que nunca se había
grabado.

Un hecho es durable aunque no produzca ninguna consecuencia. Ahora se registra por sí mismo
y antes que sus efectos. Lo encontró `test_una_linea_no_stock_no_genera_movimiento`,
escrita antes que el código.

## Historia: se bloquea, no se improvisa

Notas de crédito y anulación exceden el slice, y media anulación improvisada sería peor que
ninguna. En su lugar, **nueve triggers** hacen imposible editar o borrar una compra
confirmada, sus líneas o su reparto, desde cualquier escritor.

La factura original nunca desaparece para "corregir" el stock: para eso ya existe el
movimiento compensatorio del slice 2. Hay prueba de que sacar una unidad rota deja la
compra intacta.

## Dinero y stock, separados

Registrar y confirmar una factura no toca Caja. Una compra a crédito es una obligación, no
una salida de dinero de hoy. Cuentas por Pagar excede el slice: sólo se guarda e indexa el
vencimiento, que es lo necesario para preservar la factura.

## Verificación

- 43 pruebas dirigidas escritas antes de la implementación.
- Suite completa: **806 passed, 4 subtests, exit 0** (763 baseline del slice 2 + 43).
- Cadena 022+023+024 aplicada sobre una **copia** de la base real: 0 tablas perdidas, 0
  filas cambiadas en las 25 preexistentes, `integrity_check ok`, `foreign_key_check 0`,
  cadena 21 → 024, totales de Caja sin cambios.
- **14 invariantes probados sobre esa copia con filas reales sembradas**, no sobre tablas
  vacías — un trigger de fila sobre tabla vacía no rechaza nada, y eso ya dio un falso
  resultado en el slice anterior.
- Base productiva real sin tocar: `sha256 1c4fcc40…98ec` antes y después.
- Gates: Librarian PASS, QA PASS, Auditor PASS, Artifact Consistency PASS.

Una corrida intermedia dio 5 errors en `tests/gestion_central/test_ui_interactions.py`.
Aislados pasan y la corrida siguiente dio 806 limpios: es el flake heredado
`BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001`, agravado por procesos de otra sesión compitiendo
por recursos. No lo introdujo este slice y no se lo corrigió.

## Y una causa raíz, no sólo su síntoma

`test_la_cadena_de_migraciones_llega_a_023` fijaba el final de la cadena. Es la **tercera**
vez que aparece el mismo error: el slice 1 se lo corrigió a seis contratos ajenos y lo
repitió en el propio; el slice 2 hizo lo mismo. Además de corregirla, se agregó
`afirmar_cadena_completa_con()` a `tests/migration_chain.py`, para que el próximo slice
tenga dónde apoyarse en vez de volver a escribirlo mal.

## Producción, intacta

21 migraciones. Ni la 022, ni la 023, ni la 024 instaladas. Sin promover a `main`, sin PR,
sin empaquetar: `main` es lo que se empaqueta, y promover ahora haría que la próxima RC
arrastre tres cambios de esquema que nunca pasaron gate de instalación.
