PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

-- BC-OPTICA-USUARIOS-ROLES-V1-019, slice 19.
--
-- La lista de personas ya existia a medias y en dos lugares distintos:
-- `admin_users`, con credenciales reales -PBKDF2, sal, bloqueo por intentos- y
-- una columna `role` que nadie leia; y `authorized_responsibles`, creada por la
-- 015 y nunca usada por una sola linea de codigo.
--
-- Y en el medio, la lista que de verdad se usaba todos los dias estaba cableada
-- en la pantalla: «Ana», «Belén», «Carla», «Diana». Cuatro nombres inventados
-- para una maqueta que quedaron eligiendo la vendedora de cada venta real.
--
-- Esta migracion no crea una tercera lista. Le termina de dar a `admin_users`
-- lo que le falta para ser la unica: como se llama la persona, en que sucursal
-- trabaja, y quien la dio de alta.

-- ==========================================================================
-- Como se llama, donde trabaja, quien la cargo
-- ==========================================================================
--
-- `username` es la identidad para entrar; `display_name` es como se la nombra
-- en una venta. No son lo mismo y por eso son dos columnas: la vendedora de una
-- venta es un dato del hecho, no del login de quien estaba en la caja.
ALTER TABLE admin_users ADD COLUMN display_name TEXT NOT NULL DEFAULT '';

-- Sucursal en la que trabaja. Vacio significa «todas», que es lo que
-- corresponde a quien administra. No se inventa un catalogo: son los mismos
-- nombres que ya usa `cash_register_branches`.
ALTER TABLE admin_users ADD COLUMN branch TEXT NOT NULL DEFAULT '';

-- Quien la dio de alta y quien la toco por ultima vez. La bitacora de
-- `admin_audit_log` guarda cada cambio con su motivo; esto es el atajo para
-- responder «¿quien cargo a esta persona?» sin recorrer la bitacora entera.
ALTER TABLE admin_users ADD COLUMN created_by TEXT NOT NULL DEFAULT '';
ALTER TABLE admin_users ADD COLUMN updated_by TEXT NOT NULL DEFAULT '';

-- El administrador que ya existe se queda como esta, y ahora tiene nombre: el
-- suyo. No se inventa uno.
UPDATE admin_users SET display_name = username WHERE display_name = '';

CREATE INDEX IF NOT EXISTS idx_admin_users_activos
    ON admin_users(active, role);

-- ==========================================================================
-- Lo que NO se toca
-- ==========================================================================
--
-- `role` ya existia con DEFAULT 'ADMIN', asi que el administrador que hoy entra
-- al panel sigue siendo ADMIN sin que nadie lo actualice. Esa es la razon de no
-- agregar una columna nueva para el rol: la que hay ya dice la verdad.
--
-- `password_hash`, `salt` e `iterations` siguen NOT NULL y no se relajan. Una
-- persona sin credencial se guarda con el hash vacio, que no puede coincidir
-- con ningun PBKDF2: existe para ser nombrada en una venta y para tener rol,
-- pero no puede entrar. Esa es exactamente la diferencia entre este slice y el
-- login de operadora, que es otra mision.
--
-- `authorized_responsibles` se deja donde esta. Esta vacia y sin usar desde la
-- 015; borrarla es una limpieza de esquema que no le urge a nadie y que no
-- corresponde meter en la misma migracion que agrega usuarios.
--
-- Ninguna venta, ningun movimiento, ninguna caja y ningun trabajo de
-- Seguimiento se tocan. `cash_entries.saleswoman` sigue siendo el texto que se
-- guardo el dia de la venta, y sigue sin ser una foreign key a proposito: si
-- manana se corrige el nombre de una persona, agosto no se reescribe.

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('030', datetime('now'));

COMMIT;
