PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-COMERCIAL-UI-Y-CARGA-INICIAL-V1-005, slice 5.
--
-- Los slices 1 a 4 cerraron el circuito y no dejaron una sola pantalla desde
-- donde usarlo. Este slice hace operable lo que ya existe. De dominio agrega lo
-- minimo indispensable para que la pantalla de articulos exista de verdad, y
-- nada mas.
--
-- Migracion aditiva: tres ADD COLUMN sobre articles, un indice parcial y un
-- motivo sembrado. No reconstruye ni reescribe nada.

-- ==========================================================================
-- Lo que el ABM de articulos necesita y no tenia donde vivir
-- ==========================================================================
--
-- Estos tres son datos propios del articulo, sin ninguna otra fuente posible:
-- donde esta fisicamente, cuando avisar que se esta por acabar, y su codigo de
-- barras si el proveedor se lo puso.
--
-- Lo que NO se agrega, y es deliberado:
--
--   * `cost`. El costo de un articulo es lo que dice la factura con que se
--     compro, y eso ya vive en purchase_lines.unit_cost. Una columna aca seria
--     una segunda verdad que puede contradecir al documento. La pantalla lo
--     muestra DERIVADO de la ultima compra, y cuando no hay compra lo declara
--     PENDIENTE_DE_CONCILIACION en vez de inventar un numero.
--
--   * `tax_rate`. El IVA de la optica es 10% para todo y no hay evidencia de
--     una sola excepcion. Una columna por articulo inventaria una variabilidad
--     que el negocio no tiene, y despues alguien la llenaria mal.
ALTER TABLE articles ADD COLUMN location TEXT NOT NULL DEFAULT '';
ALTER TABLE articles ADD COLUMN min_stock INTEGER;
ALTER TABLE articles ADD COLUMN barcode TEXT;

-- Igual que el RUC del proveedor: cuando hay identidad, el duplicado se
-- bloquea; cuando no la hay, no se inventa una para poder comparar.
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_barcode_unico
    ON articles(barcode) WHERE barcode IS NOT NULL AND trim(barcode) <> '';
CREATE INDEX IF NOT EXISTS idx_articles_min_stock
    ON articles(min_stock) WHERE min_stock IS NOT NULL;

-- ==========================================================================
-- El stock inicial es un hecho, no un dato de arranque
-- ==========================================================================
--
-- El inventario fisico que hoy hay en las dos sucursales NO se puede deducir de
-- ninguna compra registrada: no hay compras registradas. Entra por un recuento,
-- que es un hecho real con fecha, responsable y motivo, y por eso entra como
-- INGRESO_ADMINISTRATIVO igual que cualquier otro ingreso sin factura.
--
-- Falsear una compra historica para crear stock inicial habria dado un stock
-- correcto colgando de un proveedor que nunca facturo eso, y esa mentira no se
-- puede deshacer despues sin borrar historia.
INSERT OR IGNORE INTO administrative_entry_reasons(code, label, requires_note, position)
VALUES ('INVENTARIO_INICIAL', 'Inventario inicial (recuento físico)', 1, 0);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('026', CURRENT_TIMESTAMP);
COMMIT;
