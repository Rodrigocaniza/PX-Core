PASS
Mision BC-OPTICA-INVENTORY-LEDGER-V1-002, slice 2 de 6, sobre ed0dbba (slice 1), que sale
  de origin/main 7db56a0 = BC Caja 1.0.0-rc.31, instalada y validada en la Optica
Fuentes verificadas 10 sha256 ok
Contratos ajenos actualizados 1 sha256 ok
Convencion de hash: sha256 con saltos normalizados a LF, igual que el slice 1

ESTADO CANONICO VERIFICADO ANTES DE TOCAR NADA
origin/main 7db56a0, sin avanzar
Rama del slice 1 pusheada y limpia en ed0dbba, identica en local y en origin
Base productiva: 21 migraciones, 25 tablas, sha256 1c4fcc40...98ec
main local esta 147 commits detras de origin/main. Es una referencia vieja sin worktree
  asociado, no un conflicto; no se toca ni se actualiza porque esta mision no promueve
Otras sesiones activas: si, hay procesos de la mision BC-HEADLESS-EXECUTOR-CHANGED-PATHS
  -FIDELITY-V1-001 corriendo mission_workflow_engine.py y pytest. Operan sobre BC-Core,
  no sobre PX-Core/main. Se dejan como estan porque BC-Core no se toca en esta mision
0 leases vivos en PX-Core

BASE DERIVADA DEL SLICE 1, NO DE MAIN
El ledger referencia articles(id) y suppliers(id), que crea la 022. Sobre main no compilaria

REGLA FUNDACIONAL: DE PRINCIPIO A ESQUEMA
Todo dato tiene origen: stock_movements.event_id -> domain_events; sin evento, igual hay
  actor, occurred_at e idempotency_key. Un movimiento nunca es anonimo
Nada se recarga si puede derivarse: el stock ES SUM(quantity), expuesto como la vista
  stock_actual. No existe contador editable de stock en ningun lado
Cambio extraordinario con causa, responsable, fecha, referencia, efecto y auditoria:
  reason_code, note, actor, occurred_at, document_*, event_effects, append-only
No se borra ni se reescribe historia: 10 triggers lo impiden en stock_movements,
  domain_events y event_effects. Verificado sobre la copia productiva, no solo en pruebas
Correccion por compensacion: compensar() crea el inverso con compensates_id; indice unico
  parcial impide compensar dos veces
Dato no atribuible declarado como tal: PlanDeBackfill, y CostStatus del slice 1

EVENT SPINE V1
domain_events es una tabla de hechos, NO un event bus. Montar un bus hoy seria
  infraestructura antes que necesidad; lo que no se puede agregar despues sin migrar dos
  veces es la forma del hecho, y esa si esta
Campos: event_id, event_type, source, entity_type, entity_id, destination, actor,
  occurred_at, recorded_at, payload, processing_state, processed_at, failure_reason,
  idempotency_key unico
event_effects guarda que produjo cada hecho: se va del evento a sus movimientos y del
  movimiento a su evento. Sin eso "efectos derivados" seria una promesa
El ledger es su primer consumidor. PURCHASE_CONFIRMED y SALE_COMPLETED quedan contemplados
  y NO implementados: cuelgan de la misma tabla sin cambiarle la forma

EL LEDGER
quantity va CON SIGNO y el signo lo decide kind, atado por un CHECK. No hay columna de
  signo al lado del tipo: si la hubiera, nada impediria una venta que suma. Es la misma
  decision que tracks_stock en el slice 1, por el mismo motivo
10 tipos: 5 entradas y 5 salidas. Las dos transferencias quedan declaradas y sin usar
El slice 1 habia dejado un unico TRANSFERENCIA, que no puede decir de que lado del
  traslado esta el destino, y el signo se deriva de eso. Se abre en dos. Nada lo consumia
  todavia, asi que no queda una tercera forma de escribir lo mismo
Movimientos de Caja y de Stock quedan separados: una salida administrativa por rotura
  descuenta una unidad y no toca un guarani. Verificado mecanicamente que el ledger no
  nombra cash_entries, cash_days, cash_outflows ni cash_register

INGRESO ADMINISTRATIVO
Entra stock sin factura con motivo obligatorio de un catalogo cerrado y sembrado
  (STOCK_ENCONTRADO, CORRECCION_INVENTARIO, FUERA_DE_CIRCUITO, OTRO), observacion
  obligatoria en los cuatro, usuario, fecha y cantidad
