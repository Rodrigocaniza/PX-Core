PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-COMISION-COMPOSTURAS-V1-021, slice 21.
--
-- La 031 dejo el motor: una compostura que llega a LISTO devenga, el event_id
-- unico impide pagar dos veces el mismo hecho, y anular compensa en vez de
-- borrar. Lo que no dejo es como se administra eso. Su tabla de politica tiene
-- una fila por persona y se sobreescribe, y ahi hay dos cosas que el negocio si
-- necesita y esa forma no puede dar.
--
-- La primera es la vigencia. El dia que una tarifa pase de 5.000 a 7.000, un
-- UPDATE deja la base diciendo que siempre fue 7.000, y las composturas de
-- agosto pasan a estar explicadas por una tarifa que en agosto no existia. El
-- importe devengado no cambia -eso ya esta guardado en el asiento- pero se
-- pierde la razon: por que se pagaron 5.000. Un numero economico sin su causa
-- verificable es exactamente lo que este sistema no quiere tener.
--
-- La segunda es que una politica se apaga. Con una sola fila, dejar de
-- comisionar a alguien solo se puede escribir borrando la fila o poniendo cero,
-- y las dos cosas mienten distinto: la primera borra que alguna vez cobro, la
-- segunda dice "le corresponde cero" donde lo que paso fue "se le dio de baja".
--
-- ==========================================================================
-- Por que versiones y no columnas nuevas
-- ==========================================================================
--
-- Agregar active, effective_from y reason con ALTER TABLE seria aditivo y
-- barato, y no alcanzaria: la PRIMARY KEY (user_id, job_type) admite una fila
-- por alcance, asi que cada cambio seguiria pisando al anterior. La historia no
-- se guarda agregando columnas a la fila que se sobreescribe; se guarda dejando
-- de sobreescribirla.
--
-- Asi que la politica pasa a ser un log append-only, igual que
-- service_job_commissions y stock_movements: cada cambio es una fila nueva que
-- sucede a la anterior. Cambiar el importe, activar y desactivar son todos el
-- mismo hecho -una version nueva- y por eso no hay tres caminos distintos que
-- mantener.

-- ==========================================================================
-- La politica, versionada
-- ==========================================================================
--
-- El alcance son tres columnas y las tres usan el mismo idioma que ya usaba la
-- 031 para job_type: vacio significa "cualquiera". branch vacio es la politica
-- comun de la persona, job_type vacio es cualquier tipo de trabajo. La regla
-- mas especifica gana, y quien tenga una sola politica global tiene una sola
-- fila, sin pagar la complejidad de una sucursal que no necesita.
--
-- user_id y no display_name: la identidad estable esta en admin_users desde la
-- 030. Corregir como se escribe el nombre de una persona no puede reescribir a
-- quien se le devengo en agosto.
--
-- amount >= 0 y no > 0: cero es una decision legitima y distinta de no tener
-- politica. "A esta persona le corresponde cero" es una respuesta; "no hay
-- politica cargada" es una pregunta sin responder, y el reporte las distingue.
CREATE TABLE IF NOT EXISTS service_commission_policy_versions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES admin_users(id),
    branch TEXT NOT NULL DEFAULT '' CHECK(branch IN ('','ASUNCION','PILAR')),
    job_type TEXT NOT NULL DEFAULT '',
    amount INTEGER NOT NULL CHECK(amount >= 0),

    -- Apagar una politica es una version mas, no un DELETE. Asi la baja tiene
    -- fecha, actor y motivo, que es lo que despues alguien va a preguntar.
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),

    -- Desde cuando rige. Puede ser futura: una tarifa acordada hoy que empieza
    -- el mes que viene se carga hoy y no depende de que alguien se acuerde.
    effective_from TEXT NOT NULL,

    -- Lo que valia antes, copiado al momento del cambio. Es redundante con la
    -- version anterior y se guarda igual: el pedido operativo es "que paso con
    -- este importe", y responderlo no deberia obligar a reconstruir la cadena.
    previous_amount INTEGER,
    supersedes_id TEXT REFERENCES service_commission_policy_versions(id),

    reason TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL CHECK(length(trim(created_by)) > 0),

    -- Cuando se escribio la fila, que no es lo mismo que desde cuando rige.
    -- Esta distincion no es prolijidad: es el desempate. Dos versiones del
    -- mismo alcance pueden compartir effective_from -corregir una tarifa
    -- futura antes de que empiece es normal, y las dos arrancan el dia 1- y en
    -- ese caso rige la que se escribio despues. Prohibir el empate con un
    -- UNIQUE fue la primera idea y estaba mal: convertia una correccion
    -- legitima en un error de base, y obligaba a la administradora a inventar
    -- una fecha distinta a la que queria poner.
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_service_policy_versions_alcance
    ON service_commission_policy_versions(user_id, branch, job_type, effective_from);
