PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- RC20: lote de envio desde Pilar.
-- El lote agrupa para cargar y recibir en bloque; no sustituye la identidad
-- individual del trabajo, que conserva su fila, su traza y su estado.
CREATE TABLE IF NOT EXISTS pilar_shipments (
    id TEXT PRIMARY KEY,
    shipped_on TEXT NOT NULL,
    consultation_date TEXT,
    origin_branch TEXT NOT NULL DEFAULT 'PILAR',
    destination_branch TEXT NOT NULL DEFAULT 'ASUNCION',
    operator TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pilar_shipments_fecha
    ON pilar_shipments(shipped_on DESC);

ALTER TABLE tracked_works ADD COLUMN shipment_id TEXT REFERENCES pilar_shipments(id);
CREATE INDEX IF NOT EXISTS idx_tracked_works_shipment ON tracked_works(shipment_id);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('017', CURRENT_TIMESTAMP);
COMMIT;
