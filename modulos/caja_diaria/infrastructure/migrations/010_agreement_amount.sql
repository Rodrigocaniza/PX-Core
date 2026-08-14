ALTER TABLE cash_entries
ADD COLUMN agreement_amount INTEGER NOT NULL DEFAULT 0 CHECK (agreement_amount >= 0);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('010', datetime('now'));
