PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-PURCHASES-PROVIDERS-V1-003, slice 3.
--
-- La factura del proveedor se registra UNA sola vez, a nivel empresa, y el
-- stock de las dos sucursales sale de ahi. No hay una carga por sucursal: eso
-- seria la misma factura existiendo dos veces, con dos verdades posibles.
--
-- Migracion aditiva. Lo unico que toca de lo que ya existia son tres columnas
-- nullables sobre suppliers, que la 022 creo y que en produccion todavia no
-- tiene ni una fila. No reconstruye ni reescribe ninguna tabla.

-- ==========================================================================
-- Proveedores: se EXTIENDE el catalogo de la 022, no se crea otro
-- ==========================================================================
--
-- suppliers ya tiene identidad, nombre, clase, documento, telefono, vinculo
-- con el laboratorio canonico, activo y auditoria. Le faltaban los datos de
-- contacto que la carga de una factura real pide. Crear una tabla "proveedores"
-- al lado seria exactamente el sistema paralelo que se viene evitando.
ALTER TABLE suppliers ADD COLUMN address TEXT NOT NULL DEFAULT '';
ALTER TABLE suppliers ADD COLUMN email TEXT NOT NULL DEFAULT '';
ALTER TABLE suppliers ADD COLUMN contact_name TEXT NOT NULL DEFAULT '';

-- Cuando hay identidad fiscal fiable, el duplicado se bloquea. Cuando no la
-- hay, no se inventa una: el indice es parcial a proposito, asi que dos
-- proveedores sin RUC conviven sin problema.
CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_documento_unico
    ON suppliers(document) WHERE trim(document) <> '';

