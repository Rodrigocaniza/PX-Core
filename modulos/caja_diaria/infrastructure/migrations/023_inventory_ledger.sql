PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-INVENTORY-LEDGER-V1-002, slice 2.
--
-- El stock deja de ser una cifra que alguien edita y pasa a ser la suma de los
-- movimientos que ocurrieron. De ahi sale todo lo demas: una compra vieja nunca
-- se modifica ni se borra para sacar una unidad rota, se registra la salida.
--
-- Migracion estrictamente ADITIVA. Ni siquiera modifica una tabla existente:
-- todo lo que crea es nuevo, asi que ninguna fila productiva puede perderse.
-- Lo unico que escribe es la siembra de su propio catalogo de motivos, y hay
-- una prueba que verifica esto leyendo el .sql.

-- ==========================================================================
-- Event Spine V1
-- ==========================================================================
--
-- La representacion durable de los hechos del negocio. No es un event bus: es
-- una tabla de hechos con identidad, idempotencia y estado de procesamiento,
-- que es lo que hace falta para que PURCHASE_CONFIRMED o SALE_COMPLETED tengan
-- consecuencias derivadas una sola vez y se pueda decir de donde salio cada
-- efecto.
--
-- `idempotency_key` es el que hace que reprocesar no duplique. `payload` es el
-- minimo para reconstruir el hecho, no una copia del sistema entero.
CREATE TABLE IF NOT EXISTS domain_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL CHECK(length(trim(event_type)) > 0),
    source TEXT NOT NULL CHECK(length(trim(source)) > 0),
    entity_type TEXT NOT NULL CHECK(length(trim(entity_type)) > 0),
    entity_id TEXT,
    -- Mismo vocabulario de sucursales que ya usan cash_register_branches,
    -- tracked_works y orders. No se crea un catalogo paralelo.
    destination TEXT CHECK(destination IS NULL OR destination IN ('ASUNCION','PILAR')),
    actor TEXT NOT NULL CHECK(length(trim(actor)) > 0),
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    processing_state TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK(processing_state IN ('PENDIENTE','PROCESADO','FALLIDO','NO_APLICA')),
    processed_at TEXT,
    failure_reason TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_domain_events_tipo
    ON domain_events(event_type, occurred_at);
CREATE INDEX IF NOT EXISTS idx_domain_events_entidad
    ON domain_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_domain_events_pendientes
    ON domain_events(processing_state, occurred_at);

-- Que produjo cada hecho. Sin esto, "efectos derivados" seria una promesa: con
-- esto se puede ir del evento al movimiento y del movimiento al evento.
CREATE TABLE IF NOT EXISTS event_effects (
    event_id TEXT NOT NULL REFERENCES domain_events(event_id),
    effect_kind TEXT NOT NULL,
    effect_table TEXT NOT NULL,
    effect_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (event_id, effect_kind, effect_id)
);
CREATE INDEX IF NOT EXISTS idx_event_effects_efecto
    ON event_effects(effect_table, effect_id);

-- ==========================================================================
-- Motivos de ingreso administrativo
-- ==========================================================================
--
-- Espeja administrative_exit_reasons, que la 022 sembro para el otro lado. Un
-- ingreso administrativo entra sin factura, asi que TODOS sus motivos exigen
-- observacion: si no, seria stock aparecido de la nada.
CREATE TABLE IF NOT EXISTS administrative_entry_reasons (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    requires_note INTEGER NOT NULL DEFAULT 1 CHECK(requires_note IN (0,1)),
    position INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);

INSERT OR IGNORE INTO administrative_entry_reasons(code, label, requires_note, position)
VALUES
    ('STOCK_ENCONTRADO',      'Stock encontrado',                              1, 1),
    ('CORRECCION_INVENTARIO', 'Corrección de inventario',                      1, 2),
    ('FUERA_DE_CIRCUITO',     'Mercadería ingresada fuera del circuito normal', 1, 3),
    ('OTRO',                  'Otro motivo justificado',                       1, 4);

