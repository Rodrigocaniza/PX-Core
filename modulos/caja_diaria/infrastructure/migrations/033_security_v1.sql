-- BC SEGURIDAD V1 — identidad de instalacion, llavero de datos y auditoria.
--
-- Migracion ESTRICTAMENTE ADITIVA: solo CREATE TABLE/INDEX/TRIGGER IF NOT
-- EXISTS. Ni un ALTER TABLE, ni un UPDATE, ni un DROP. Ninguna tabla de
-- historia economica —ventas, caja, stock, comisiones, pedidos— se nombra en
-- este archivo, y hay una prueba que lee el .sql y lo verifica.
--
-- Aplicarla no cifra nada y no cambia ningun comportamiento: crea tres tablas
-- vacias. La proteccion de datos es un paso posterior, explicito y reversible
-- (`tools/bc_security.py proteger-datos`), que exige respaldo previo.
--
-- Por que las tres tablas viven en la base de Caja y no en un archivo aparte:
--   * el llavero tiene que viajar con la base. Un respaldo restaurado sin su
--     llavero seria un respaldo indescifrable, y eso es perdida de datos.
--     Guardar la DEK envuelta al lado de los datos no la revela: envolverla es
--     precisamente lo que la vuelve inutil sin el secreto de la instalacion o
--     sin la frase de recuperacion.
--   * el estado de lease escrito en la base no se resetea borrando un archivo.
--   * la auditoria de seguridad tiene que sobrevivir a que borren la carpeta
--     de seguridad, que es justo lo que haria alguien probando de clonar.

-- Estado sellado con MAC: lease, marca de agua del reloj, serial de revocacion.
-- El valor no es secreto; lo que importa es que no se pueda editar. Sin el MAC,
-- extender un lease seria abrir un JSON y cambiar una fecha.
CREATE TABLE IF NOT EXISTS security_state (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    mac TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Llavero. Una fila por forma de recuperar la MISMA clave de datos (DEK).
--   wrap_kind='installation' — envuelta con la clave derivada del secreto
--       sellado por el sistema operativo. Es el camino de todos los dias.
--   wrap_kind='recovery'     — envuelta con una clave derivada por scrypt de
--       una frase que se entrega en el enrolamiento y se guarda fuera de linea.
--       Es el unico camino cuando la PC muere o hay que re-enrolar.
-- `wrapped_dek` es criptograma, nunca la clave. `salt` solo aplica a 'recovery'.
CREATE TABLE IF NOT EXISTS security_keyring (
    id TEXT PRIMARY KEY,
    wrap_kind TEXT NOT NULL CHECK(wrap_kind IN ('installation', 'recovery')),
    installation_id TEXT NOT NULL DEFAULT '',
    wrapped_dek TEXT NOT NULL,
    salt TEXT NOT NULL DEFAULT '',
    dek_id TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_security_keyring_activo
    ON security_keyring(dek_id, wrap_kind) WHERE active = 1;

-- Una sola envoltura activa por (dek_id, forma). Dos envolturas activas de la
-- misma DEK por el mismo camino significaria que una de las dos quedo huerfana
-- y nadie sabria cual.
CREATE UNIQUE INDEX IF NOT EXISTS idx_security_keyring_unica
    ON security_keyring(dek_id, wrap_kind) WHERE active = 1;

-- Bitacora de seguridad. Append-only por trigger, igual que el resto de las
-- bitacoras de esta base: una auditoria que se puede reescribir no es una
-- auditoria. Nunca lleva material criptografico; `detail_json` guarda nombres
-- de componentes y conteos, no valores.
CREATE TABLE IF NOT EXISTS security_audit (
    id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    installation_id TEXT NOT NULL DEFAULT '',
    event TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    detail_json TEXT NOT NULL DEFAULT '{}',
    security_schema_version TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_security_audit_momento
    ON security_audit(occurred_at);
CREATE INDEX IF NOT EXISTS idx_security_audit_evento
    ON security_audit(event, occurred_at);

CREATE TRIGGER IF NOT EXISTS security_audit_sin_update
BEFORE UPDATE ON security_audit
BEGIN
    SELECT RAISE(ABORT, 'la bitacora de seguridad no se reescribe');
END;

CREATE TRIGGER IF NOT EXISTS security_audit_sin_delete
BEFORE DELETE ON security_audit
BEGIN
    SELECT RAISE(ABORT, 'la bitacora de seguridad no se borra');
END;

-- El llavero tampoco se borra: una envoltura se desactiva (active=0) y queda.
-- Borrar la unica envoltura util de una DEK es perder la base entera.
CREATE TRIGGER IF NOT EXISTS security_keyring_sin_delete
BEFORE DELETE ON security_keyring
BEGIN
    SELECT RAISE(ABORT, 'una envoltura del llavero se desactiva, no se borra');
END;
