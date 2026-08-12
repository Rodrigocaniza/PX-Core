PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS sale_items (
    id TEXT PRIMARY KEY,
    cash_entry_id TEXT NOT NULL REFERENCES cash_entries(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 0),
    description TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    item_type TEXT NOT NULL DEFAULT '',
    frame_price INTEGER CHECK (frame_price IS NULL OR frame_price >= 0),
    lens_price INTEGER CHECK (lens_price IS NULL OR lens_price >= 0),
    laboratory TEXT NOT NULL DEFAULT '',
    prescription_doctor TEXT NOT NULL DEFAULT '',
    UNIQUE(cash_entry_id, position)
);
CREATE INDEX IF NOT EXISTS idx_sale_items_entry ON sale_items(cash_entry_id, position);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('006', CURRENT_TIMESTAMP);
COMMIT;