-- ==========================================================================
-- El ledger
-- ==========================================================================
--
-- `quantity` va CON SIGNO y el signo lo decide `kind`. No hay una columna de
-- signo al lado del tipo: si la hubiera, nada impediria una venta que suma.
-- El CHECK ata las dos cosas, asi que el stock es literalmente SUM(quantity).
--
-- `reason_code` apunta a administrative_entry_reasons cuando el movimiento es
-- un INGRESO_ADMINISTRATIVO y a administrative_exit_reasons en los demas casos.
-- Es una sola columna con dos catalogos porque el catalogo se DERIVA del tipo;
-- una segunda columna que dijera cual es podria contradecirlo. El trigger
-- stock_movements_motivo_valido es el que lo verifica.
CREATE TABLE IF NOT EXISTS stock_movements (
    id TEXT PRIMARY KEY,
    -- El hecho del que salio. Nullable porque el ledger nace usable antes de
    -- que exista Compras, pero un movimiento sin evento igual lleva actor,
    -- fecha y clave: nunca es anonimo.
    event_id TEXT REFERENCES domain_events(event_id),
    article_id TEXT NOT NULL REFERENCES articles(id),
    destination TEXT NOT NULL CHECK(destination IN ('ASUNCION','PILAR')),
    kind TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    actor TEXT NOT NULL CHECK(length(trim(actor)) > 0),
    reason_code TEXT,
    note TEXT NOT NULL DEFAULT '',
    -- Referencia durable al documento de origen. Compras la va a llenar sin
    -- necesidad de otra migracion: la factura, su linea, el proveedor.
    supplier_id TEXT REFERENCES suppliers(id),
    document_kind TEXT,
    document_id TEXT,
    document_line_id TEXT,
    document_number TEXT,
    -- Una correccion no reescribe: apunta al movimiento que compensa.
    compensates_id TEXT REFERENCES stock_movements(id),
    negative_override INTEGER NOT NULL DEFAULT 0 CHECK(negative_override IN (0,1)),
    idempotency_key TEXT NOT NULL UNIQUE,

    -- El signo sale del tipo, y este CHECK es tambien la lista cerrada de tipos
    -- validos: no hay una segunda enumeracion que pueda quedar desfasada.
    CHECK(
        (kind IN ('INGRESO_COMPRA','INGRESO_PRODUCCION','INGRESO_ADMINISTRATIVO',
                  'AJUSTE_POSITIVO','TRANSFERENCIA_ENTRADA') AND quantity > 0)
        OR
        (kind IN ('VENTA','SALIDA_ADMINISTRATIVA','DEVOLUCION_PROVEEDOR',
                  'AJUSTE_NEGATIVO','TRANSFERENCIA_SALIDA') AND quantity < 0)
    ),
    -- Lo que sale o se ajusta sin venta tiene que decir por que.
    CHECK(
        kind NOT IN ('INGRESO_ADMINISTRATIVO','SALIDA_ADMINISTRATIVA',
                     'AJUSTE_POSITIVO','AJUSTE_NEGATIVO')
        OR reason_code IS NOT NULL
    ),
    -- La excepcion al stock negativo es administrativa, explicita y explicada.
    -- Una VENTA no puede pedirla: para eso existe el bloqueo.
    CHECK(
        negative_override = 0
        OR (kind IN ('SALIDA_ADMINISTRATIVA','AJUSTE_NEGATIVO')
            AND reason_code IS NOT NULL
            AND length(trim(note)) > 0)
    )
);
CREATE INDEX IF NOT EXISTS idx_stock_movements_articulo_destino
    ON stock_movements(article_id, destination);
