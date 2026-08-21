# IMPLEMENTATION PACKET — BC-OPTICA-INVENTORY-LEDGER-V1-002

Base: `ed0dbba` = slice 1 (`feature/bc-optica-commercial-core-foundation-v1-001`), que a su
vez sale de `origin/main` = `7db56a0` = BC Caja 1.0.0-rc.31, instalada y validada en la
Óptica. Worktree: `.worktrees/inventory-ledger-002`. Rama:
`feature/bc-optica-inventory-ledger-v1-002`.

Se deriva del slice 1 y no de `main` por una razón concreta: el ledger referencia
`articles(id)` y `suppliers(id)`, que crea la migración 022. Sobre `main` no compilaría.

## Regla fundacional: "nada existe porque sí"

Este slice es donde la regla deja de ser un principio y pasa a ser esquema.

| Invariante | Dónde vive, verificable |
| --- | --- |
| Todo dato tiene origen real | `stock_movements.event_id` → `domain_events`; y si no hay evento, igual hay `actor`, `occurred_at`, `idempotency_key`. Nunca anónimo |
| Se carga una vez, donde ocurre el hecho | El movimiento se registra donde pasa; Gestión Central lee `stock_actual`, no vuelve a cargar |
| Nada se recarga si puede derivarse | El stock **es** `SUM(quantity)`. No hay contador que mantener |
| Todo cambio extraordinario tiene causa, responsable, fecha, referencia, efecto y auditoría | `reason_code`, `note`, `actor`, `occurred_at`, `document_*`, `event_effects`, append-only |
| Gestión Central consolida, no vuelve a cargar | La vista `stock_actual` es derivada; no hay tabla de stock editable |
| No se borra ni reescribe historia | Triggers `_sin_update` / `_sin_delete` en `stock_movements`, `domain_events` y `event_effects` |
| Corrección por compensación | `compensar()` crea el movimiento inverso con `compensates_id`; índice único que impide compensar dos veces |
| Real / estimado / pendiente / no atribuible | `CostStatus.PENDIENTE_DE_CONCILIACION` (slice 1) y `PlanDeBackfill` declarando lo histórico como NO ATRIBUIBLE |

## Event Spine V1

`domain_events` es una tabla de hechos, no un event bus. Montar un bus hoy sería
infraestructura antes que necesidad; lo que sí no se puede agregar después sin migrar dos
veces es la **forma** del hecho:

`event_id`, `event_type`, `source`, `entity_type`, `entity_id`, `destination`, `actor`,
`occurred_at`, `recorded_at`, `payload`, `processing_state`, `processed_at`,
`failure_reason`, `idempotency_key` único.

`event_effects` guarda qué produjo cada hecho: sin eso, "efectos derivados" sería una
promesa. Con eso se va del evento a sus movimientos y del movimiento a su evento.

Los hechos que el diseño ya contempla y que este slice **no** implementa:

```
PURCHASE_CONFIRMED  → proveedor/Gestión → INGRESO_COMPRA por destino     (slice 3)
SALE_COMPLETED      → Movimiento de Caja → VENTA → Pedido/Trabajo
                      → FactuFácil pendiente → revisión → estadísticas   (slices 4 y 6)
```

El ledger ya es el primer consumidor del spine, así que esas rutas cuelgan de la misma
tabla sin cambiarle la forma.

## El ledger

`stock_movements`, append-only, por artículo y destino.

**`quantity` va con signo y el signo lo decide `kind`.** No hay columna de signo al lado
del tipo: si la hubiera, nada impediría una venta que suma. Un `CHECK` ata las dos cosas,
y por eso el stock es literalmente `SUM(quantity)` — expuesto como la vista `stock_actual`.

Es la misma decisión que `tracks_stock` en el slice 1, por el mismo motivo.

### Tipos

| Entradas (+) | Salidas (−) |
| --- | --- |
| `INGRESO_COMPRA` | `VENTA` |
| `INGRESO_PRODUCCION` | `SALIDA_ADMINISTRATIVA` |
| `INGRESO_ADMINISTRATIVO` | `DEVOLUCION_PROVEEDOR` |
| `AJUSTE_POSITIVO` | `AJUSTE_NEGATIVO` |
| `TRANSFERENCIA_ENTRADA` | `TRANSFERENCIA_SALIDA` |

Las transferencias quedan **declaradas y no usadas**: el vocabulario existe para que el
slice que las implemente no tenga que migrar. El slice 1 había dejado un único
`TRANSFERENCIA`, que no puede decir de qué lado del traslado está el destino — y el signo
se deriva justamente de eso. Se abre en dos. Nada consumía el nombre viejo, así que se
corrige acá y no queda una tercera forma de escribir lo mismo.

### Movimientos de Caja vs. movimientos de Stock