NO crea compra ficticia: sin proveedor, sin documento, sin impacto en Caja. Hay prueba
Son dos catalogos y no uno con bandera: "roto" no puede ser el motivo por el que algo
  entro. Cual se usa se DERIVA del tipo; una columna que lo dijera podria contradecirlo

SALIDA ADMINISTRATIVA
Consume los 7 motivos que la 022 ya habia sembrado
Compra +1 seguido de SALIDA_ADMINISTRATIVA -1 / ROTO deja las dos filas. La compra
  original es imposible de tocar: el trigger lo impide

PRODUCCION INTERNA
INGRESO_PRODUCCION sin proveedor ni factura, con cantidad, fecha, responsable y
  observacion. Solo para articulos de naturaleza PRODUCCION_INTERNA: un armazon entraria
  por compra, y hay prueba de que se rechaza

POLITICA DE STOCK NEGATIVO
Bloqueado, y no solo en Python: el trigger stock_movements_sin_negativo vale para
  cualquier escritor. Verificado sobre la copia productiva
La excepcion es administrativa, explicita y auditada: negative_override solo en
  SALIDA_ADMINISTRATIVA y AJUSTE_NEGATIVO, y solo con motivo y observacion, por CHECK
Una VENTA nunca puede pedirla: para eso existe el bloqueo. Hay prueba
No hay negativo silencioso en ningun camino

CONCURRENCIA
BEGIN IMMEDIATE en toda escritura. Sin eso, dos cajas descontando la ultima unidad al
  mismo tiempo podrian leer stock 1 las dos
Prueba con dos hilos y una barrera: exactamente una de las dos ventas pasa y el stock
  queda en 0, nunca en -1

IDEMPOTENCIA
idempotency_key unico en la base. Registrar dos veces la misma clave devuelve el
  movimiento original y no descuenta de nuevo
Reprocesar un PURCHASE_CONFIRMED no duplica el stock y event_effects sigue con un efecto

MIGRACION 023
Aditiva ESTRICTA: solo CREATE TABLE/INDEX/VIEW/TRIGGER IF NOT EXISTS. NI UN SOLO
  ALTER TABLE, a diferencia de la 022. Ni siquiera modifica una tabla existente
Lo unico que escribe filas es la siembra de su propio catalogo nuevo. Hay una prueba que
  lo verifica leyendo el .sql
Cadena 22 -> 23

VERIFICACION SOBRE LA BASE PRODUCTIVA REAL
La 022 y la 023 se aplicaron sobre una COPIA de la base de la Optica. La base real se
  abrio en modo lectura y se copio con la API de backup de SQLite
0 tablas perdidas, 0 filas cambiadas en las 25 tablas preexistentes
sale_items: 10 filas intactas, las 10 con article_id NULL. Ningun articulo inventado
integrity_check ok, foreign_key_check 0, migraciones 21 -> 023,
  SUM(cash_entries.total) 6.400.000 sin cambios
stock_movements 0, domain_events 0: el ledger arranca vacio y no inventa historia
Append-only verificado sobre la copia con filas reales sembradas, no sobre tablas vacias:
  DELETE y UPDATE de stock_movements rechazados, DELETE y UPDATE de domain_events
  rechazados, VENTA que dejaria stock negativo rechazada
Base productiva real sin tocar: sha256 1c4fcc40...98ec antes y despues

PRUEBAS
Dirigidas primero: 49 pruebas escritas antes de la implementacion
Suite completa 763 passed + 4 subtests, exit 0 (714 baseline del slice 1 + 49 nuevas)
Log en QA_SUITE.txt

CONTRATO AJENO ACTUALIZADO CON SU INTENCION PRESERVADA
test_la_cadena_de_migraciones_llega_a_022 contaba las migraciones a mano: exactamente lo
  que el slice 1 le corrigio a otros seis contratos y reintrodujo en su propia prueba. Su
  intencion era "la 022 se aplico y no falta ninguna", no "nunca habra una 023". Ahora
  deriva la lista de tests/migration_chain.py y sigue exigiendo que la 022 este

LO QUE NO SE HIZO, A PROPOSITO
Compras, UI de stock, enlace venta -> articulo en la UI, trabajos operativos, FactuFacil,
  transferencias entre sucursales, notas de credito
Backfill historico: se planifica y NO se aplica. Falla cerrado
BC-Core y Telegram no se tocaron
NO promovido a main: agrega la 023 sobre la 022, y ninguna de las dos paso gate de
  empaquetado ni de instalacion. Mismo criterio que el slice 1
