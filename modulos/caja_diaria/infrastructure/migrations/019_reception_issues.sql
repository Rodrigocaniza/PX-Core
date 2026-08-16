PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- RC24: discrepancias reales al recibir un lote.
-- No son etapas del circuito: conviven con la etapa y se resuelven recibiendo
-- o corrigiendo, asi que no entran en el CHECK de `status`.
ALTER TABLE tracked_works ADD COLUMN reception_issue TEXT
    CHECK(reception_issue IN ('NO_LLEGO','NO_ESTABA_EN_LISTA'));
CREATE INDEX IF NOT EXISTS idx_tracked_works_reception_issue
    ON tracked_works(reception_issue) WHERE reception_issue IS NOT NULL;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('019', CURRENT_TIMESTAMP);
COMMIT;
