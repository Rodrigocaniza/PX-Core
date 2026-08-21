PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-COMMERCIAL-CORE-FOUNDATION-V1-001, slice 1.
--
-- Foundation canonica del nucleo comercial: los catalogos de los que van a
-- colgar Compras, Stock, Ventas y Trabajos. BC Caja evoluciona hacia el sistema
-- operativo/comercial de la optica; esto NO es un sistema paralelo, vive en la
-- misma base y en la misma cadena de migraciones.
--
-- Migracion estrictamente ADITIVA: solo CREATE TABLE/INDEX IF NOT EXISTS y un
-- ALTER TABLE ADD COLUMN nullable. No altera ni reconstruye ninguna tabla
-- existente, asi que ninguna fila productiva se toca.

-- Categorias y marcas: catalogos planos, nombre unico sin importar mayusculas.
CREATE TABLE IF NOT EXISTS article_categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_article_categories_active
    ON article_categories(active, name);

CREATE TABLE IF NOT EXISTS brands (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_brands_active ON brands(active, name);

-- Proveedores. `laboratory_id` referencia el catalogo canonico de laboratorios
-- que ya existe desde la 016: un laboratorio que ademas factura es un proveedor
-- que apunta a su laboratorio, no una segunda ficha que haya que mantener
-- sincronizada a mano.
CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    kind TEXT NOT NULL DEFAULT 'PROVEEDOR'
        CHECK(kind IN ('PROVEEDOR','LABORATORIO','AMBOS')),
    document TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    laboratory_id TEXT REFERENCES laboratories(id),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_suppliers_active ON suppliers(active, name);
CREATE INDEX IF NOT EXISTS idx_suppliers_laboratory ON suppliers(laboratory_id);

-- Articulos.
--
-- `nature` es el eje del modelo y por eso es un CHECK cerrado, no texto libre:
--   PRODUCTO_STOCKEABLE     armazon, liquido, estuche
--   SERVICIO_NO_STOCKEABLE  compostura, ajuste, consulta
--   TRABAJO_BAJO_PEDIDO     cristal recetado, insumo pedido para un trabajo
--   PRODUCCION_INTERNA      lo que la optica arma y despues vende
--
-- No hay columna `tracks_stock`. Si mueve stock se DERIVA de la naturaleza, en
-- el dominio. Una columna libre permitiria un armazon que no mueve stock y una
-- compostura que si, que es justo el error que este modelo existe para impedir.
--
-- De ahi se sigue lo pedido: composturas y cristales no se representan con
-- productos, facturas ni clientes ficticios. Son naturalezas que no generan
-- unidades de inventario, asi que no hay nada ficticio que crear ni que limpiar.
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
    nature TEXT NOT NULL CHECK(nature IN (
        'PRODUCTO_STOCKEABLE','SERVICIO_NO_STOCKEABLE',
        'TRABAJO_BAJO_PEDIDO','PRODUCCION_INTERNA'
    )),
    category_id TEXT REFERENCES article_categories(id),
    brand_id TEXT REFERENCES brands(id),
    supplier_id TEXT REFERENCES suppliers(id),
    unit TEXT NOT NULL DEFAULT 'UNIDAD',
    sale_price INTEGER CHECK(sale_price IS NULL OR sale_price >= 0),
    notes TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_nature ON articles(nature, active);
CREATE INDEX IF NOT EXISTS idx_articles_active_name ON articles(active, name);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category_id);
CREATE INDEX IF NOT EXISTS idx_articles_brand ON articles(brand_id);
CREATE INDEX IF NOT EXISTS idx_articles_supplier ON articles(supplier_id);

-- Motivos de salida administrativa. Lista cerrada y sembrada; el movimiento que
-- los consume es el slice del ledger, pero el catalogo es foundation y va aca.
-- Cada salida va a exigir motivo, observacion, usuario, fecha y cantidad.
CREATE TABLE IF NOT EXISTS administrative_exit_reasons (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    requires_note INTEGER NOT NULL DEFAULT 0 CHECK(requires_note IN (0,1)),
    position INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);

INSERT OR IGNORE INTO administrative_exit_reasons(code, label, requires_note, position)
VALUES
    ('ROTO',             'Roto',                 0, 1),
    ('RAYADO',           'Rayado',               0, 2),
    ('PERDIDA',          'Pérdida',              1, 3),
    ('DETERIORO',        'Deterioro',            0, 4),
    ('USO_INTERNO',      'Uso interno',          1, 5),
    ('ERROR_INVENTARIO', 'Error de inventario',  1, 6),
    -- `OTRO` exige observacion: sin ella la salida seria un agujero sin explicar.
    ('OTRO',             'Otro',                 1, 7);

-- La costura con la venta que hoy se escribe a mano.
--
-- Nullable a proposito: las lineas de venta que ya existen en produccion no
-- tienen articulo del catalogo y NO se les inventa uno. La UI no cambia en este
-- slice; la columna queda lista para que el slice de Ventas la empiece a llenar
-- hacia adelante, sin reescribir historia.
ALTER TABLE sale_items ADD COLUMN article_id TEXT REFERENCES articles(id);
CREATE INDEX IF NOT EXISTS idx_sale_items_article ON sale_items(article_id);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('022', CURRENT_TIMESTAMP);
COMMIT;