CREATE INDEX IF NOT EXISTS idx_stock_movements_evento
    ON stock_movements(event_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_documento
    ON stock_movements(document_kind, document_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_fecha
    ON stock_movements(occurred_at);
-- Un movimiento se compensa una sola vez: dos compensaciones del mismo error
-- descontarian dos veces.
CREATE UNIQUE INDEX IF NOT EXISTS idx_stock_movements_compensacion_unica
    ON stock_movements(compensates_id) WHERE compensates_id IS NOT NULL;

-- El stock, derivado. No es una tabla porque no es un dato: es una cuenta.
CREATE VIEW IF NOT EXISTS stock_actual AS
SELECT article_id, destination, SUM(quantity) AS quantity
FROM stock_movements
GROUP BY article_id, destination;

-- --------------------------------------------------------------------------
-- Append-only. No hay DELETE economico ni reescritura silenciosa.
-- --------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS stock_movements_sin_update
BEFORE UPDATE ON stock_movements
BEGIN
    SELECT RAISE(ABORT, 'stock_movements es append-only: corregir con un movimiento compensatorio');
END;

CREATE TRIGGER IF NOT EXISTS stock_movements_sin_delete
BEFORE DELETE ON stock_movements
BEGIN
    SELECT RAISE(ABORT, 'stock_movements es append-only: corregir con un movimiento compensatorio');
END;

-- --------------------------------------------------------------------------
-- Que mueve stock lo decide la naturaleza del articulo, y solo ella.
-- Esta lista es la misma que _NATURALEZAS_QUE_MUEVEN_STOCK en el dominio; hay
-- una prueba que verifica que no se separen.
-- --------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS stock_movements_solo_articulos_stockeables
BEFORE INSERT ON stock_movements
WHEN (SELECT nature FROM articles WHERE id = NEW.article_id)
     NOT IN ('PRODUCTO_STOCKEABLE','PRODUCCION_INTERNA')
BEGIN
    SELECT RAISE(ABORT, 'el articulo no mueve stock por su naturaleza');
END;

-- --------------------------------------------------------------------------
-- Stock negativo: bloqueado, nunca silencioso.
-- --------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS stock_movements_sin_negativo
BEFORE INSERT ON stock_movements
WHEN NEW.quantity < 0 AND NEW.negative_override = 0
 AND COALESCE((SELECT SUM(quantity) FROM stock_movements
               WHERE article_id = NEW.article_id
                 AND destination = NEW.destination), 0) + NEW.quantity < 0
BEGIN
    SELECT RAISE(ABORT, 'stock insuficiente: el movimiento dejaria el stock en negativo');
END;

-- --------------------------------------------------------------------------
-- El motivo tiene que existir en el catalogo que corresponde al tipo.
-- --------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS stock_movements_motivo_valido
BEFORE INSERT ON stock_movements
WHEN NEW.reason_code IS NOT NULL
 AND ((NEW.kind = 'INGRESO_ADMINISTRATIVO'
       AND NOT EXISTS(SELECT 1 FROM administrative_entry_reasons
                      WHERE code = NEW.reason_code AND active = 1))
   OR (NEW.kind <> 'INGRESO_ADMINISTRATIVO'
       AND NOT EXISTS(SELECT 1 FROM administrative_exit_reasons
                      WHERE code = NEW.reason_code AND active = 1)))
BEGIN
    SELECT RAISE(ABORT, 'motivo desconocido para este tipo de movimiento');
END;

CREATE TRIGGER IF NOT EXISTS stock_movements_observacion_requerida
BEFORE INSERT ON stock_movements
WHEN NEW.reason_code IS NOT NULL AND length(trim(NEW.note)) = 0
 AND ((NEW.kind = 'INGRESO_ADMINISTRATIVO'
       AND EXISTS(SELECT 1 FROM administrative_entry_reasons
                  WHERE code = NEW.reason_code AND requires_note = 1))
   OR (NEW.kind <> 'INGRESO_ADMINISTRATIVO'
       AND EXISTS(SELECT 1 FROM administrative_exit_reasons
                  WHERE code = NEW.reason_code AND requires_note = 1)))
BEGIN
    SELECT RAISE(ABORT, 'este motivo exige observacion');
END;

-- --------------------------------------------------------------------------
-- Los hechos tampoco se reescriben. Lo unico que avanza es su procesamiento.
-- --------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS domain_events_inmutable
BEFORE UPDATE ON domain_events
WHEN NEW.event_type <> OLD.event_type
  OR NEW.source <> OLD.source
  OR NEW.entity_type <> OLD.entity_type
  OR NEW.entity_id IS NOT OLD.entity_id
  OR NEW.destination IS NOT OLD.destination
  OR NEW.actor <> OLD.actor
  OR NEW.occurred_at <> OLD.occurred_at
  OR NEW.payload <> OLD.payload
  OR NEW.idempotency_key <> OLD.idempotency_key
BEGIN
    SELECT RAISE(ABORT, 'un hecho registrado no se reescribe: solo avanza su estado de procesamiento');
END;

CREATE TRIGGER IF NOT EXISTS domain_events_sin_delete
BEFORE DELETE ON domain_events
BEGIN
    SELECT RAISE(ABORT, 'un hecho registrado no se borra');
END;

CREATE TRIGGER IF NOT EXISTS event_effects_sin_update
BEFORE UPDATE ON event_effects
BEGIN
    SELECT RAISE(ABORT, 'el efecto de un hecho no se reescribe');
END;

CREATE TRIGGER IF NOT EXISTS event_effects_sin_delete
BEFORE DELETE ON event_effects
BEGIN
    SELECT RAISE(ABORT, 'el efecto de un hecho no se borra');
END;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('023', CURRENT_TIMESTAMP);
COMMIT;
