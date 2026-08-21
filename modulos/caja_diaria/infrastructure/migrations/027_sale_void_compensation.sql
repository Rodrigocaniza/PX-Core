PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-VENTA-REVERSIBLE-Y-RELEASE-GATE-V1-006, slice 6.
--
-- Una venta que ya movio stock se puede anular. Hasta la 025 no se podia, y eso
-- era deliberado: media reversion improvisada es peor que ninguna. Lo que
-- faltaba no era el mecanismo -- compensar() existe desde la 023 -- sino el
-- circuito de negocio que lo dispara y la garantia de que dispararlo no
-- reescriba nada.
--
-- El principio es uno solo y esta migracion existe para hacerlo cumplir en la
-- base, no solo en la aplicacion:
--
--     el hecho original permanece
--     -> se registra un hecho compensatorio
--     -> que produce efectos compensatorios
--     -> y el estado derivado queda correcto
--
-- SALE_COMPLETED no se borra. Los movimientos VENTA no se borran. Las lineas no
-- se tocan. Lo que se agrega es un SALE_VOIDED y un AJUSTE_POSITIVO por cada
-- unidad que la venta original saco del deposito.
--
-- Migracion ADITIVA salvo por el reemplazo de un trigger de la 025, que pasa de
-- prohibir la anulacion a exigir que este compensada. Ninguna fila se modifica.

-- ==========================================================================
-- El motivo canonico
-- ==========================================================================
--
-- El catalogo de motivos se DERIVA del tipo de movimiento (trigger
-- stock_movements_motivo_valido, 023): todo lo que no es INGRESO_ADMINISTRATIVO
-- valida contra administrative_exit_reasons, y la compensacion de una VENTA es
-- un AJUSTE_POSITIVO. Por eso el motivo va aca y no en el otro catalogo:
-- ponerlo donde suena mejor lo haria invalido.
--
-- Exige observacion. La observacion es el motivo que la operadora escribio al
-- anular: sin el, la unidad vuelve al stock sin nada que lo explique.
INSERT OR IGNORE INTO administrative_exit_reasons(code, label, requires_note, position)
VALUES ('VENTA_ANULADA', 'Venta anulada', 1, 8);

-- Y es un motivo reservado: explica la devolucion de una venta compensada y
-- nada mas. Sin esto, cualquiera podria ingresar mercaderia a mano diciendo que
-- una venta se anulo, sin que ninguna venta se hubiera anulado.
CREATE TRIGGER IF NOT EXISTS stock_movements_venta_anulada_solo_compensa
BEFORE INSERT ON stock_movements
WHEN NEW.reason_code = 'VENTA_ANULADA'
 AND (NEW.kind <> 'AJUSTE_POSITIVO'
      OR NEW.compensates_id IS NULL
      OR NOT EXISTS(SELECT 1 FROM stock_movements
                    WHERE id = NEW.compensates_id AND kind = 'VENTA'))
BEGIN
    SELECT RAISE(ABORT, 'venta anulada solo explica la devolucion de una venta compensada');
END;

