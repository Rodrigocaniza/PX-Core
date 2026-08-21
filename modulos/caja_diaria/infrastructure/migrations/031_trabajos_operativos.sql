PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-TRABAJOS-OPERATIVOS-V1-020, slice 20.
--
-- Lo que la optica hace todos los dias y no estaba en ningun lado: una senora
-- deja los lentes para que le pongan un tornillo, y hasta hoy eso vivia en un
-- cuaderno. No es una venta, no es un pedido al laboratorio, y sobre todo no es
-- una unidad de inventario.
--
-- ==========================================================================
-- Por que una entidad nueva y no tracked_works
-- ==========================================================================
--
-- La 016 ya sigue trabajos, pero sigue OTRO trabajo: el circuito fisico
-- Pilar -> Asuncion -> laboratorio -> Pilar. Sus siete estados son lugares
-- donde esta el sobre, y su CHECK es cerrado. Una compostura que se arregla en
-- el mostrador de Asuncion no esta en ninguno de esos siete lugares.
--
-- Meterla ahi obligaria a abrir ese CHECK y a que una misma tabla respondiera
-- dos preguntas distintas -donde esta fisicamente, y en que etapa del taller
-- esta-, que es exactamente como se rompe un modelo. Son dos circuitos, y el
-- dia que un trabajo de taller tenga que ir al laboratorio, order_id y
-- cash_entry_id ya son la costura para enlazarlos sin fundirlos.
--
-- ==========================================================================
-- Que NO se toca
-- ==========================================================================
--
-- Ninguna venta, ningun pago, ninguna caja, ningun arqueo, ningun movimiento,
-- ningun articulo y ningun stock_movements. Esta migracion es estrictamente
-- ADITIVA: no altera una sola tabla existente y no escribe una sola fila fuera
-- de las que crea. Lo unico que siembra es su propio catalogo de tipos.
--
-- La naturaleza de los articulos tampoco se toca. Hilo, Tornillo, Plaqueta y
-- Par de patillas ya fueron corregidos a SERVICIO_NO_STOCKEABLE por la V1-010,
-- con su evidencia y su cierre. Volver a corregirlos aqui seria reescribir una
-- decision que ya esta tomada y auditada. Lo que este slice agrega es la prueba
-- de que sigue siendo cierto.

-- ==========================================================================
-- Tipos de trabajo
-- ==========================================================================
--
-- La columna stockeable existe y esta clavada en 0 por CHECK. Parece una
-- columna inutil -si siempre vale 0, para que guardarla- y es justo al reves:
-- es el invariante escrito en el esquema. El dia que alguien intente dar de
-- alta un tipo de trabajo que mueva stock, la base lo rechaza sola, sin
-- depender de que el codigo se acuerde. Un hilo y un tornillo entran aca, y por
-- eso mismo no pueden volver a ser inventario por la puerta de atras.
CREATE TABLE IF NOT EXISTS service_job_types (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL CHECK(length(trim(label)) > 0),
    position INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    stockeable INTEGER NOT NULL DEFAULT 0 CHECK(stockeable = 0)
);

INSERT OR IGNORE INTO service_job_types(code, label, position) VALUES
    ('COMPOSTURA', 'Compostura',        1),
    ('HILO',       'Hilo',              2),
    ('TORNILLO',   'Tornillo',          3),
    ('PLAQUETA',   'Plaqueta',          4),
    ('PATILLA',    'Patilla',           5),
    ('AJUSTE',     'Ajuste',            6),
    ('ARMADO',     'Armado / montaje',  7),
    ('OTRO',       'Otro trabajo',      8);