CREATE INDEX IF NOT EXISTS idx_service_policy_versions_persona
    ON service_commission_policy_versions(user_id, created_at);

CREATE TRIGGER IF NOT EXISTS service_policy_versions_sin_update
BEFORE UPDATE ON service_commission_policy_versions
BEGIN
    SELECT RAISE(ABORT, 'la politica es append-only: cambiar es agregar una version');
END;

CREATE TRIGGER IF NOT EXISTS service_policy_versions_sin_delete
BEFORE DELETE ON service_commission_policy_versions
BEGIN
    SELECT RAISE(ABORT, 'una politica no se borra: se desactiva y queda su historia');
END;

-- ==========================================================================
-- Lo que la 031 ya habia cargado
-- ==========================================================================
--
-- En la Optica esta migracion llega junto con la 031 y no hay nada que
-- trasladar. En las bases de Casa donde la 031 ya corrio si lo hay, y perderlo
-- seria empezar la historia de la politica con un agujero. El id es
-- determinista para que reaplicar no duplique.
INSERT OR IGNORE INTO service_commission_policy_versions(
    id, user_id, branch, job_type, amount, active, effective_from,
    previous_amount, supersedes_id, reason, created_by, created_at)
SELECT
    'migrada-031-' || p.user_id || '-' || p.job_type,
    p.user_id, '', p.job_type, p.amount, 1, p.updated_at,
    NULL, NULL, 'Politica vigente al migrar a la 032',
    CASE WHEN length(trim(p.updated_by)) > 0 THEN p.updated_by ELSE 'migracion-032' END,
    p.updated_at
FROM service_commission_policy p;

-- La tabla vieja se va. Dejarla seria tener dos lugares donde dice cuanto cobra
-- una persona, y el dia que discrepen no habria forma de decir cual manda. Su
-- contenido no se pierde: acaba de quedar como la primera version de cada
-- alcance. No es historia economica -los devengos viven en otra tabla y no se
-- tocan-: es la configuracion, y la configuracion ahora se guarda entera.
DROP TABLE IF EXISTS service_commission_policy;

-- ==========================================================================
-- El asiento dice que politica lo explico
-- ==========================================================================
--
-- El importe ya estaba guardado en el asiento, asi que la plata de agosto nunca
-- estuvo en riesgo. Lo que faltaba era la causa: poder ir del devengo a la
-- version exacta de politica que lo produjo, con su fecha, su actor y su
-- motivo. Sin esto, reconstruir "por que cobro esto" obligaba a inferir la
-- tarifa por la fecha, que es justo la heuristica que no queremos.
--
-- Nullable a proposito: los devengos que la 031 ya produjo no tienen version
-- que referenciar, y no vamos a inventarles una.
ALTER TABLE service_job_commissions
    ADD COLUMN policy_id TEXT REFERENCES service_commission_policy_versions(id);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('032', datetime('now'));

COMMIT;
