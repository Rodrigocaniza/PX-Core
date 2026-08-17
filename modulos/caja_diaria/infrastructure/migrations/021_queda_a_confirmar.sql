PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- RC27: el trabajo esta fisicamente en la optica pero todavia no puede salir
-- al laboratorio porque falta que el cliente confirme.
--
-- No es una etapa nueva del circuito: fisicamente el trabajo esta RECIBIDO EN
-- ASUNCION, y lo unico que cambia es que no corresponde despacharlo todavia.
-- Por eso viaja como condicion, igual que `reception_issue`, y no entra en el
-- CHECK de `status`. La operadora igual lo lee como estado, porque la fila
-- muestra `QUEDA A CONFIRMAR · RECIBIDO EN ASUNCIÓN`.
--
-- Modelarlo como condicion tambien evita reconstruir `tracked_works` para
-- ampliar su CHECK, que en una base con trabajos reales y dos tablas
-- referenciandola es un riesgo que este cambio no necesita correr.
ALTER TABLE tracked_works ADD COLUMN awaiting_confirmation INTEGER NOT NULL
    DEFAULT 0 CHECK(awaiting_confirmation IN (0,1));
ALTER TABLE tracked_works ADD COLUMN confirmation_note TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_tracked_works_awaiting_confirmation
    ON tracked_works(awaiting_confirmation) WHERE awaiting_confirmation = 1;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('021', CURRENT_TIMESTAMP);
COMMIT;
