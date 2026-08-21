PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-LABORATORIO-POR-DEFECTO-V1-012, slice 12.
--
-- Cada cristal se manda casi siempre al mismo laboratorio. Hoy la operadora
-- escribe ese nombre a mano en cada venta, y por eso en las diez lineas que hay
-- conviven 'Optilab', 'optilab', 'SI', 'asd' y 'asasa'. No es distraccion: es
-- que el dato no estaba en ningun lado y habia que recordarlo.
--
-- Lo que falta es una preferencia, no un atributo del articulo. El cristal no
-- «es» de Optilab: se le suele pedir a Optilab. La diferencia importa porque el
-- dia que la Optica cambie de laboratorio, cambiar la preferencia no puede
-- reescribir lo que ya se mando.

-- ==========================================================================
-- La preferencia
-- ==========================================================================
--
-- Nula por defecto, y esa nulidad es informacion: significa «nadie definio a
-- donde va esto», que es distinto de «va a ningun lado». `2000212 ST
-- Fotocromatico` se queda asi a proposito hasta que exista informacion real.
--
-- Apunta a `laboratories`, la tabla que la 003 ya creo para el circuito de
-- seguimiento. No se crea un segundo catalogo de laboratorios: el laboratorio
-- al que se le pide un cristal y el laboratorio al que se le reclama un trabajo
-- atrasado son el mismo, y tener dos listas seria tener dos verdades.
ALTER TABLE articles ADD COLUMN default_laboratory_id TEXT
    REFERENCES laboratories(id);

CREATE INDEX IF NOT EXISTS idx_articles_default_laboratory
    ON articles(default_laboratory_id);

-- ==========================================================================
-- Lo que NO se toca
-- ==========================================================================
--
-- `sale_items.laboratory` sigue siendo texto libre y sigue guardando el nombre
-- del laboratorio que realmente hizo ese trabajo. Es historia: dice a donde fue
-- esa venta, no a donde iria hoy. Cambiar la preferencia de un cristal manana
-- no puede alterar una linea de agosto, y por eso el default vive en el
-- articulo y el hecho vive en la linea.
--
-- Tampoco se toca `brand_id`. En las planillas de la Optica la columna «Marca»
-- de un cristal trae el laboratorio, y asi entro al catalogo: 20 cristales
-- tienen hoy «Laboratorio Optilab» o «Laboratorio Servi Optical» como marca.
-- Esta migracion no lo corrige ni lo copia: agrega el lugar donde ese dato
-- deberia haber estado siempre. Que la marca quede o se limpie es una decision
-- de catalogo, no de esquema.

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('028', datetime('now'));

COMMIT;
