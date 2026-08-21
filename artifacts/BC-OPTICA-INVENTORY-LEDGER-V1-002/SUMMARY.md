# SUMMARY — BC-OPTICA-INVENTORY-LEDGER-V1-002

Slice 2 de 6. El stock deja de ser una cifra editable y pasa a ser la suma de los
movimientos que ocurrieron.

## Lo que decide todo lo demás

`stock actual = SUM(quantity)` sobre `stock_movements`, expuesto como la vista
`stock_actual`. No hay contador que mantener, así que no hay contador que pueda estar
mal. De ahí salen las demás consecuencias sin tener que pedirlas por separado:

- Una compra vieja nunca se modifica ni se borra para sacar una unidad rota. No es una
  regla de proceso: los triggers `_sin_update` y `_sin_delete` lo hacen imposible.
- Corregir no es reescribir. `compensar()` crea el movimiento inverso, el error y su
  corrección quedan los dos, y un índice único parcial impide compensar dos veces.
- Asunción y Pilar no se mezclan: el stock se agrupa por `(article_id, destination)`.

`quantity` va con signo y el signo lo decide `kind`, atado por un `CHECK`. Es la misma
decisión que `tracks_stock` en el slice 1 y por el mismo motivo: si el signo fuera un dato
aparte, nada impediría una venta que suma.

## Event Spine V1

`domain_events` + `event_effects`. No es un event bus, y no hacía falta que lo fuera. Lo
que sí no se puede agregar después sin migrar dos veces es la forma del hecho: identidad,
tipo, origen, entidad, destino, actor, momento, payload, estado de procesamiento, clave de
idempotencia, y qué produjo.

El ledger es el primer consumidor. `PURCHASE_CONFIRMED` y `SALE_COMPLETED` quedan
contemplados y **no** implementados: cuelgan de la misma tabla sin cambiarle la forma.

Reprocesar un hecho no lo aplica dos veces. Hay prueba: el mismo `PURCHASE_CONFIRMED`
registrado dos veces deja un movimiento, un efecto y el stock en 5.

## Los diez tipos

| Entradas (+) | Salidas (−) |
| --- | --- |
| `INGRESO_COMPRA` | `VENTA` |
| `INGRESO_PRODUCCION` | `SALIDA_ADMINISTRATIVA` |
| `INGRESO_ADMINISTRATIVO` | `DEVOLUCION_PROVEEDOR` |
| `AJUSTE_POSITIVO` | `AJUSTE_NEGATIVO` |
| `TRANSFERENCIA_ENTRADA` | `TRANSFERENCIA_SALIDA` |

Las transferencias quedan declaradas y sin usar. El slice 1 había dejado un único
`TRANSFERENCIA`, que no puede decir de qué lado del traslado está el destino — y el signo
se deriva justamente de eso. Se abre en dos ahora, cuando todavía nada lo consumía.

## Caja y Stock, separados

Una salida administrativa por rotura descuenta una unidad y no toca un guaraní. El ledger
no nombra `cash_entries`, `cash_days`, `cash_outflows` ni `cash_register`, y hay
verificación mecánica de eso, no sólo la intención.

## Stock negativo

Bloqueado para ventas y salidas normales, en la base y no sólo en Python: el trigger vale
para cualquier escritor, incluida una consola SQLite. Se verificó sobre la copia
productiva.

La excepción es administrativa, explícita y auditada — `negative_override` sólo en
`SALIDA_ADMINISTRATIVA` y `AJUSTE_NEGATIVO`, y sólo con motivo y observación, exigidos por
`CHECK`. Una `VENTA` nunca puede pedirla: para eso existe el bloqueo.

## Lo histórico: no se inventa

`planificar_backfill_historico()` calcula y no escribe, igual que el importador del slice
1. Las 10 líneas de venta de producción no tienen artículo del catálogo y qué se vendió en
ellas es un dato **NO ATRIBUIBLE**. Un inventario que arranca en cero y se explica es más
útil que uno que arranca con un número que nadie puede justificar.

## Verificación

- 49 pruebas dirigidas escritas antes de la implementación.
- Suite completa: **763 passed, 4 subtests, exit 0** (714 baseline del slice 1 + 49).
- Migración aplicada sobre una **copia** de la base real de la Óptica: 0 tablas perdidas,
  0 filas cambiadas, `integrity_check ok`, `foreign_key_check 0`, cadena 21 → 023,
  `SUM(cash_entries.total)` 6.400.000 sin cambios, las 10 líneas con `article_id NULL`.
- Append-only verificado sobre la copia **con filas reales sembradas**, no sobre tablas
  vacías: un trigger `BEFORE ... FOR EACH ROW` sobre una tabla vacía no rechaza nada, y la
  primera pasada del verificador lo reportó como fallo hasta que se sembró la fila.
- Base productiva real sin tocar: `sha256 1c4fcc40…98ec` antes y después.
- Gates: Librarian PASS, QA PASS, Auditor PASS, Artifact Consistency PASS.

## Un contrato ajeno corregido

`test_la_cadena_de_migraciones_llega_a_022` contaba las migraciones a mano — exactamente
lo que el slice 1 le corrigió a otros seis contratos, reintroducido en su propia prueba.
Ahora deriva la lista del directorio y sigue exigiendo que la 022 esté.

## Producción, intacta

Producción sigue en 21 migraciones. Ni la 022 ni la 023 están instaladas. La rama **no se
promueve a `main`** por el mismo criterio del slice 1: `main` es lo que se empaqueta, y
promover ahora haría que la próxima RC arrastre dos cambios de esquema que nunca pasaron
gate de instalación.
