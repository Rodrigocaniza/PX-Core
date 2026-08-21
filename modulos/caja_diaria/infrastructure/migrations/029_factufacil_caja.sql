PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-FACTUFACIL-CAJA-V1-016, slice 16.
--
-- Hoy la chica que atiende no sabe que ventas faltan cargar en FactuFacil.
-- Alguien mas lleva esa cuenta en otro sistema, y para saberlo hay que
-- preguntarle. Lo que falta no es una pantalla: es un lugar donde diga que ya
-- se cargo, y quien la cargo.
--
-- ==========================================================================
-- Lo que NO se crea, y es la decision de fondo
-- ==========================================================================
--
-- No se crea una tabla de ventas de FactuFacil. La venta ya existe en
-- `cash_entries`: tiene el cliente, el sobre, la vendedora, el importe, el
-- documento, el telefono y las observaciones. Copiarla a otra tabla seria
-- cargar el mismo hecho dos veces, y el dia que se corrija en Caja la copia
-- quedaria mintiendo.
--
-- «PARA CARGAR» tampoco se guarda: se deduce. Una venta activa, que no sea un
-- gasto ni una entrega a administracion, con importe, y sin marca de cargada,
-- esta para cargar. Es una consulta, no un estado que alguien tenga que
-- mantener al dia.
--
-- Lo unico que no se puede deducir de ningun lado es que una persona entro a
-- FactuFacil y la cargo. Eso, y solo eso, es lo que estas dos tablas guardan.

-- ==========================================================================
-- La marca
-- ==========================================================================
--
-- Una fila por venta que alguna vez se marco. No tener fila significa «nadie
-- la marco todavia», que es distinto de «se reverso»: lo segundo deja fila con
-- estado PARA_CARGAR y su historia al lado.
--
-- `entry_revision` guarda en que version de la venta se hizo la marca. Si
-- despues alguien corrige el importe o el cliente, la revision de la venta
-- avanza y deja de coincidir: la pantalla lo muestra, y nadie se entera tarde
-- de que se cargo un dato viejo.
CREATE TABLE IF NOT EXISTS factufacil_loads (
    cash_entry_id   TEXT PRIMARY KEY REFERENCES cash_entries(id),
    status          TEXT NOT NULL CHECK (status IN ('PARA_CARGAR', 'CARGADA')),
    loaded_by       TEXT NOT NULL DEFAULT '',
    loaded_at       TEXT NOT NULL DEFAULT '',
    entry_revision  INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_factufacil_loads_status
    ON factufacil_loads(status);

-- ==========================================================================
-- La historia, que no se pisa
-- ==========================================================================
--
-- Append-only: marcar, revertir y volver a marcar dejan cada uno su linea. El
-- motivo es obligatorio al revertir porque una reversion sin motivo es una
-- marca que desaparece sin que nadie sepa por que.
CREATE TABLE IF NOT EXISTS factufacil_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cash_entry_id   TEXT NOT NULL REFERENCES cash_entries(id),
    from_state      TEXT,
    to_state        TEXT NOT NULL,
    actor           TEXT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    entry_revision  INTEGER NOT NULL DEFAULT 0,
    recorded_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_factufacil_history_entry
    ON factufacil_history(cash_entry_id, id);

-- ==========================================================================
-- Lo que esta migracion no toca
-- ==========================================================================
--
-- Ni `cash_entries`, ni `cash_days`, ni `sale_items`, ni un importe. Marcar una
-- venta como cargada en FactuFacil no puede cambiar la caja del dia: son dos
-- hechos distintos y el cierre economico no se entera de este. Por eso la marca
-- vive en su propia tabla y no en una columna de la venta.
--
-- Aditiva y backward-safe: una version anterior de BC Caja abre esta base y no
-- ve estas tablas, y todo lo demas sigue funcionando igual.

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('029', datetime('now'));

COMMIT;
