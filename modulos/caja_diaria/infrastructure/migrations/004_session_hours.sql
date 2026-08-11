PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

ALTER TABLE cash_days ADD COLUMN session_duration_seconds INTEGER
    CHECK (session_duration_seconds IS NULL OR session_duration_seconds >= 0);
ALTER TABLE cash_days ADD COLUMN overtime_triggered INTEGER
    CHECK (overtime_triggered IS NULL OR overtime_triggered IN (0, 1));
ALTER TABLE cash_days ADD COLUMN overtime_minutes INTEGER
    CHECK (overtime_minutes IS NULL OR overtime_minutes >= 0);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('004', CURRENT_TIMESTAMP);
COMMIT;
