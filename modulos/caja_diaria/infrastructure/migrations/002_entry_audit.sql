BEGIN IMMEDIATE;

ALTER TABLE cash_entries ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'VOIDED'));
ALTER TABLE cash_entries ADD COLUMN voided_at TEXT;
ALTER TABLE cash_entries ADD COLUMN void_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE cash_entries ADD COLUMN revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0);

CREATE TABLE IF NOT EXISTS cash_entry_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,
    cash_day_id TEXT NOT NULL REFERENCES cash_days(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL CHECK (revision >= 0),
    action TEXT NOT NULL CHECK (action IN ('CREATE', 'UPDATE', 'VOID')),
    snapshot_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE (entry_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_entry_revisions_entry
    ON cash_entry_revisions(entry_id, revision);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('002', CURRENT_TIMESTAMP);
COMMIT;
