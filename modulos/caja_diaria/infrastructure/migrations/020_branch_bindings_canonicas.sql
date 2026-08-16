PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-CAJA-RC25: los tres vinculos caja -> sucursal que la operacion ya usa.
--
-- La 018 solo derivo la caja de esta instalacion desde app_settings y dejo el
-- resto sin vincular a proposito. Con la alerta principal en la pantalla de
-- Caja, una caja sin sucursal deja de ser un hueco silencioso y pasa a ser una
-- pantalla sin alerta: PC, P2 y PILAR son inequivocas y se siembran.
--
-- `INSERT OR IGNORE` respeta cualquier asignacion administrativa previa: si
-- alguien ya vinculo la caja a mano, esa decision manda sobre la siembra.
INSERT OR IGNORE INTO cash_register_branches(
    cash_register, branch, assigned_by, reason, created_at, updated_at)
VALUES
    ('PC',    'ASUNCION', 'MIGRACION-020',
     'Vinculo canonico de la operacion: la caja PC atiende en Asuncion',
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('P2',    'PILAR',    'MIGRACION-020',
     'Vinculo canonico de la operacion: la caja P2 atiende en Pilar',
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('PILAR', 'PILAR',    'MIGRACION-020',
     'Vinculo canonico de la operacion: la caja PILAR atiende en Pilar',
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('020', CURRENT_TIMESTAMP);
COMMIT;
