PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- RC22: una caja pertenece permanentemente a una sucursal.
-- La cajera cambia; el vinculo caja -> sucursal no. Cambiarlo exige una
-- accion administrativa explicita, registrada en admin_audit_log.
CREATE TABLE IF NOT EXISTS cash_register_branches (
    cash_register TEXT PRIMARY KEY COLLATE NOCASE,
    branch TEXT NOT NULL,
    assigned_by TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cash_register_branches_branch
    ON cash_register_branches(branch);

-- La sucursal que procesa el trabajo, distinta de la que lo origino.
ALTER TABLE tracked_works ADD COLUMN processing_branch TEXT NOT NULL DEFAULT 'ASUNCION';
CREATE INDEX IF NOT EXISTS idx_tracked_works_branches
    ON tracked_works(origin_branch, processing_branch, status);

-- Solo se siembra lo inequivoco. Las cajas sin evidencia quedan sin vincular
-- a proposito: inventarles una sucursal enrutaria trabajos al local errado.
INSERT OR IGNORE INTO cash_register_branches(
    cash_register, branch, assigned_by, reason, created_at, updated_at)
SELECT json_extract(value_json, '$.cashbox'),
       'ASUNCION',
       'MIGRACION-018',
       'Derivado de app_settings.branch, que liga esta instalacion a su caja',
       CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM app_settings
WHERE key = 'branch'
  AND COALESCE(json_extract(value_json, '$.cashbox'), '') <> '';

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('018', CURRENT_TIMESTAMP);
COMMIT;
