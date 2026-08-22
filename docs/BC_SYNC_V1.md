# BC Sync V1 — contrato de arquitectura

BC sigue operando localmente en cada sucursal. Sync replica hechos con IDs estables;
no copia bases operativas ni crea una base de negocio paralela.

## Límites

- `SyncEvent` es el sobre canónico: UUID global, instalación, sucursal, tipo, fecha,
  versión, payload mínimo, clave de idempotencia y estado.
- `SyncStore` mantiene únicamente journal técnico, outbox, inbox, nonces, conflictos
  y auditoría. SQLite usa WAL y `synchronous=FULL`.
- `SyncNode` publica/recibe y `AutoResumeWorker` reanuda al arrancar y por intervalo.
  El transporte es un puerto; no hay IP ni servidor productivo inventado.
- `SecurityAdapter` será implementado por BC Seguridad: identidad por instalación,
  firma/autenticación, nonce/timestamp y revocación. Sólo tests usan HMAC falso con
  una clave distinta por instalación.
- `SyncedHistoryReader` implementa `HistoryReader`; proyecta clientes, compras,
  recetas, sobres y eventos manteniendo `branch_id` y `event_id`, siempre read-only.

## Idempotencia, retry y conflictos

El emisor conserva un evento hasta ACK. El receptor tiene unicidad por `event_id`
y `(installation_id, idempotency_key)`. Una respuesta perdida puede causar otra
entrega, nunca otro hecho. Cada mensaje nuevo usa nonce; nonces vistos persisten.
Hechos distintos se conservan. Un conflicto real se inserta abierto en
`sync_conflicts` y sólo una resolución explícita, con auditoría, podrá cerrarlo.
No existe `last write wins`.

## FactuFácil transitorio

`BillingQueue` sólo referencia `sale_id` y guarda los datos fiscales necesarios
para ejecutar/conciliar la factura; no duplica el modelo Venta. Estados soportados:
`NO_REQUIERE_FACTURA`, `PENDIENTE_FACTU_FACIL`, `EN_PROCESO`, `CARGADA`, `ERROR`,
`REINTENTAR`, `ANULADA`, `CORREGIDA`. La clave idempotente evita altas repetidas.

`AssistedFactuFacilAdapter` prepara datos validados para carga manual y posterior
marcado con número de factura. No automatiza ni raspa la UI. Cada cambio publica
`FACTURACION_ESTADO` para Gestión Central. `DisabledFactuFacilAdapter` demuestra
que FactuFácil puede retirarse o sustituirse por e-Kuatia/proveedor/API oficial sin
cambiar Venta, Historial ni Sync.

## Instalación física pendiente

1. BC Seguridad debe emitir `installation_id` y credencial/certificado individual,
   registrar revocación y concretar validación de ventana temporal.
2. Elegir y autorizar transporte/red entre sedes; configurar endpoint por ambiente.
3. Crear fuera de la DB operativa un archivo Sync y otro de facturación por sede,
   con backup, ACL y espacio monitorizado.
4. Registrar `AutoResumeWorker` como servicio al inicio y configurar observabilidad.
5. Conectar productores de Venta/Receta/Sobre y el consumidor Gestión Central.
6. Ejecutar piloto ASUNCION↔PILAR, reconciliar conteos/auditoría y habilitar por fases.
7. Confirmar con FactuFácil si existe API oficial autorizada; hasta entonces usar el
   flujo asistido y definir responsables/numeración/conciliación.
