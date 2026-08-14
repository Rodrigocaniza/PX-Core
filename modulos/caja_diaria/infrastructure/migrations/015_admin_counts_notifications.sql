BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS admin_users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    iterations INTEGER NOT NULL CHECK(iterations >= 100000),
    role TEXT NOT NULL DEFAULT 'ADMIN',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS authorized_responsibles (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_admin_audit_time ON admin_audit_log(recorded_at DESC);

CREATE TABLE IF NOT EXISTS import_runs (
    id TEXT PRIMARY KEY,
    administrator TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    unit TEXT NOT NULL,
    rows_processed INTEGER NOT NULL DEFAULT 0,
    rows_imported INTEGER NOT NULL DEFAULT 0,
    rows_skipped INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    result TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(file_sha256, unit)
);

CREATE TABLE IF NOT EXISTS cash_count_snapshots (
    id TEXT PRIMARY KEY,
    cash_day_id TEXT NOT NULL REFERENCES cash_days(id),
    count_type TEXT NOT NULL CHECK(count_type IN ('OPENING','INTERMEDIATE','CLOSING')),
    sequence INTEGER NOT NULL DEFAULT 1,
    quantities_json TEXT NOT NULL,
    counted_total INTEGER NOT NULL CHECK(counted_total >= 0),
    expected_total INTEGER,
    difference INTEGER,
    reason TEXT NOT NULL DEFAULT '',
    responsible TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('DRAFT','CONFIRMED')),
    idempotency_key TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL,
    UNIQUE(cash_day_id, count_type, sequence)
);
CREATE INDEX IF NOT EXISTS idx_count_snapshots_day ON cash_count_snapshots(cash_day_id, recorded_at);

CREATE TABLE IF NOT EXISTS mail_outbox (
    id TEXT PRIMARY KEY,
    cash_day_id TEXT NOT NULL REFERENCES cash_days(id),
    closure_id TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    report_path TEXT NOT NULL,
    recipient TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('PENDING','SENT','ERROR','NOT_CONFIGURED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sent_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_mail_outbox_status ON mail_outbox(status, next_attempt_at);

CREATE TABLE IF NOT EXISTS mail_history (
    id TEXT PRIMARY KEY,
    outbox_id TEXT NOT NULL REFERENCES mail_outbox(id),
    result TEXT NOT NULL,
    sanitized_detail TEXT NOT NULL DEFAULT '',
    recorded_at TEXT NOT NULL
);

INSERT OR IGNORE INTO app_settings(key,value_json,updated_by,updated_at) VALUES
('counting', '{"blind_close":true,"tolerance":0,"reason_mode":"ANY_DIFFERENCE","admin_limit":0}', 'SYSTEM', CURRENT_TIMESTAMP),
('branch', '{"branch":"Optica Central","cashbox":"PC"}', 'SYSTEM', CURRENT_TIMESTAMP),
('mail', '{"enabled":false,"recipient":"","cc":[],"subject":"Cierre {fecha} - {sucursal}","host":"","port":587,"username":"","secret_ref":"smtp"}', 'SYSTEM', CURRENT_TIMESTAMP);

INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES ('015', CURRENT_TIMESTAMP);
COMMIT;