-- ==========================================================================
-- La compra: el hecho economico
-- ==========================================================================
--
-- `document_total` es lo que dice el papel. La suma de las lineas es derivada.
-- Se guardan los dos y se contrastan al confirmar: que no coincidan es un hecho
-- que hay que mostrar, no uno que el sistema deba arreglar por su cuenta.
--
-- `due_date` es derivado de la fecha y el plazo. Se materializa para poder
-- indexarlo y consultarlo, y un trigger verifica que no contradiga su origen.
--
-- No hay estado ANULADA. Notas de credito y devoluciones exceden este slice, y
-- media anulacion improvisada seria peor que ninguna: lo que se hace es impedir
-- la mutacion destructiva y dejar el boundary explicito.
CREATE TABLE IF NOT EXISTS purchases (
    id TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL REFERENCES suppliers(id),
    document_date TEXT NOT NULL,
    document_number TEXT NOT NULL CHECK(length(trim(document_number)) > 0),
    stamped_number TEXT NOT NULL DEFAULT '',
    condition TEXT NOT NULL CHECK(condition IN ('CONTADO','CREDITO')),
    receipt_reference TEXT NOT NULL DEFAULT '',
    credit_days INTEGER CHECK(credit_days IS NULL OR credit_days >= 0),
    due_date TEXT,
    document_total INTEGER NOT NULL CHECK(document_total >= 0),
    status TEXT NOT NULL DEFAULT 'BORRADOR' CHECK(status IN ('BORRADOR','CONFIRMADA')),
    notes TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL CHECK(length(trim(created_by)) > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmed_by TEXT,
    confirmed_at TEXT,
    event_id TEXT REFERENCES domain_events(event_id),

    -- El plazo y el vencimiento existen si y solo si hay credito.
    CHECK(
        (condition = 'CREDITO' AND credit_days IS NOT NULL AND due_date IS NOT NULL)
        OR
        (condition = 'CONTADO' AND credit_days IS NULL AND due_date IS NULL)
    ),
    -- Confirmada implica saber quien, cuando y con que hecho. Sin esas tres
    -- cosas el stock derivado no tendria de donde colgar.
    CHECK(
        (status = 'CONFIRMADA' AND confirmed_by IS NOT NULL
         AND confirmed_at IS NOT NULL AND event_id IS NOT NULL)
        OR
        (status = 'BORRADOR' AND confirmed_by IS NULL
         AND confirmed_at IS NULL AND event_id IS NULL)
    )
);
-- Una factura real del mismo proveedor existe una sola vez.
CREATE UNIQUE INDEX IF NOT EXISTS idx_purchases_documento_unico
    ON purchases(supplier_id, document_number);
CREATE INDEX IF NOT EXISTS idx_purchases_proveedor ON purchases(supplier_id, document_date);
CREATE INDEX IF NOT EXISTS idx_purchases_estado ON purchases(status, document_date);
CREATE INDEX IF NOT EXISTS idx_purchases_vencimiento ON purchases(due_date);
CREATE INDEX IF NOT EXISTS idx_purchases_evento ON purchases(event_id);

-- ==========================================================================
-- Lineas
-- ==========================================================================
--
-- No hay columna que diga si la linea mueve stock. Se deriva de la naturaleza
-- del articulo, igual que en el slice 1, y por el mismo motivo: una bandera
-- propia permitiria una linea de armazones que no ingresa y una de composturas
-- que si.
--
-- Tampoco hay columna de total de linea: es cantidad por costo unitario.
CREATE TABLE IF NOT EXISTS purchase_lines (
    id TEXT PRIMARY KEY,
    purchase_id TEXT NOT NULL REFERENCES purchases(id),
    line_number INTEGER NOT NULL CHECK(line_number > 0),
    article_id TEXT NOT NULL REFERENCES articles(id),
    description TEXT NOT NULL DEFAULT '',
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_cost INTEGER NOT NULL CHECK(unit_cost >= 0),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(purchase_id, line_number)
);
CREATE INDEX IF NOT EXISTS idx_purchase_lines_compra ON purchase_lines(purchase_id);
CREATE INDEX IF NOT EXISTS idx_purchase_lines_articulo ON purchase_lines(article_id);

-- ==========================================================================
-- Distribucion fisica
-- ==========================================================================
--
-- Cuantas unidades de esta linea van a cada sucursal. Solo para lo que mueve
-- stock: repartir un cristal recetado o una compostura no significa nada.
CREATE TABLE IF NOT EXISTS purchase_line_distributions (
    id TEXT PRIMARY KEY,
    purchase_line_id TEXT NOT NULL REFERENCES purchase_lines(id),
    destination TEXT NOT NULL CHECK(destination IN ('ASUNCION','PILAR')),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    created_at TEXT NOT NULL,
    UNIQUE(purchase_line_id, destination)
);
CREATE INDEX IF NOT EXISTS idx_purchase_distribuciones_linea
    ON purchase_line_distributions(purchase_line_id);

-- --------------------------------------------------------------------------
-- El vencimiento no puede contradecir a su origen
-- --------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS purchases_vencimiento_derivado
BEFORE INSERT ON purchases
WHEN NEW.condition = 'CREDITO'
 AND NEW.due_date <> date(NEW.document_date, '+' || NEW.credit_days || ' days')
BEGIN
    SELECT RAISE(ABORT, 'el vencimiento se deriva de la fecha del documento y el plazo');
END;

-- --------------------------------------------------------------------------
-- Solo se distribuye lo que mueve stock, y nunca mas de lo comprado.
-- La lista de naturalezas es la misma del dominio y la del ledger; hay una
-- prueba que verifica que no se separen.
-- --------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS purchase_line_distributions_solo_stockeables
BEFORE INSERT ON purchase_line_distributions
WHEN (SELECT a.nature FROM purchase_lines l JOIN articles a ON a.id = l.article_id
      WHERE l.id = NEW.purchase_line_id)
     NOT IN ('PRODUCTO_STOCKEABLE','PRODUCCION_INTERNA')
BEGIN
    SELECT RAISE(ABORT, 'la linea no mueve stock por la naturaleza del articulo: no se distribuye');
END;

CREATE TRIGGER IF NOT EXISTS purchase_line_distributions_no_excede
BEFORE INSERT ON purchase_line_distributions
WHEN COALESCE((SELECT SUM(quantity) FROM purchase_line_distributions
               WHERE purchase_line_id = NEW.purchase_line_id), 0) + NEW.quantity
     > (SELECT quantity FROM purchase_lines WHERE id = NEW.purchase_line_id)
BEGIN
    SELECT RAISE(ABORT, 'la distribucion no puede superar la cantidad comprada');
END;

-- --------------------------------------------------------------------------
-- Confirmada es historia. No se reescribe ni desaparece.
--
-- La transicion BORRADOR -> CONFIRMADA si pasa, porque el trigger mira el
-- estado VIEJO. Lo que queda prohibido es tocar lo que ya se confirmo.
-- --------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS purchases_confirmada_inmutable
BEFORE UPDATE ON purchases
WHEN OLD.status = 'CONFIRMADA'
BEGIN
    SELECT RAISE(ABORT, 'una compra confirmada no se reescribe: la correccion es un hecho nuevo, no una edicion');
END;

CREATE TRIGGER IF NOT EXISTS purchases_confirmada_sin_delete
BEFORE DELETE ON purchases
WHEN OLD.status = 'CONFIRMADA'
BEGIN
    SELECT RAISE(ABORT, 'una compra confirmada no se borra: el stock que genero quedaria sin origen');
END;

CREATE TRIGGER IF NOT EXISTS purchase_lines_de_confirmada_sin_insert
BEFORE INSERT ON purchase_lines
WHEN (SELECT status FROM purchases WHERE id = NEW.purchase_id) = 'CONFIRMADA'
BEGIN
    SELECT RAISE(ABORT, 'no se agregan lineas a una compra confirmada');
END;

CREATE TRIGGER IF NOT EXISTS purchase_lines_de_confirmada_inmutables
BEFORE UPDATE ON purchase_lines
WHEN (SELECT status FROM purchases WHERE id = OLD.purchase_id) = 'CONFIRMADA'
BEGIN
    SELECT RAISE(ABORT, 'la linea de una compra confirmada no se reescribe');
END;

CREATE TRIGGER IF NOT EXISTS purchase_lines_de_confirmada_sin_delete
BEFORE DELETE ON purchase_lines
WHEN (SELECT status FROM purchases WHERE id = OLD.purchase_id) = 'CONFIRMADA'
BEGIN
    SELECT RAISE(ABORT, 'la linea de una compra confirmada no se borra');
END;

CREATE TRIGGER IF NOT EXISTS purchase_distribuciones_de_confirmada_sin_insert
BEFORE INSERT ON purchase_line_distributions
WHEN (SELECT p.status FROM purchase_lines l JOIN purchases p ON p.id = l.purchase_id
      WHERE l.id = NEW.purchase_line_id) = 'CONFIRMADA'
BEGIN
    SELECT RAISE(ABORT, 'no se reparte de nuevo una compra confirmada');
END;

CREATE TRIGGER IF NOT EXISTS purchase_distribuciones_de_confirmada_inmutables
BEFORE UPDATE ON purchase_line_distributions
WHEN (SELECT p.status FROM purchase_lines l JOIN purchases p ON p.id = l.purchase_id
      WHERE l.id = OLD.purchase_line_id) = 'CONFIRMADA'
BEGIN
    SELECT RAISE(ABORT, 'el reparto de una compra confirmada no se reescribe');
END;

CREATE TRIGGER IF NOT EXISTS purchase_distribuciones_de_confirmada_sin_delete
BEFORE DELETE ON purchase_line_distributions
WHEN (SELECT p.status FROM purchase_lines l JOIN purchases p ON p.id = l.purchase_id
      WHERE l.id = OLD.purchase_line_id) = 'CONFIRMADA'
BEGIN
    SELECT RAISE(ABORT, 'el reparto de una compra confirmada no se borra');
END;

-- ==========================================================================
-- Trazabilidad: de una unidad en el deposito hasta la factura que la trajo
-- ==========================================================================
--
-- La pregunta "de donde salio este stock" tiene que poder contestarse con una
-- consulta, no leyendo codigo. El movimiento ya guarda la referencia durable;
-- esta vista la resuelve completa.
CREATE VIEW IF NOT EXISTS stock_origen_compra AS
SELECT
    m.id                AS movement_id,
    m.article_id        AS article_id,
    m.destination       AS destination,
    m.quantity          AS quantity,
    m.occurred_at       AS moved_at,
    p.id                AS purchase_id,
    p.document_number   AS document_number,
    p.document_date     AS document_date,
    p.stamped_number    AS stamped_number,
    p.condition         AS condition,
    p.due_date          AS due_date,
    p.confirmed_by      AS confirmed_by,
    p.confirmed_at      AS confirmed_at,
    l.id                AS purchase_line_id,
    l.line_number       AS line_number,
    l.unit_cost         AS unit_cost,
    s.id                AS supplier_id,
    s.name              AS supplier_name,
    s.document          AS supplier_document,
    e.event_id          AS event_id,
    e.event_type        AS event_type,
    e.occurred_at       AS event_at
FROM stock_movements m
JOIN purchases p       ON p.id = m.document_id AND m.document_kind = 'COMPRA'
JOIN purchase_lines l  ON l.id = m.document_line_id
JOIN suppliers s       ON s.id = p.supplier_id
LEFT JOIN domain_events e ON e.event_id = m.event_id;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('024', CURRENT_TIMESTAMP);
COMMIT;