-- ==========================================================================
-- El trabajo
-- ==========================================================================
--
-- branch la decide la caja, no la persona: es el mismo vocabulario de
-- cash_register_branches, tracked_works y domain_events. No se crea un catalogo
-- paralelo de sucursales.
--
-- responsible es texto y no una foreign key, igual que cash_entries.saleswoman
-- y por la misma razon: si manana se corrige como se escribe el nombre de una
-- persona, los trabajos de agosto no se reescriben. responsible_user_id guarda
-- la identidad para lo unico que si necesita identidad -la comision- y es
-- nullable porque un trabajo puede recibirse antes de saber quien lo va a hacer.
--
-- El estado operativo y el estado economico son dos cosas y estan separadas a
-- proposito: status dice donde esta el trabajo, cash_entry_id dice si se cobro.
-- Una compostura puede estar LISTO y sin cobrar, y una cobrada puede seguir sin
-- entregar. Un solo campo no podria decir las dos cosas.
CREATE TABLE IF NOT EXISTS service_jobs (
    id TEXT PRIMARY KEY,
    -- Numero legible para el mostrador: es lo que se le canta al cliente.
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE,
    received_at TEXT NOT NULL,
    branch TEXT NOT NULL CHECK(branch IN ('ASUNCION','PILAR')),

    customer_name TEXT NOT NULL CHECK(length(trim(customer_name)) > 0),
    customer_phone TEXT NOT NULL DEFAULT '',

    job_type TEXT NOT NULL REFERENCES service_job_types(code),
    description TEXT NOT NULL CHECK(length(trim(description)) > 0),
    observations TEXT NOT NULL DEFAULT '',

    -- Quien recibio, quien lo hace y quien entrego son tres papeles distintos y
    -- muchas veces tres personas distintas; una sola columna los confundiria.
    received_by TEXT NOT NULL CHECK(length(trim(received_by)) > 0),
    responsible TEXT NOT NULL DEFAULT '',
    responsible_user_id TEXT REFERENCES admin_users(id),
    delivered_by TEXT NOT NULL DEFAULT '',

    status TEXT NOT NULL DEFAULT 'RECIBIDO' CHECK(status IN (
        'RECIBIDO','EN_TALLER','LISTO','ENTREGADO','ANULADO'
    )),

    promised_date TEXT,
    workshop_return_at TEXT,
    ready_at TEXT,
    delivered_at TEXT,
    voided_at TEXT,

    -- El importe queda como referencia de lo que se cobro, y el cobro real vive
    -- en la caja. No se duplica el dinero: cash_entry_id es el hecho.
    charged_amount INTEGER CHECK(charged_amount IS NULL OR charged_amount >= 0),
    cash_entry_id TEXT REFERENCES cash_entries(id),
    order_id TEXT REFERENCES orders(id),

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- Un trabajo entregado tiene fecha de entrega y quien lo entrego. Sin esto,
    -- ENTREGADO seria una palabra sin hecho detras.
    CHECK(status <> 'ENTREGADO' OR (delivered_at IS NOT NULL
                                    AND length(trim(delivered_by)) > 0)),
    CHECK(status <> 'ANULADO' OR voided_at IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_service_jobs_estado
    ON service_jobs(status, branch, received_at);
CREATE INDEX IF NOT EXISTS idx_service_jobs_responsable
    ON service_jobs(responsible_user_id, status);
CREATE INDEX IF NOT EXISTS idx_service_jobs_sucursal_fecha
    ON service_jobs(branch, received_at);
CREATE INDEX IF NOT EXISTS idx_service_jobs_cobro
    ON service_jobs(cash_entry_id) WHERE cash_entry_id IS NOT NULL;

-- Nada de hard-delete. Un trabajo con historia se anula, no se borra.
CREATE TRIGGER IF NOT EXISTS service_jobs_sin_delete
BEFORE DELETE ON service_jobs
BEGIN
    SELECT RAISE(ABORT, 'un trabajo no se borra: se anula y queda su historia');
END;

-- ==========================================================================
-- La historia del trabajo
-- ==========================================================================
--
-- Append-only y con sequence, igual que tracked_work_transitions. Cada fila
-- dice el trabajo, quien, cuando, de que estado a cual y por que. El motivo es
-- obligatorio en lo que necesita explicacion -anular y reabrir- porque son las
-- dos cosas que despues alguien va a preguntar.
CREATE TABLE IF NOT EXISTS service_job_events (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES service_jobs(id),
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN (
        'CREADO','RESPONSABLE_ASIGNADO','RESPONSABLE_CAMBIADO','ENVIADO_A_TALLER',
        'MARCADO_LISTO','ENTREGADO','ANULADO','REABIERTO','DATOS_MODIFICADOS',
        'COBRO_VINCULADO','COMISION_DEVENGADA','COMISION_COMPENSADA'
    )),
    from_status TEXT,
    to_status TEXT,
    actor TEXT NOT NULL CHECK(length(trim(actor)) > 0),
    reason TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL,
    UNIQUE(job_id, sequence),
    CHECK(event_type NOT IN ('ANULADO','REABIERTO') OR length(trim(reason)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_service_job_events_trabajo
    ON service_job_events(job_id, sequence);
CREATE INDEX IF NOT EXISTS idx_service_job_events_tipo
    ON service_job_events(event_type, occurred_at);

CREATE TRIGGER IF NOT EXISTS service_job_events_sin_update
BEFORE UPDATE ON service_job_events
BEGIN
    SELECT RAISE(ABORT, 'la historia de un trabajo no se reescribe');
END;

CREATE TRIGGER IF NOT EXISTS service_job_events_sin_delete
BEFORE DELETE ON service_job_events
BEGIN
    SELECT RAISE(ABORT, 'la historia de un trabajo no se borra');
END;

-- ==========================================================================
-- Comision de composturas
-- ==========================================================================
--
-- No es la comision comercial. La del 1% remunera vender y se calcula sobre el
-- monto de la venta; esta remunera arreglar, es un monto fijo por trabajo y la
-- cobra quien lo hizo, que muchas veces no es quien vendio. Viven en tablas
-- distintas y no se suman en ningun lado: fundirlas seria pagar dos veces una y
-- ninguna vez la otra.
--
-- La politica NO trae nombres sembrados. Que una persona cobre 5.000 por
-- compostura y otra no cobre nada es una decision de la Optica sobre personas
-- reales, y las personas reales viven en admin_users desde la 030. Sembrar un
-- nombre aqui seria volver a cablear en el esquema la lista que la 030 termino
-- de sacar de la pantalla. Sin politica cargada un trabajo no devenga: cero, no
-- un default inventado.
--
-- job_type vacio significa cualquier tipo. Es una sola columna con dos lecturas
-- y no dos tablas, porque la regla es la misma regla.
CREATE TABLE IF NOT EXISTS service_commission_policy (
    user_id TEXT NOT NULL REFERENCES admin_users(id),
    job_type TEXT NOT NULL DEFAULT '',
    amount INTEGER NOT NULL CHECK(amount >= 0),
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, job_type)
);

-- El devengo. Append-only con compensacion, igual que stock_movements: una
-- comision mal generada no se borra, se compensa.
--
-- event_id es UNIQUE y ahi esta toda la no-duplicacion: cada devengo cuelga del
-- evento que lo causo, y un evento causa un devengo o ninguno. Reprocesar,
-- reabrir y volver a marcar listo no puede pagar dos veces lo mismo, porque el
-- segundo intento choca contra el mismo evento.
CREATE TABLE IF NOT EXISTS service_job_commissions (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES service_jobs(id),
    event_id TEXT NOT NULL UNIQUE REFERENCES service_job_events(id),
    user_id TEXT REFERENCES admin_users(id),
    beneficiary TEXT NOT NULL CHECK(length(trim(beneficiary)) > 0),
    job_type TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('DEVENGO','COMPENSACION')),
    -- El signo sale del tipo, igual que en el ledger de stock. Asi lo adeudado
    -- es literalmente SUM(amount) y no hay forma de que una compensacion sume.
    amount INTEGER NOT NULL,
    compensates_id TEXT REFERENCES service_job_commissions(id),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    CHECK((kind = 'DEVENGO' AND amount > 0) OR (kind = 'COMPENSACION' AND amount < 0)),
    CHECK(kind <> 'COMPENSACION' OR compensates_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_service_commissions_trabajo
    ON service_job_commissions(job_id);
CREATE INDEX IF NOT EXISTS idx_service_commissions_persona
    ON service_job_commissions(user_id, created_at);
-- Un devengo se compensa una sola vez: dos compensaciones descontarian doble.
CREATE UNIQUE INDEX IF NOT EXISTS idx_service_commissions_compensacion_unica
    ON service_job_commissions(compensates_id) WHERE compensates_id IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS service_commissions_sin_update
BEFORE UPDATE ON service_job_commissions
BEGIN
    SELECT RAISE(ABORT, 'la comision es append-only: corregir con una compensacion');
END;

CREATE TRIGGER IF NOT EXISTS service_commissions_sin_delete
BEFORE DELETE ON service_job_commissions
BEGIN
    SELECT RAISE(ABORT, 'la comision es append-only: corregir con una compensacion');
END;

-- Lo adeudado por persona, derivado. No es un dato: es una cuenta.
CREATE VIEW IF NOT EXISTS service_commission_balance AS
SELECT user_id, beneficiary, SUM(amount) AS amount
FROM service_job_commissions
GROUP BY user_id, beneficiary;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('031', datetime('now'));

COMMIT;
