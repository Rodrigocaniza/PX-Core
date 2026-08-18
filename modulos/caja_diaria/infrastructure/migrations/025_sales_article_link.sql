PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-SALES-ARTICLE-LINK-V1-004, slice 4.
--
-- Cierra el circuito: compra -> INGRESO_COMPRA -> stock -> venta ->
-- SALE_COMPLETED -> VENTA -> stock restante.
--
-- Sin reescribir el subsistema de ventas. La linea de venta sigue siendo la
-- misma fila de sale_items que la Optica usa desde la 006, con su armazon y su
-- cristal; lo unico que se agrega es el vinculo con el articulo canonico y el
-- registro de que esa venta ya movio inventario.

-- ==========================================================================
-- El vinculo
-- ==========================================================================
--
-- La linea de la Optica tiene DOS componentes y siempre los tuvo: frame_price
-- es el articulo fisico (armazon, cadenilla, liquido, o un servicio con precio)
-- y lens_price es el trabajo de laboratorio. La 022 ya agrego article_id, que
-- es el articulo del primer componente; falta el del segundo.
--
-- Partir la venta en dos filas para que cada una tuviera un solo articulo
-- habria sido reescribir el subsistema de ventas, que es justo lo que este
-- slice no hace. La forma de la linea es la que la operacion real tiene.
ALTER TABLE sale_items ADD COLUMN lens_article_id TEXT REFERENCES articles(id);
CREATE INDEX IF NOT EXISTS idx_sale_items_lens_article ON sale_items(lens_article_id);

-- ==========================================================================
-- Que ventas ya movieron inventario
-- ==========================================================================
--
-- Es el registro durable de la idempotencia: sin esto, reabrir la ventana o
-- recuperarse de un corte volveria a descontar. Una bandera en memoria no
-- sobrevive a ninguna de las dos cosas.
--
-- Tambien es lo que define el limite de la edicion: una venta que ya saco
-- mercaderia del deposito tiene sus lineas congeladas.
CREATE TABLE IF NOT EXISTS sale_stock_integrations (
    cash_entry_id TEXT PRIMARY KEY REFERENCES cash_entries(id),
    event_id TEXT NOT NULL REFERENCES domain_events(event_id),
    destination TEXT CHECK(destination IS NULL OR destination IN ('ASUNCION','PILAR')),
    movement_count INTEGER NOT NULL DEFAULT 0 CHECK(movement_count >= 0),
    integrated_at TEXT NOT NULL,
    integrated_by TEXT NOT NULL CHECK(length(trim(integrated_by)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_sale_integrations_evento
    ON sale_stock_integrations(event_id);

CREATE TRIGGER IF NOT EXISTS sale_stock_integrations_sin_update
BEFORE UPDATE ON sale_stock_integrations
BEGIN
    SELECT RAISE(ABORT, 'una venta se integra una sola vez: el registro no se reescribe');
END;

CREATE TRIGGER IF NOT EXISTS sale_stock_integrations_sin_delete
BEFORE DELETE ON sale_stock_integrations
BEGIN
    SELECT RAISE(ABORT, 'borrar la integracion dejaria el stock afuera sin nada que lo explique');
END;

-- --------------------------------------------------------------------------
-- Las lineas de una venta que ya movio stock son historia
-- --------------------------------------------------------------------------
--
-- El guardado de Caja borra y reinserta las lineas de cada entrada en cada
-- save. Eso esta bien para una venta que todavia no movio nada, y es
-- inaceptable para una que si: la unidad ya salio del deposito y el movimiento
-- que la saco apunta a esta linea.
--
-- La entrada NO queda congelada entera. Telefono, observaciones, cliente y
-- todo lo que no cambia la causalidad del inventario se siguen editando: son
-- columnas de cash_entries, no de sale_items.
CREATE TRIGGER IF NOT EXISTS sale_items_de_venta_integrada_sin_delete
BEFORE DELETE ON sale_items
WHEN EXISTS(SELECT 1 FROM sale_stock_integrations
            WHERE cash_entry_id = OLD.cash_entry_id)
BEGIN
    SELECT RAISE(ABORT, 'esta venta ya movio stock: su linea no se borra, se compensa');
END;

CREATE TRIGGER IF NOT EXISTS sale_items_de_venta_integrada_sin_update
BEFORE UPDATE ON sale_items
WHEN EXISTS(SELECT 1 FROM sale_stock_integrations
            WHERE cash_entry_id = OLD.cash_entry_id)
BEGIN
    SELECT RAISE(ABORT, 'esta venta ya movio stock: su linea no se reescribe');
END;

CREATE TRIGGER IF NOT EXISTS sale_items_de_venta_integrada_sin_insert
BEFORE INSERT ON sale_items
WHEN EXISTS(SELECT 1 FROM sale_stock_integrations
            WHERE cash_entry_id = NEW.cash_entry_id)
BEGIN
    SELECT RAISE(ABORT, 'no se agregan lineas a una venta que ya movio stock');
END;

-- Anular la venta la haria desaparecer del dia y dejaria la mercaderia afuera
-- sin nada que la explique. La reversion correcta es un movimiento
-- compensatorio, que existe desde la 023 pero cuyo circuito de negocio todavia
-- no esta armado; hasta entonces esto se bloquea en vez de improvisarse.
CREATE TRIGGER IF NOT EXISTS cash_entries_integrada_sin_anular
BEFORE UPDATE ON cash_entries
WHEN NEW.status = 'VOIDED' AND OLD.status <> 'VOIDED'
 AND EXISTS(SELECT 1 FROM sale_stock_integrations WHERE cash_entry_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'esta venta ya movio stock: anularla dejaria la mercaderia afuera sin explicacion');
END;

-- ==========================================================================
-- Trazabilidad: de una salida de stock hasta la venta que la produjo
-- ==========================================================================
--
-- El espejo de stock_origen_compra, que la 024 dejo para el otro lado del
-- circuito. Entre las dos, cualquier unidad que entro o salio del deposito se
-- explica con una consulta.
CREATE VIEW IF NOT EXISTS stock_origen_venta AS
SELECT
    m.id              AS movement_id,
    m.article_id      AS article_id,
    m.destination     AS destination,
    m.quantity        AS quantity,
    m.occurred_at     AS moved_at,
    m.actor           AS actor,
    e.id              AS cash_entry_id,
    e.description     AS entry_description,
    e.saleswoman      AS saleswoman,
    e.total           AS entry_total,
    e.status          AS entry_status,
    d.id              AS cash_day_id,
    d.business_date   AS business_date,
    d.unit            AS unit,
    i.id              AS sale_item_id,
    i.position        AS line_position,
    i.description     AS line_description,
    i.frame_price     AS frame_price,
    i.lens_price      AS lens_price,
    g.integrated_at   AS integrated_at,
    g.integrated_by   AS integrated_by,
    ev.event_id       AS event_id,
    ev.event_type     AS event_type,
    ev.occurred_at    AS event_at
FROM stock_movements m
JOIN cash_entries e ON e.id = m.document_id AND m.document_kind = 'VENTA'
JOIN cash_days d    ON d.id = e.cash_day_id
JOIN sale_items i   ON i.id = m.document_line_id
LEFT JOIN sale_stock_integrations g ON g.cash_entry_id = e.id
LEFT JOIN domain_events ev ON ev.event_id = m.event_id;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('025', CURRENT_TIMESTAMP);
COMMIT;