-- ==========================================================================
-- Que ventas ya fueron anuladas y compensadas
-- ==========================================================================
--
-- El espejo de sale_stock_integrations. Aquella dice que una venta salio del
-- deposito; esta dice que volvio. Es el registro durable de la idempotencia de
-- la anulacion: sin esto, reabrir la ventana o recuperarse de un corte
-- devolveria el stock dos veces.
CREATE TABLE IF NOT EXISTS sale_void_compensations (
    cash_entry_id TEXT PRIMARY KEY REFERENCES cash_entries(id),
    -- El hecho que se compensa y el hecho que compensa. Los dos quedan.
    sale_event_id TEXT NOT NULL REFERENCES domain_events(event_id),
    void_event_id TEXT NOT NULL REFERENCES domain_events(event_id),
    destination TEXT CHECK(destination IS NULL OR destination IN ('ASUNCION','PILAR')),
    reason_code TEXT NOT NULL REFERENCES administrative_exit_reasons(code),
    -- El motivo escrito por quien anulo. No puede estar vacio: una anulacion sin
    -- causa declarada es un agujero, igual que un movimiento administrativo sin
    -- motivo.
    note TEXT NOT NULL CHECK(length(trim(note)) > 0),
    movement_count INTEGER NOT NULL DEFAULT 0 CHECK(movement_count >= 0),
    voided_at TEXT NOT NULL,
    voided_by TEXT NOT NULL CHECK(length(trim(voided_by)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_sale_voids_evento
    ON sale_void_compensations(void_event_id);

-- --------------------------------------------------------------------------
-- Append-only, igual que todo lo demas de este circuito
-- --------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS sale_void_compensations_sin_update
BEFORE UPDATE ON sale_void_compensations
BEGIN
    SELECT RAISE(ABORT, 'una venta se anula una sola vez: el registro no se reescribe');
END;

CREATE TRIGGER IF NOT EXISTS sale_void_compensations_sin_delete
BEFORE DELETE ON sale_void_compensations
BEGIN
    SELECT RAISE(ABORT, 'borrar la anulacion dejaria el stock devuelto sin nada que lo explique');
END;

-- --------------------------------------------------------------------------
-- Solo se compensa lo que este circuito produjo
-- --------------------------------------------------------------------------
--
-- Una venta anterior a esta arquitectura -- las que hay hoy en produccion -- no
-- tiene integracion, no emitio SALE_COMPLETED y no saco nada del deposito.
-- Anotarle una anulacion compensatoria seria declarar la compensacion de un
-- efecto que nunca existio.
--
-- Una venta de puros servicios SI tiene integracion, con cero movimientos: su
-- hecho es durable aunque no produzca efectos, y su anulacion tambien. Devuelve
-- cero unidades, que es exactamente lo que saco.
CREATE TRIGGER IF NOT EXISTS sale_void_compensations_solo_ventas_integradas
BEFORE INSERT ON sale_void_compensations
WHEN NOT EXISTS(SELECT 1 FROM sale_stock_integrations
                WHERE cash_entry_id = NEW.cash_entry_id)
BEGIN
    SELECT RAISE(ABORT, 'esta venta nunca paso por el circuito de inventario: no hay nada que compensar');
END;

-- --------------------------------------------------------------------------
-- La compensacion es total o no es
-- --------------------------------------------------------------------------
--
-- Devolver algunas unidades y otras no dejaria el deposito en un estado que
-- nadie puede explicar y que nadie va a notar hasta que alguien busque
-- fisicamente algo que el sistema dice tener. Si falta una sola, la anulacion
-- entera se rechaza y la transaccion vuelve atras.
CREATE TRIGGER IF NOT EXISTS sale_void_compensations_sin_reversion_parcial
BEFORE INSERT ON sale_void_compensations
WHEN EXISTS(
    SELECT 1 FROM stock_movements m
     WHERE m.document_kind = 'VENTA'
       AND m.document_id = NEW.cash_entry_id
       AND m.kind = 'VENTA'
       AND NOT EXISTS(SELECT 1 FROM stock_movements c WHERE c.compensates_id = m.id))
BEGIN
    SELECT RAISE(ABORT, 'una anulacion parcial dejaria mercaderia afuera sin explicacion');
END;

-- --------------------------------------------------------------------------
-- Lo declarado tiene que ser lo ocurrido
-- --------------------------------------------------------------------------
--
-- movement_count no es un comentario: es una afirmacion sobre el ledger, y el
-- ledger es quien la confirma. Sin esto, una fila podria decir que devolvio
-- cinco unidades sin haber devuelto ninguna.
CREATE TRIGGER IF NOT EXISTS sale_void_compensations_cuenta_declarada_real
BEFORE INSERT ON sale_void_compensations
WHEN NEW.movement_count <> (
    SELECT COUNT(*) FROM stock_movements
     WHERE document_kind = 'VENTA'
       AND document_id = NEW.cash_entry_id
       AND compensates_id IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'la anulacion declara una cantidad de compensaciones que no registro');
END;

-- ==========================================================================
-- La anulacion deja de estar prohibida y pasa a estar condicionada
-- ==========================================================================
--
-- La 025 bloqueaba anular una venta integrada porque el circuito compensatorio
-- todavia no existia. Ahora existe, asi que la regla cambia de "no se puede" a
-- "no se puede sin haber devuelto el stock primero". El bloqueo sigue estando
-- para cualquier escritor que intente anular por su cuenta.
DROP TRIGGER IF EXISTS cash_entries_integrada_sin_anular;

CREATE TRIGGER cash_entries_integrada_sin_anular
BEFORE UPDATE ON cash_entries
WHEN NEW.status = 'VOIDED' AND OLD.status <> 'VOIDED'
 AND EXISTS(SELECT 1 FROM sale_stock_integrations WHERE cash_entry_id = OLD.id)
 AND NOT EXISTS(SELECT 1 FROM sale_void_compensations WHERE cash_entry_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'esta venta ya movio stock: anularla exige compensar la mercaderia en la misma operacion');
END;

-- Y no se revive. Sacar la venta del estado anulado despues de haber devuelto
-- la mercaderia descontaria el stock una segunda vez sin un hecho que lo
-- explique. Corregir una anulacion equivocada es una venta nueva, no un undo.
CREATE TRIGGER IF NOT EXISTS cash_entries_anulada_no_revive
BEFORE UPDATE ON cash_entries
WHEN OLD.status = 'VOIDED' AND NEW.status <> 'VOIDED'
 AND EXISTS(SELECT 1 FROM sale_void_compensations WHERE cash_entry_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'la anulacion ya devolvio la mercaderia: revivir la venta la sacaria de nuevo sin explicacion');
END;

-- ==========================================================================
-- Trazabilidad: de la unidad devuelta hasta la venta que la habia sacado
-- ==========================================================================
--
-- El tercer lado del circuito, despues de stock_origen_compra (024) y
-- stock_origen_venta (025). Con las tres, cualquier unidad que entro o salio
-- del deposito se explica con una consulta.
CREATE VIEW IF NOT EXISTS stock_origen_anulacion AS
SELECT
    c.id              AS movement_id,
    c.article_id      AS article_id,
    c.destination     AS destination,
    c.quantity        AS quantity,
    c.occurred_at     AS moved_at,
    c.actor           AS actor,
    c.reason_code     AS reason_code,
    c.note            AS note,
    m.id              AS compensated_movement_id,
    m.quantity        AS compensated_quantity,
    m.occurred_at     AS compensated_moved_at,
    e.id              AS cash_entry_id,
    e.description     AS entry_description,
    e.total           AS entry_total,
    e.status          AS entry_status,
    e.void_reason     AS void_reason,
    e.voided_at       AS voided_at,
    d.id              AS cash_day_id,
    d.business_date   AS business_date,
    d.unit            AS unit,
    v.voided_by       AS voided_by,
    v.void_event_id   AS void_event_id,
    v.sale_event_id   AS sale_event_id
FROM stock_movements c
JOIN stock_movements m ON m.id = c.compensates_id AND m.document_kind = 'VENTA'
JOIN cash_entries e    ON e.id = m.document_id
JOIN cash_days d       ON d.id = e.cash_day_id
LEFT JOIN sale_void_compensations v ON v.cash_entry_id = e.id;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('027', CURRENT_TIMESTAMP);
COMMIT;
