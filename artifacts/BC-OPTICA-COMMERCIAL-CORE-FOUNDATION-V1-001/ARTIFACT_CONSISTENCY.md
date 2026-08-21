PASS
Mision BC-OPTICA-COMMERCIAL-CORE-FOUNDATION-V1-001, slice 1 de 6, sobre origin/main 7db56a0
  (BC Caja 1.0.0-rc.31, instalada y validada en la Optica)
Fuentes verificadas 12 sha256 ok
Contratos ajenos actualizados 6 sha256 ok
Convencion de hash: sha256 con saltos normalizados a LF, igual que la mision anterior

ALCANCE SUBDIVIDIDO
La foundation completa era demasiado grande para una mision. Se partio en 6 slices y se
  ejecuta solo el 1, el catalogo canonico, que es el que desbloquea a los otros cinco.
  Los slices 2-6 quedan disenados en IMPLEMENTATION_PACKET.md, con su vocabulario ya
  fijado en el dominio de este slice, para no migrar dos veces

MODELO
Cuatro naturalezas cerradas en CHECK de base y Enum de dominio: PRODUCTO_STOCKEABLE,
  SERVICIO_NO_STOCKEABLE, TRABAJO_BAJO_PEDIDO, PRODUCCION_INTERNA
tracks_stock NO es columna: se deriva de la naturaleza. Pasarlo al constructor es TypeError
  y hay prueba que lo fija. Una columna libre permitiria un armazon que no descuenta y una
  compostura que si
Composturas como SERVICIO_NO_STOCKEABLE y cristales como TRABAJO_BAJO_PEDIDO: ninguno
  genera unidades de inventario, asi que no hay productos, facturas ni clientes ficticios
CostStatus.PENDIENTE_DE_CONCILIACION definido: cuando no hay dato real de costo se declara
  que falta conciliar. No se inventa costo
CONSUMIDOR_FINAL es constante de dominio, no una fila: una venta sin cliente identificado
  normaliza a esa constante y no se crea un cliente ficticio por caso. Hay prueba de que
  no existe tabla de clientes

REUTILIZACION VERIFICADA, NO DUPLICACION
laboratories (016) sigue siendo el catalogo canonico; suppliers.laboratory_id lo referencia
Destinos ASUNCION/PILAR reusan el vocabulario de cash_register_branches,
  tracked_works.origin_branch y orders.branch. Destination vive en el dominio SIN tabla
  nueva, y hay prueba de que no se crearon branches/sucursales/commercial_destinations

MIGRACION 022
Estrictamente aditiva: CREATE TABLE/INDEX IF NOT EXISTS y un solo ALTER TABLE ADD COLUMN
  nullable. No altera ni reconstruye ninguna tabla existente
Tablas nuevas: article_categories, brands, suppliers, articles,
  administrative_exit_reasons (7 motivos sembrados: ROTO, RAYADO, PERDIDA, DETERIORO,
  USO_INTERNO, ERROR_INVENTARIO, OTRO)
Columna nueva: sale_items.article_id, nullable, REFERENCES articles(id)
Cadena 21 -> 22. Es un cambio de esquema real y se declara como tal

VERIFICACION SOBRE LA BASE PRODUCTIVA REAL
La migracion se aplico sobre una COPIA de la base de la Optica, no sobre una fixture y
  nunca sobre la base real. Evidencia en MIGRATION_ON_PRODUCTION_COPY.txt
0 tablas perdidas, 0 filas perdidas en las 24 tablas preexistentes
sale_items: 10 filas intactas y las 10 con article_id NULL. No se invento ningun articulo
  para una venta ya cargada a mano
integrity_check ok, foreign_key_check 0, migraciones 21 -> 22, SUM(cash_entries.total)
  6.400.000 sin cambios
Base productiva real sin tocar: sha256 1c4fcc40...98ec antes y despues

PRUEBAS
Dirigidas primero: 32 pruebas escritas antes de la implementacion
Suite completa 714 passed + 4 subtests, exit 0 (682 baseline + 32 nuevas). Log en QA_SUITE.txt
Los 2 fallos historicos de gestion_central no aparecieron

CONTRATOS AJENOS ACTUALIZADOS CON SU INTENCION PRESERVADA
Seis contratos fijaban la cadena en 21 repitiendo la lista de versiones a mano. Su
  intencion era "este slice no agrega migraciones", no "nunca habra una 022"
test_rc11_compact_tables y test_rc15_apertura_caja cuentan ahora la linea de Caja hasta
  021, que es lo que realmente afirmaban sobre RC27 y sobre Apertura
test_sqlite_repository, test_sqlite_save_bugfix, test_recovery_drill y
  test_rc13_admin_counts_email derivan la lista de tests/migration_chain.py, asi el
  proximo slice no rompe cinco pruebas ajenas. La prueba no se vuelve vacia: verifica que
  la base registre TODAS las migraciones del directorio, en orden
test_recovery_drill gana una afirmacion nueva: tras migrar, las lineas de venta historicas
  quedan con article_id NULL

LO QUE NO SE HIZO, A PROPOSITO
Ledger de inventario, compras centralizadas, enlace venta->articulo en la UI, cristales y
  composturas operativos, bandeja FactuFacil, y carga masiva de la base real de articulos
FactuFacil no se toco: hoy no existe en CajaDiaria.py y hay un contrato que lo verifica
UI sin cambios. Reglas economicas de Caja sin cambios
NO promovido a main: agrega la 022 y todavia no hay gate de empaquetado ni de instalacion.
  main es lo que se empaqueta, asi que promoverlo ahora arrastraria un cambio de esquema
  que nunca paso por un gate. Queda en su rama, pusheada
