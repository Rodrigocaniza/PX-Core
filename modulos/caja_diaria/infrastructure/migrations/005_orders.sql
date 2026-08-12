PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

ALTER TABLE cash_entries ADD COLUMN customer_document TEXT NOT NULL DEFAULT '';
ALTER TABLE cash_entries ADD COLUMN saleswoman TEXT NOT NULL DEFAULT '';
ALTER TABLE cash_entries ADD COLUMN delivery_date TEXT;
ALTER TABLE cash_entries ADD COLUMN observations TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    source_reference TEXT NOT NULL DEFAULT '',
    delivery_date TEXT NOT NULL,
    branch TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    customer_document TEXT NOT NULL DEFAULT '',
    envelope TEXT NOT NULL DEFAULT '',
    saleswoman TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDIENTE', 'LISTO', 'ENTREGADO')),
    observations TEXT NOT NULL DEFAULT '',
    cash_entry_id TEXT REFERENCES cash_entries(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_cash_entry
    ON orders(cash_entry_id) WHERE cash_entry_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_delivery_status
    ON orders(delivery_date, status);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('005', CURRENT_TIMESTAMP);
COMMIT;
