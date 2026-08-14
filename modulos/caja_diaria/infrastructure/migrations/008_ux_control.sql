ALTER TABLE cash_entries ADD COLUMN customer_phone TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS cash_day_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cash_day_id TEXT NOT NULL REFERENCES cash_days(id) ON DELETE CASCADE,
    unit TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT NOT NULL,
    new_value TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    corrected_by TEXT NOT NULL CHECK (length(trim(corrected_by)) > 0),
    corrected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cash_day_corrections_day_time
ON cash_day_corrections(cash_day_id, corrected_at DESC);
