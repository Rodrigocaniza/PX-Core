PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- RC19: circuito Pilar -> Asuncion -> laboratorio -> Pilar.
-- Local-first: todo vive en la misma base SQLite de Caja. Los campos
-- created_at/updated_at quedan listos para una sincronizacion futura hacia
-- BC Gestion sin ampliar el alcance a infraestructura cloud.

CREATE TABLE IF NOT EXISTS laboratories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    -- Linea y WhatsApp son columnas distintas a proposito: rara vez coinciden.
    phone_line TEXT NOT NULL DEFAULT '',
    whatsapp TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_laboratories_active ON laboratories(active, name);

CREATE TABLE IF NOT EXISTS tracked_works (
    id TEXT PRIMARY KEY,
    envelope TEXT NOT NULL DEFAULT '',
    customer_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK(status IN (
        'ENVIADO_DESDE_PILAR','RECIBIDO_EN_ASUNCION','EN_LABORATORIO',
        'RECIBIDO_DEL_LABORATORIO','ENVIADO_A_PILAR','RECIBIDO_EN_PILAR','CERRADO'
    )),
    origin_branch TEXT NOT NULL DEFAULT 'PILAR',
    laboratory_id TEXT REFERENCES laboratories(id),
    expected_date TEXT,
    expected_time TEXT,
    confirmed_for_next_day INTEGER NOT NULL DEFAULT 0 CHECK(confirmed_for_next_day IN (0,1)),
    -- Identidad reutilizada: el trabajo enlaza con el pedido y la venta ya
    -- cargados en Caja cuando existen; sobre y cliente sostienen el caso en
    -- que Pilar registra antes de que haya venta en Asuncion.
    order_id TEXT REFERENCES orders(id),
    cash_entry_id TEXT REFERENCES cash_entries(id),
    consultation_date TEXT,
    observations TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(envelope <> '' OR customer_name <> '')
);
CREATE INDEX IF NOT EXISTS idx_tracked_works_status ON tracked_works(status, expected_date);
CREATE INDEX IF NOT EXISTS idx_tracked_works_laboratory ON tracked_works(laboratory_id, status);
CREATE INDEX IF NOT EXISTS idx_tracked_works_consultation ON tracked_works(consultation_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tracked_works_order
    ON tracked_works(order_id) WHERE order_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS tracked_work_transitions (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES tracked_works(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    responsible TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    recorded_at TEXT NOT NULL,
    UNIQUE(work_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_tracked_transitions_work
    ON tracked_work_transitions(work_id, sequence);

CREATE TABLE IF NOT EXISTS tracked_work_contacts (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES tracked_works(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    operator TEXT NOT NULL,
    channel TEXT NOT NULL CHECK(channel IN ('LLAMADA','WHATSAPP','OTRO')),
    result TEXT NOT NULL DEFAULT '',
    next_expected_date TEXT,
    next_expected_time TEXT,
    recorded_at TEXT NOT NULL,
    UNIQUE(work_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_tracked_contacts_work
    ON tracked_work_contacts(work_id, sequence);

-- Default operativo configurable: no se cablea una unica hora global.
INSERT OR IGNORE INTO app_settings(key,value_json,updated_by,updated_at) VALUES
('tracking', '{"default_expected_time":"15:00","alternate_expected_time":"15:30"}', 'SYSTEM', CURRENT_TIMESTAMP);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('016', CURRENT_TIMESTAMP);
COMMIT;
