PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

ALTER TABLE cash_entries ADD COLUMN laboratory TEXT NOT NULL DEFAULT '';

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('003', CURRENT_TIMESTAMP);
COMMIT;