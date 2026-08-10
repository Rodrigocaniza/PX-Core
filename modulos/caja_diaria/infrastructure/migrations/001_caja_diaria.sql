PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cash_days (
    id TEXT PRIMARY KEY,
    business_date TEXT NOT NULL,
    unit TEXT NOT NULL,
    opening_cash INTEGER NOT NULL CHECK (opening_cash >= 0),
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED')),
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    closing_total INTEGER,
    closing_cash INTEGER,
    closing_card_check INTEGER,
    closing_expenses INTEGER,
    closing_expected_cash INTEGER,
    closing_entry_count INTEGER,
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    UNIQUE (business_date, unit),
    CHECK (
        (status = 'OPEN' AND closed_at IS NULL)
        OR
        (status = 'CLOSED' AND closed_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS cash_entries (
    id TEXT PRIMARY KEY,
    cash_day_id TEXT NOT NULL REFERENCES cash_days(id) ON DELETE CASCADE,
    description TEXT NOT NULL CHECK (length(trim(description)) > 0),
    envelope TEXT NOT NULL DEFAULT '',
    frame_origin TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    frame TEXT NOT NULL DEFAULT '',
    lens TEXT NOT NULL DEFAULT '',
    prescription_doctor TEXT NOT NULL DEFAULT '',
    total INTEGER CHECK (total IS NULL OR total >= 0),
    cash INTEGER CHECK (cash IS NULL OR cash >= 0),
    card_check INTEGER CHECK (card_check IS NULL OR card_check >= 0),
    orders_text TEXT NOT NULL DEFAULT '',
    installments_text TEXT NOT NULL DEFAULT '',
    balance_text TEXT NOT NULL DEFAULT '',
    expenses INTEGER CHECK (expenses IS NULL OR expenses >= 0),
    origin TEXT NOT NULL DEFAULT 'manual',
    source_reference TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cash_entries_day ON cash_entries(cash_day_id);

CREATE TABLE IF NOT EXISTS cash_counts (
    id TEXT PRIMARY KEY,
    cash_day_id TEXT NOT NULL REFERENCES cash_days(id) ON DELETE CASCADE,
    quantities_json TEXT NOT NULL,
    counted_total INTEGER NOT NULL CHECK (counted_total >= 0),
    expected_total INTEGER NOT NULL,
    difference INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('OK', 'SOBRA', 'FALTA')),
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cash_counts_day_time ON cash_counts(cash_day_id, recorded_at DESC);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('001', CURRENT_TIMESTAMP);
COMMIT;
