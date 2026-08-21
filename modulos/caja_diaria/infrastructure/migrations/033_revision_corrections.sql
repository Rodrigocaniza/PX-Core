-- Solicitudes de corrección que vuelven desde Gestión Central.
-- Aditiva y append-only: no modifica ventas ni revisiones históricas.
CREATE TABLE IF NOT EXISTS central_review_corrections (
    id                  TEXT PRIMARY KEY,
    idempotency_key     TEXT NOT NULL UNIQUE,
    review_identity     TEXT NOT NULL,
    cash_entry_id       TEXT NOT NULL,
    requested_version   INTEGER NOT NULL,
    field_name          TEXT,
    reason              TEXT NOT NULL,
    requested_by        TEXT NOT NULL,
    requested_at        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK(status IN ('PENDIENTE','VISTA','RESUELTA','REABIERTA')),
    seen_by             TEXT,
    seen_at             TEXT,
    resolved_by         TEXT,
    resolved_at         TEXT,
    resolved_version    INTEGER,
    resolution_reason   TEXT
);

CREATE INDEX IF NOT EXISTS idx_central_review_corrections_pending
    ON central_review_corrections(status, cash_entry_id, requested_at);

CREATE TABLE IF NOT EXISTS central_review_correction_events (
    id              TEXT PRIMARY KEY,
    correction_id   TEXT NOT NULL REFERENCES central_review_corrections(id),
    action          TEXT NOT NULL,
    actor           TEXT NOT NULL,
    details_json    TEXT NOT NULL DEFAULT '{}',
    recorded_at     TEXT NOT NULL
);

