PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

ALTER TABLE sale_items ADD COLUMN frame_discount_percent INTEGER NOT NULL DEFAULT 0 CHECK (frame_discount_percent BETWEEN 0 AND 100);
ALTER TABLE sale_items ADD COLUMN lens_discount_percent INTEGER NOT NULL DEFAULT 0 CHECK (lens_discount_percent BETWEEN 0 AND 100);
ALTER TABLE sale_items ADD COLUMN frame_final_price INTEGER CHECK (frame_final_price IS NULL OR frame_final_price >= 0);
ALTER TABLE sale_items ADD COLUMN lens_final_price INTEGER CHECK (lens_final_price IS NULL OR lens_final_price >= 0);
ALTER TABLE sale_items ADD COLUMN no_cost INTEGER NOT NULL DEFAULT 0 CHECK (no_cost IN (0, 1));

UPDATE sale_items
SET frame_final_price = COALESCE(frame_final_price, frame_price, 0),
    lens_final_price = COALESCE(lens_final_price, lens_price, 0)
WHERE frame_final_price IS NULL OR lens_final_price IS NULL;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('013', CURRENT_TIMESTAMP);
COMMIT;