Separados. Una salida administrativa por rotura descuenta una unidad y **no toca un
guaraní**. Si además hubo un hecho económico, ese hecho se registra por su lado. El ledger
no escribe en ninguna tabla de Caja y no hay una sola línea que lo haga.

### Ingreso administrativo

Entra stock sin factura, con motivo obligatorio de un catálogo cerrado y sembrado
(`administrative_entry_reasons`: `STOCK_ENCONTRADO`, `CORRECCION_INVENTARIO`,
`FUERA_DE_CIRCUITO`, `OTRO`), observación obligatoria en los cuatro, usuario, fecha y
cantidad. **No crea una compra ficticia** — no hay proveedor, ni documento, ni impacto en
Caja — y hay prueba de eso.

Son dos catálogos y no uno con bandera: «roto» no puede ser el motivo por el que algo
entró, y «stock encontrado» no puede ser el motivo por el que algo salió. Cuál se usa se
**deriva** del tipo de movimiento; una columna que lo dijera podría contradecirlo.

### Salida administrativa

Consume los 7 motivos que la 022 ya había sembrado. `Compra +1` seguido de
`SALIDA_ADMINISTRATIVA -1 / ROTO` deja las dos filas y el historial completo. La compra
original no se toca: es imposible tocarla, el trigger lo impide.

### Producción interna

`INGRESO_PRODUCCION` sin proveedor ni factura, con cantidad, fecha, responsable y
observación/lote. Sólo válido para artículos de naturaleza `PRODUCCION_INTERNA`: un armazón
entraría por compra.

### Stock negativo

Bloqueado, y no sólo en Python. El trigger `stock_movements_sin_negativo` lo impide para
**cualquier** escritor.

La excepción es administrativa, explícita y auditada: `negative_override` sólo se admite en
`SALIDA_ADMINISTRATIVA` y `AJUSTE_NEGATIVO`, y sólo con motivo y observación — el `CHECK`
lo exige en la base. **Una `VENTA` nunca puede pedirla**: para eso existe el bloqueo.

### Concurrencia

`BEGIN IMMEDIATE` en toda escritura. Sin eso, dos cajas descontando la última unidad al
mismo tiempo podrían leer stock 1 las dos. Con eso, la segunda espera y cuando entra el
trigger ya ve el movimiento de la primera. Hay una prueba con dos hilos y una barrera.

### Idempotencia

`idempotency_key` único en la base. Registrar dos veces la misma clave devuelve el
movimiento original y no descuenta de nuevo. Reprocesar un `PURCHASE_CONFIRMED` no duplica
el stock, y `event_effects` sigue teniendo un solo efecto.

## Compatibilidad con lo histórico

`planificar_backfill_historico()` calcula y **no escribe**, igual que el importador del
slice 1. Falla cerrado: las 10 líneas de venta en producción no tienen artículo del
catálogo y qué se vendió en ellas es un dato **NO ATRIBUIBLE**. Elegir uno sería
inventarlo.

Un inventario que arranca en cero y se explica es más útil que uno que arranca con un
número que nadie puede justificar. Las líneas con `article_id NULL` siguen funcionando.

## Preparación para Compras

El movimiento acepta ya la referencia durable que el slice 3 necesita: `supplier_id`,
`document_kind`, `document_id`, `document_line_id`, `document_number`, más `destination`.
`movimientos_de_documento()` permite ir del origen a sus movimientos. **Compras no se
implementa acá**; lo que se garantiza es que enganche sin otra migración.

## Restricciones respetadas

- Migración **estrictamente aditiva**: sólo `CREATE TABLE/INDEX/VIEW/TRIGGER IF NOT
  EXISTS`. **Ni un solo `ALTER TABLE`** — a diferencia de la 022, ni siquiera modifica una
  tabla existente, así que ninguna fila productiva puede perderse. Hay una prueba que lo
  verifica leyendo el `.sql`.
- La cadena va de 22 a 23.
- Reglas económicas de Caja: sin cambios. UI: sin cambios.
- `main` no se toca. La base productiva real no se toca.
- Verificado sobre una **copia** de la base real de la Óptica, no sobre una fixture.

## Contrato ajeno actualizado

`test_la_cadena_de_migraciones_llega_a_022` contaba las migraciones a mano —exactamente lo
que el slice 1 le había corregido a otros seis contratos, reintroducido en su propia
prueba. Su intención era "la 022 se aplicó y no falta ninguna", no "nunca va a haber una
023". Ahora deriva la lista de `tests/migration_chain.py` y sigue exigiendo que la `022`
esté.

## Pruebas dirigidas primero

`tests/comercial/test_inventory_ledger.py`, 49 pruebas escritas antes de la
implementación, cubriendo los 18 puntos pedidos. Detalle en `SUMMARY.md`.
