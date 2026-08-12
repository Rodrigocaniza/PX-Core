PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    position INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    category_slug TEXT NOT NULL REFERENCES categories(slug) ON UPDATE CASCADE,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    body TEXT NOT NULL CHECK (length(trim(body)) > 0),
    keywords TEXT NOT NULL DEFAULT '',
    search_blob TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    favorite INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1)),
    -- Reservado para "plantillas por sucursal": '' significa todas las sucursales.
    branch TEXT NOT NULL DEFAULT '',
    origin TEXT NOT NULL DEFAULT 'manual',
    usage_count INTEGER NOT NULL DEFAULT 0 CHECK (usage_count >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_templates_unique_title
    ON templates(category_slug, branch, lower(trim(title)));
CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category_slug, active);
CREATE INDEX IF NOT EXISTS idx_templates_favorite ON templates(favorite, active);

CREATE TABLE IF NOT EXISTS template_variables (
    template_id TEXT NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    example TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (template_id, name)
);

CREATE TABLE IF NOT EXISTS prepared_messages (
    id TEXT PRIMARY KEY,
    template_id TEXT,
    template_title TEXT NOT NULL,
    category_slug TEXT NOT NULL DEFAULT '',
    final_text TEXT NOT NULL CHECK (length(trim(final_text)) > 0),
    values_json TEXT NOT NULL DEFAULT '{}',
    operator TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT 'whatsapp',
    status TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK (status IN ('PENDIENTE', 'ENVIADO', 'ENTREGADO', 'RESPONDIDO')),
    delivery_reference TEXT NOT NULL DEFAULT '',
    -- Enganche para clientes / pedidos futuros: ('cliente', '<id>') o ('pedido', '<id>').
    subject_kind TEXT NOT NULL DEFAULT '',
    subject_reference TEXT NOT NULL DEFAULT '',
    manually_edited INTEGER NOT NULL DEFAULT 0 CHECK (manually_edited IN (0, 1)),
    prepared_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prepared_recent ON prepared_messages(prepared_at DESC);
CREATE INDEX IF NOT EXISTS idx_prepared_status ON prepared_messages(status, prepared_at DESC);

-- Outbox local: telemetría y envío directo futuro por proveedor intercambiable.
-- El MVP sólo escribe eventos; ningún despachador los consume todavía.
CREATE TABLE IF NOT EXISTS outbox_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    dispatched_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox_events(dispatched_at, created_at);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('001', CURRENT_TIMESTAMP);
COMMIT;
