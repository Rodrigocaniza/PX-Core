PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS order_status_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    responsible TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_status_revisions_order
ON order_status_revisions(order_id, id);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('014', CURRENT_TIMESTAMP);
COMMIT;