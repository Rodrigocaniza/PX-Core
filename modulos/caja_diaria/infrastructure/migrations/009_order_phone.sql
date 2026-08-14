PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

ALTER TABLE orders ADD COLUMN customer_phone TEXT NOT NULL DEFAULT '';

UPDATE orders
SET customer_phone = COALESCE((
    SELECT cash_entries.customer_phone
    FROM cash_entries
    WHERE cash_entries.id = orders.cash_entry_id
), '')
WHERE cash_entry_id IS NOT NULL AND customer_phone = '';

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('009', CURRENT_TIMESTAMP);
COMMIT;
