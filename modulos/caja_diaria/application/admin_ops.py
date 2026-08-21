"""Seguridad administrativa, arqueos tipados y outbox durable de RC.13."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import smtplib
import ssl
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from ..domain.errors import CashDayClosedError, CashDayNotFoundError, InvalidCashDayError
from ..domain.models import CashDay, DENOMINATIONS, parse_business_date, utc_now


UTC = timezone.utc
PBKDF2_ITERATIONS = 390_000


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid.uuid4())


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _quantities(values: Mapping[int, int]) -> tuple[dict[int, int], int]:
    normalized = {}
    for denomination, quantity in values.items():
        denomination = int(denomination)
        if denomination not in DENOMINATIONS or isinstance(quantity, bool) or int(quantity) < 0:
            raise InvalidCashDayError("El conteo contiene una denominación o cantidad inválida.")
        normalized[denomination] = int(quantity)
    return normalized, sum(key * value for key, value in normalized.items())


#: Los dos roles del producto. Dos alcanzan para lo que la Optica necesita: la
#: que atiende y la que administra. Un tercero solo tendria sentido el dia que
#: exista una responsabilidad que hoy no existe.
ROL_ADMIN = "ADMIN"
ROL_OPERADOR = "OPERADOR"
ROLES = (ROL_OPERADOR, ROL_ADMIN)

ETIQUETA_ROL = {ROL_OPERADOR: "Operadora", ROL_ADMIN: "Administradora"}


@dataclass(frozen=True)
class AdminSession:
    token: str
    username: str
    expires_at: datetime
    role: str = ROL_ADMIN

    @property
    def is_admin(self) -> bool:
        return self.role == ROL_ADMIN


@dataclass(frozen=True)
class CashSession:
    """Quien esta operando la caja, para toda la jornada.

    Es distinta de `AdminSession` a proposito, y la diferencia esta en cuanto
    dura. La administrativa vence a los 20 minutos porque protege cosas que se
    hacen una vez y con cuidado. Esta acompana a una persona que atiende ocho
    horas seguidas: pedirle la contrasena cada 20 minutos seria pedirle que la
    deje anotada en un papel al lado de la pantalla.

    Vence al terminar el dia. Abrir a la manana, trabajar, y que la sesion no
    sobreviva a la noche es lo que hace una caja.
    """

    token: str
    user_id: str
    username: str
    display_name: str
    role: str
    branch: str
    started_at: datetime
    expires_at: datetime

    @property
    def is_admin(self) -> bool:
        return self.role == ROL_ADMIN

    def etiqueta(self, sucursal_efectiva: str = "") -> str:
        """Lo que la pantalla muestra: «Operando: Leti · ASUNCION»."""
        lugar = sucursal_efectiva or self.branch
        return f"{self.display_name} · {lugar}" if lugar else self.display_name


@dataclass(frozen=True)
class Usuario:
    """Una persona autorizada a estar en BC Caja.

    `username` es con lo que entra; `display_name` es como se la nombra en una
    venta. Una operadora normalmente no tiene con que entrar —eso es el login de
    operadora, que es otra mision— y existe para tener rol y para poder ser la
    vendedora de una venta.
    """

    id: str
    username: str
    display_name: str
    role: str
    active: bool
    branch: str = ""
    created_by: str = ""
    created_at: str = ""
    updated_by: str = ""
    updated_at: str = ""
    puede_entrar: bool = False

    @property
    def etiqueta_rol(self) -> str:
        return ETIQUETA_ROL.get(self.role, self.role)


@dataclass(frozen=True)
class CountResult:
    id: str
    cash_day_id: str
    count_type: str
    quantities: dict[int, int]
    counted_total: int
    expected_total: int | None
    difference: int | None
    reason: str
    responsible: str
    recorded_at: datetime


class DPAPISecretStore:
    """Blob CurrentUser fuera de SQLite; nunca devuelve ni registra secretos crudos."""

    def __init__(self, root: Path):
        self.root = root / "Secrets"

    def _path(self, name: str) -> Path:
        safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_")
        if not safe:
            raise ValueError("referencia de secreto inválida")
        return self.root / f"{safe}.dpapi"

    @staticmethod
    def _crypt(data: bytes, protect: bool) -> bytes:
        if os.name != "nt":
            raise RuntimeError("DPAPI CurrentUser sólo está disponible en Windows")
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        buffer = ctypes.create_string_buffer(data)
        source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        target = Blob()
        function = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
        if protect:
            ok = function(ctypes.byref(source), "BC Caja SMTP", None, None, None, 0, ctypes.byref(target))
        else:
            ok = function(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target))
        if not ok:
            raise OSError("Windows no pudo proteger la credencial")
        try:
            return ctypes.string_at(target.pbData, target.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(target.pbData)

    def set(self, name: str, secret: str) -> None:
        if not secret:
            raise ValueError("secreto vacío")
        self.root.mkdir(parents=True, exist_ok=True)
        protected = self._crypt(secret.encode("utf-8"), True)
        destination = self._path(name)
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(base64.b64encode(protected))
        temporary.replace(destination)

    def get(self, name: str) -> str | None:
        path = self._path(name)
        if not path.exists():
            return None
        return self._crypt(base64.b64decode(path.read_bytes()), False).decode("utf-8")

    def configured(self, name: str) -> bool:
        return self._path(name).is_file()


class AdminOperations:
    SETTINGS = {"counting", "branch", "mail"}

    def __init__(self, repository, data_root: Path):
        self.repository = repository
        self.data_root = Path(data_root)
        self.secret_store = DPAPISecretStore(self.data_root)
        self._sessions: dict[str, AdminSession] = {}
        #: Las sesiones de caja viven aparte de las administrativas. Mezclarlas
        #: haria que la de la jornada le preste su duracion a la sensible.
        self._cash_sessions: dict[str, CashSession] = {}

    def _audit(self, connection, actor: str, action: str, target_type: str,
               result: str, target_id: str = "", details=None) -> None:
        connection.execute(
            "INSERT INTO admin_audit_log(id,actor,action,target_type,target_id,result,details_json,recorded_at) VALUES(?,?,?,?,?,?,?,?)",
            (_id(), actor or "UNKNOWN", action, target_type, target_id, result,
             _json(details or {}), _now().isoformat()),
        )

    def has_admin(self) -> bool:
        with self.repository._connection() as connection:
            return connection.execute("SELECT 1 FROM admin_users WHERE active=1 LIMIT 1").fetchone() is not None

    def create_initial_admin(self, username: str, password: str) -> AdminSession:
        username = str(username).strip()
        if len(username) < 3 or len(password) < 10:
            raise InvalidCashDayError("Use un administrador y una contraseña de al menos 10 caracteres.")
        salt = secrets.token_bytes(24)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        now = _now().isoformat()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM admin_users LIMIT 1").fetchone():
                connection.rollback()
                raise InvalidCashDayError("La credencial administrativa ya fue configurada.")
            connection.execute(
                "INSERT INTO admin_users(id,username,password_hash,salt,iterations,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (_id(), username, base64.b64encode(digest).decode(), base64.b64encode(salt).decode(),
                 PBKDF2_ITERATIONS, now, now),
            )
            self._audit(connection, username, "ADMIN_BOOTSTRAP", "admin_user", "SUCCESS")
            connection.commit()
        return self.authenticate(username, password)

    def authenticate(self, username: str, password: str) -> AdminSession:
        username = str(username).strip()
        now = _now()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM admin_users WHERE username=? COLLATE NOCASE AND active=1", (username,)
            ).fetchone()
            locked = row and row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > now
            valid = False
            if row and not locked:
                actual = hashlib.pbkdf2_hmac(
                    "sha256", password.encode("utf-8"), base64.b64decode(row["salt"]), row["iterations"]
                )
                valid = hmac.compare_digest(actual, base64.b64decode(row["password_hash"]))
            if not valid:
                if row and not locked:
                    failures = row["failed_attempts"] + 1
                    delay = min(900, 2 ** min(failures, 10))
                    connection.execute(
                        "UPDATE admin_users SET failed_attempts=?,locked_until=?,updated_at=? WHERE id=?",
                        (failures, (now + timedelta(seconds=delay)).isoformat(), now.isoformat(), row["id"]),
                    )
                self._audit(connection, username or "UNKNOWN", "ADMIN_LOGIN", "session",
                            "LOCKED" if locked else "FAIL")
                connection.commit()
                raise InvalidCashDayError("Credenciales inválidas o acceso temporalmente bloqueado.")
            connection.execute(
                "UPDATE admin_users SET failed_attempts=0,locked_until=NULL,updated_at=? WHERE id=?",
                (now.isoformat(), row["id"]),
            )
            self._audit(connection, row["username"], "ADMIN_LOGIN", "session", "SUCCESS")
            connection.commit()
        session = AdminSession(
            secrets.token_urlsafe(32), row["username"], now + timedelta(minutes=20),
            role=(row["role"] or ROL_ADMIN))
        self._sessions[session.token] = session
        return session

    def require(self, token: str) -> AdminSession:
        session = self._sessions.get(token)
        if session is None or session.expires_at <= _now():
            self._sessions.pop(token, None)
            raise InvalidCashDayError("La sesión administrativa venció.")
        return session

    def require_admin(self, token: str) -> AdminSession:
        """Ademas de tener sesion, tener el rol.

        Antes bastaba con haber entrado: como todos los usuarios eran ADMIN por
        defecto, tener sesion y ser administradora eran lo mismo. Desde que hay
        dos roles dejan de serlo, y lo sensible tiene que preguntar por el rol y
        no solo por la sesion. La comprobacion vive aca y no en la pantalla:
        esconder un boton no impide llamar al metodo.
        """
        session = self.require(token)
        if not session.is_admin:
            with self.repository._connection() as connection:
                self._audit(connection, session.username, "ADMIN_DENIED", "session",
                            "DENIED", details={"role": session.role})
                connection.commit()
            raise InvalidCashDayError(
                "Esta acción es de una administradora, y esta sesión no lo es.")
        return session

    # -- sesion de caja ----------------------------------------------------

    @staticmethod
    def _fin_de_jornada(momento: datetime) -> datetime:
        """La medianoche siguiente, en la hora de la Optica.

        No es un numero de minutos elegido a ojo: es el limite natural del
        turno. Una caja se abre a la manana y se cierra a la noche, y una sesion
        que sobrevive a la noche es una caja que quedo abierta.
        """
        siguiente = momento.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return siguiente

    def authenticate_operator(self, username: str, password: str) -> CashSession:
        """Entra a operar la caja. Misma credencial, distinta sesion.

        Reusa `authenticate`, que es donde viven PBKDF2, la sal, el bloqueo
        exponencial y la bitacora de login. Este metodo no valida contrasenas:
        pide que las valide quien ya sabe hacerlo.
        """
        administrativa = self.authenticate(username, password)
        with self.repository._connection() as connection:
            fila = connection.execute(
                "SELECT * FROM admin_users WHERE username=? COLLATE NOCASE",
                (administrativa.username,)).fetchone()
        usuario = self._fila_a_usuario(fila)
        ahora = _now()
        sesion = CashSession(
            token=secrets.token_urlsafe(32), user_id=usuario.id,
            username=usuario.username, display_name=usuario.display_name,
            role=usuario.role, branch=usuario.branch,
            started_at=ahora, expires_at=self._fin_de_jornada(ahora))
        self._cash_sessions[sesion.token] = sesion
        # La sesion administrativa que se creo de paso no se conserva: entrar a
        # atender no puede dejar abierta, en la sombra, una sesion que autoriza
        # cosas sensibles. Para eso hay que volver a identificarse.
        self._sessions.pop(administrativa.token, None)
        with self.repository._connection() as connection:
            self._audit(connection, usuario.username, "CASH_LOGIN_SUCCESS", "cash_session",
                        "SUCCESS", usuario.id,
                        {"display_name": usuario.display_name, "role": usuario.role,
                         "branch": usuario.branch})
            connection.commit()
        return sesion

    def require_operator(self, token: str) -> CashSession:
        """La sesion de caja vigente, o el motivo por el que ya no lo es.

        Comprueba tres cosas, y las tres importan: que exista, que no haya
        vencido, y que la persona siga activa. Lo tercero se pregunta a la base
        en cada llamada a proposito: desactivar a alguien tiene que sacarla de
        la caja aunque ya estuviera adentro.
        """
        sesion = self._cash_sessions.get(token)
        if sesion is None:
            raise InvalidCashDayError("No hay ninguna sesión de caja abierta.")
        if sesion.expires_at <= _now():
            self._cash_sessions.pop(token, None)
            with self.repository._connection() as connection:
                self._audit(connection, sesion.username, "CASH_SESSION_EXPIRED",
                            "cash_session", "EXPIRED", sesion.user_id)
                connection.commit()
            raise InvalidCashDayError("La sesión de caja venció. Volvé a entrar.")
        with self.repository._connection() as connection:
            activa = connection.execute(
                "SELECT active FROM admin_users WHERE id=?", (sesion.user_id,)).fetchone()
        if activa is None or not activa["active"]:
            self._cash_sessions.pop(token, None)
            raise InvalidCashDayError(
                f"{sesion.display_name} ya no está activa. Entrá con otra cuenta.")
        return sesion

    def logout_operator(self, token: str, *, reason: str = "") -> None:
        """Cierra la sesion. No cierra la caja ni el arqueo: son otra cosa."""
        sesion = self._cash_sessions.pop(token, None)
        if sesion is None:
            return
        with self.repository._connection() as connection:
            self._audit(connection, sesion.username, "CASH_LOGOUT", "cash_session",
                        "SUCCESS", sesion.user_id,
                        {"motivo": str(reason or "").strip()})
            connection.commit()

    def switch_operator(self, token: str, username: str, password: str) -> CashSession:
        """Cambia de persona sin tocar la caja del dia.

        El arqueo pertenece a la caja y a la sucursal, no a quien esta parada
        adelante. Cambiar de operadora a media tarde no puede cerrar nada ni
        obligar a arquear: es un relevo, no un cierre.
        """
        anterior = self._cash_sessions.get(token)
        nueva = self.authenticate_operator(username, password)
        self._cash_sessions.pop(token, None)
        with self.repository._connection() as connection:
            self._audit(
                connection, nueva.username, "CASH_OPERATOR_CHANGED", "cash_session",
                "SUCCESS", nueva.user_id,
                {"salio": anterior.username if anterior else "",
                 "salio_nombre": anterior.display_name if anterior else "",
                 "entro": nueva.username, "entro_nombre": nueva.display_name})
            connection.commit()
        return nueva

    def audit_saleswoman_override(self, token: str, saleswoman: str, *,
                                  envelope: str = "") -> None:
        """Deja constancia de que la venta la hizo otra persona.

        Pasa de verdad: una administrativa carga la venta que hizo otra chica.
        El dato correcto es el de quien vendio, y esta bien que se pueda elegir.
        Lo que no puede pasar es que nadie se entere de que quien cargo y quien
        vendio no son la misma.
        """
        sesion = self.require_operator(token)
        elegida = str(saleswoman or "").strip()
        if not elegida or elegida == sesion.display_name:
            return
        with self.repository._connection() as connection:
            self._audit(connection, sesion.username, "SALESWOMAN_OVERRIDE", "cash_entry",
                        "SUCCESS", envelope,
                        {"cargo": sesion.display_name, "vendio": elegida})
            connection.commit()

    def effective_branch(self, token: str, host_branch: str | None) -> dict:
        """La sucursal en la que se esta operando, y si hay que avisar algo.

        La sucursal efectiva es **la de la caja**, no la de la persona: la
        determina `cash_register_branches`, que es donde ya vive esa verdad. El
        `branch` del usuario es su ambito habitual, no una autorizacion.

        Cuando no coinciden no se corrige nada en silencio: se devuelve el aviso
        para que alguien lo mire. Corregirlo solo seria decidir por la Optica
        cual de los dos datos esta mal.
        """
        sesion = self.require_operator(token)
        efectiva = str(host_branch or "").strip().upper()
        propia = (sesion.branch or "").strip().upper()
        discrepa = bool(efectiva and propia and efectiva != propia)
        return {
            "branch": efectiva or propia,
            "user_branch": propia,
            "host_branch": efectiva,
            "mismatch": discrepa,
            "aviso": (f"{sesion.display_name} figura en {propia} y esta caja es de "
                      f"{efectiva}." if discrepa else ""),
        }

    # -- usuarios y roles --------------------------------------------------

    @staticmethod
    def _fila_a_usuario(row) -> "Usuario":
        return Usuario(
            id=row["id"], username=row["username"],
            display_name=row["display_name"] or row["username"],
            role=row["role"] or ROL_ADMIN, active=bool(row["active"]),
            branch=row["branch"] or "", created_by=row["created_by"] or "",
            created_at=row["created_at"], updated_by=row["updated_by"] or "",
            updated_at=row["updated_at"],
            puede_entrar=bool(row["password_hash"]))

    def list_users(self, token: str, *, only_active: bool = False) -> list["Usuario"]:
        self.require_admin(token)
        consulta = "SELECT * FROM admin_users"
        if only_active:
            consulta += " WHERE active=1"
        consulta += " ORDER BY active DESC, display_name COLLATE NOCASE, username COLLATE NOCASE"
        with self.repository._connection() as connection:
            filas = connection.execute(consulta).fetchall()
        return [self._fila_a_usuario(fila) for fila in filas]

    def active_salespeople(self) -> list[str]:
        """Los nombres que puede elegir la venta. Sin sesion, a proposito.

        La caja necesita esta lista para llenar el desplegable de vendedora, y
        pedir una sesion administrativa para eso seria pedirle a la operadora
        que sea administradora. Es de solo lectura y no expone nada: son los
        nombres que la venta ya va a guardar en texto.
        """
        with self.repository._connection() as connection:
            filas = connection.execute(
                "SELECT display_name, username FROM admin_users WHERE active=1"
                " ORDER BY display_name COLLATE NOCASE").fetchall()
        return [(fila["display_name"] or fila["username"]) for fila in filas]

    def create_user(self, token: str, *, username: str, display_name: str,
                    role: str = ROL_OPERADOR, branch: str = "",
                    password: str | None = None) -> "Usuario":
        """Da de alta una persona. Sin contraseña no puede entrar, y está bien.

        Una operadora existe para tener rol y para poder ser la vendedora de una
        venta; entrar al sistema es otra cosa y hoy no la necesita. Cuando haga
        falta, se le pone contraseña y ya puede.
        """
        session = self.require_admin(token)
        usuario = str(username or "").strip()
        nombre = str(display_name or "").strip() or usuario
        rol = str(role or "").strip().upper()
        if len(usuario) < 3:
            raise InvalidCashDayError("El usuario necesita al menos 3 caracteres.")
        if rol not in ROLES:
            raise InvalidCashDayError(f"Rol desconocido: {role}")
        if password is not None and len(password) < 10:
            raise InvalidCashDayError("La contraseña necesita al menos 10 caracteres.")
        salt = secrets.token_bytes(24)
        # Sin contraseña el hash queda vacio, y un hash vacio no puede coincidir
        # con ningun PBKDF2: la persona existe y no puede entrar.
        digest = (hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                      PBKDF2_ITERATIONS) if password else b"")
        ahora = _now().isoformat()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existente = connection.execute(
                "SELECT username FROM admin_users WHERE username=? COLLATE NOCASE",
                (usuario,)).fetchone()
            if existente:
                connection.rollback()
                raise InvalidCashDayError(
                    f"Ya existe un usuario «{existente['username']}».")
            identificador = _id()
            connection.execute(
                "INSERT INTO admin_users(id,username,password_hash,salt,iterations,role,"
                "active,display_name,branch,created_by,updated_by,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,1,?,?,?,?,?,?)",
                (identificador, usuario, base64.b64encode(digest).decode(),
                 base64.b64encode(salt).decode(), PBKDF2_ITERATIONS, rol, nombre,
                 str(branch or "").strip().upper(), session.username, session.username,
                 ahora, ahora))
            self._audit(connection, session.username, "USER_CREATED", "admin_user",
                        "SUCCESS", identificador,
                        {"username": usuario, "display_name": nombre, "role": rol,
                         "branch": branch, "puede_entrar": bool(password)})
            connection.commit()
        return self.get_user(token, identificador)

    def get_user(self, token: str, user_id: str) -> "Usuario":
        self.require_admin(token)
        with self.repository._connection() as connection:
            fila = connection.execute(
                "SELECT * FROM admin_users WHERE id=?", (user_id,)).fetchone()
        if fila is None:
            raise InvalidCashDayError("Ese usuario no existe.")
        return self._fila_a_usuario(fila)

    def update_user(self, token: str, user_id: str, *, display_name: str | None = None,
                    role: str | None = None, branch: str | None = None) -> "Usuario":
        """Modificacion parcial: cambia lo que se nombra y deja el resto quieto."""
        session = self.require_admin(token)
        antes = self.get_user(token, user_id)
        cambios: dict[str, object] = {}
        if display_name is not None:
            nombre = str(display_name).strip()
            if not nombre:
                raise InvalidCashDayError("El nombre no puede quedar vacío.")
            cambios["display_name"] = nombre
        if role is not None:
            rol = str(role).strip().upper()
            if rol not in ROLES:
                raise InvalidCashDayError(f"Rol desconocido: {role}")
            cambios["role"] = rol
        if branch is not None:
            cambios["branch"] = str(branch).strip().upper()
        if not cambios:
            return antes
        ahora = _now().isoformat()
        asignaciones = ", ".join(f"{campo}=?" for campo in cambios)
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"UPDATE admin_users SET {asignaciones}, updated_by=?, updated_at=? WHERE id=?",
                (*cambios.values(), session.username, ahora, user_id))
            detalle = {"username": antes.username}
            if "role" in cambios:
                detalle.update(rol_anterior=antes.role, rol_nuevo=cambios["role"])
            if "display_name" in cambios:
                detalle.update(nombre_anterior=antes.display_name,
                               nombre_nuevo=cambios["display_name"])
            if "branch" in cambios:
                detalle.update(sucursal_anterior=antes.branch,
                               sucursal_nueva=cambios["branch"])
            self._audit(connection, session.username, "USER_UPDATED", "admin_user",
                        "SUCCESS", user_id, detalle)
            connection.commit()
        return self.get_user(token, user_id)

    def set_user_active(self, token: str, user_id: str, active: bool, *,
                        reason: str = "") -> "Usuario":
        """Baja logica. Nunca se borra: la historia la nombra.

        Una venta de agosto guarda el nombre de quien la hizo en texto. Borrar a
        la persona no borraria ese texto -quedaria un nombre sin nadie detras- y
        si en cambio se reusara el `id`, la historia empezaria a apuntar a otra
        persona. Desactivar deja las dos cosas en su lugar.
        """
        session = self.require_admin(token)
        antes = self.get_user(token, user_id)
        if antes.active == bool(active):
            return antes
        if not active and antes.role == ROL_ADMIN:
            with self.repository._connection() as connection:
                quedan = connection.execute(
                    "SELECT COUNT(*) FROM admin_users WHERE active=1 AND role=?"
                    " AND id<>? AND LENGTH(password_hash)>0",
                    (ROL_ADMIN, user_id)).fetchone()[0]
            if not quedan:
                # Dejar la Optica sin ninguna administradora que pueda entrar es
                # quedarse afuera del panel sin forma de volver.
                raise InvalidCashDayError(
                    "Es la única administradora que puede entrar."
                    " Dejá otra antes de desactivarla.")
        ahora = _now().isoformat()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE admin_users SET active=?, failed_attempts=0, locked_until=NULL,"
                " updated_by=?, updated_at=? WHERE id=?",
                (1 if active else 0, session.username, ahora, user_id))
            self._audit(connection, session.username,
                        "USER_ACTIVATED" if active else "USER_DEACTIVATED",
                        "admin_user", "SUCCESS", user_id,
                        {"username": antes.username, "motivo": str(reason or "").strip()})
            connection.commit()
        return self.get_user(token, user_id)

    def set_user_password(self, token: str, user_id: str, password: str) -> "Usuario":
        """Le da —o le cambia— con qué entrar. Nunca guarda la contraseña."""
        session = self.require_admin(token)
        antes = self.get_user(token, user_id)
        if len(password or "") < 10:
            raise InvalidCashDayError("La contraseña necesita al menos 10 caracteres.")
        salt = secrets.token_bytes(24)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                     PBKDF2_ITERATIONS)
        ahora = _now().isoformat()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE admin_users SET password_hash=?, salt=?, iterations=?,"
                " failed_attempts=0, locked_until=NULL, updated_by=?, updated_at=? WHERE id=?",
                (base64.b64encode(digest).decode(), base64.b64encode(salt).decode(),
                 PBKDF2_ITERATIONS, session.username, ahora, user_id))
            self._audit(connection, session.username, "USER_PASSWORD_SET", "admin_user",
                        "SUCCESS", user_id, {"username": antes.username})
            connection.commit()
        return self.get_user(token, user_id)

    def setting(self, key: str) -> dict:
        if key not in self.SETTINGS:
            raise KeyError(key)
        with self.repository._connection() as connection:
            row = connection.execute("SELECT value_json FROM app_settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value_json"]) if row else {}

    def update_setting(self, token: str, key: str, value: dict) -> None:
        session = self.require_admin(token)
        if key not in self.SETTINGS:
            raise InvalidCashDayError("Configuración no permitida.")
        safe = dict(value)
        for forbidden in ("password", "secret", "token", "pin"):
            if any(forbidden in str(item).lower() for item in safe if item != "secret_ref"):
                raise InvalidCashDayError("Los secretos deben guardarse en el almacén protegido.")
        now = _now().isoformat()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO app_settings(key,value_json,updated_by,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                (key, _json(safe), session.username, now),
            )
            self._audit(connection, session.username, "SETTING_UPDATE", "app_setting", "SUCCESS", key)
            connection.commit()

    def set_mail_secret(self, token: str, secret: str) -> None:
        session = self.require_admin(token)
        self.secret_store.set("smtp", secret)
        with self.repository._connection() as connection:
            self._audit(connection, session.username, "MAIL_SECRET_UPDATE", "credential", "SUCCESS", "smtp")
            connection.commit()

    def register_import(self, token: str, file_path: Path, summary, unit: str) -> str:
        session = self.require_admin(token)
        digest = hashlib.sha256()
        with Path(file_path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result = "SUCCESS" if not getattr(summary, "errors", 0) else "PARTIAL"
        run_id = _id()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO import_runs(id,administrator,file_name,file_sha256,unit,rows_processed,rows_imported,rows_skipped,error_count,result,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, session.username, Path(file_path).name, digest.hexdigest(), unit,
                 getattr(summary, "entries", 0), getattr(summary, "entries", 0), 0,
                 getattr(summary, "errors", 0), result, _now().isoformat()),
            )
            self._audit(connection, session.username, "EXCEL_IMPORT", "import_run", result, run_id,
                        {"file": Path(file_path).name, "sha256": digest.hexdigest(), "rows": getattr(summary, "entries", 0)})
            connection.commit()
        return run_id

    def audit_rows(self, token: str, limit: int = 100):
        self.require_admin(token)
        with self.repository._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT actor,action,target_type,target_id,result,details_json,recorded_at"
                " FROM admin_audit_log ORDER BY recorded_at DESC LIMIT ?",
                (int(limit),),
            )]

    def open_from_count(self, business_date: str, unit: str, quantities: Mapping[int, int],
                        responsible: str, operation_id: str) -> CashDay:
        values, total = _quantities(quantities)
        parsed = parse_business_date(business_date)
        unit = unit.strip().upper()
        responsible = responsible.strip() or f"Caja {unit}"
        day_id, count_id, now = _id(), _id(), utc_now()
        key = f"opening:{operation_id}"
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT id FROM cash_days WHERE business_date=? AND unit=?", (parsed.isoformat(), unit)
            ).fetchone()
            if existing:
                connection.rollback()
                return self.repository.get(existing["id"])
            connection.execute(
                "INSERT INTO cash_days(id,business_date,unit,opening_cash,status,opened_at,version,opened_by,initial_cash_source_kind) VALUES(?,?,?,?,?,?,?,?,?)",
                (day_id, parsed.isoformat(), unit, total, "OPEN", now.isoformat(), 0, responsible, "OPENING_COUNT"),
            )
            connection.execute(
                "INSERT INTO cash_count_snapshots(id,cash_day_id,count_type,sequence,quantities_json,counted_total,expected_total,difference,reason,responsible,status,idempotency_key,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (count_id, day_id, "OPENING", 1, _json(values), total, total, 0, "", responsible,
                 "CONFIRMED", key, now.isoformat()),
            )
            self._audit(connection, responsible, "CASH_OPEN", "cash_day", "SUCCESS", day_id,
                        {"count_id": count_id, "total": total})
            connection.commit()
        return self.repository.get(day_id)

    def record_count(self, cash_day_id: str, count_type: str, quantities: Mapping[int, int],
                     responsible: str, operation_id: str, reason: str = "") -> CountResult:
        values, total = _quantities(quantities)
        if count_type != "INTERMEDIATE":
            raise InvalidCashDayError("Tipo de arqueo inválido.")
        key = f"intermediate:{operation_id}"
        now = utc_now()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM cash_count_snapshots WHERE idempotency_key=?", (key,)
            ).fetchone()
            if existing:
                connection.rollback()
                return self._count(existing)
            day = connection.execute("SELECT status FROM cash_days WHERE id=?", (cash_day_id,)).fetchone()
            if not day:
                connection.rollback(); raise CashDayNotFoundError(cash_day_id)
            if day["status"] != "OPEN":
                connection.rollback(); raise CashDayClosedError("la Caja está cerrada")
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM cash_count_snapshots WHERE cash_day_id=? AND count_type='INTERMEDIATE'",
                (cash_day_id,),
            ).fetchone()[0]
            snapshot_id = _id()
            connection.execute(
                "INSERT INTO cash_count_snapshots(id,cash_day_id,count_type,sequence,quantities_json,counted_total,expected_total,difference,reason,responsible,status,idempotency_key,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (snapshot_id, cash_day_id, "INTERMEDIATE", sequence, _json(values), total, None, None,
                 reason.strip(), responsible.strip(), "CONFIRMED", key, now.isoformat()),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM cash_count_snapshots WHERE id=?", (snapshot_id,)).fetchone()
        return self._count(row)

    @staticmethod
    def _count(row) -> CountResult:
        return CountResult(row["id"], row["cash_day_id"], row["count_type"],
                           {int(k): int(v) for k, v in json.loads(row["quantities_json"]).items()},
                           row["counted_total"], row["expected_total"], row["difference"],
                           row["reason"], row["responsible"], datetime.fromisoformat(row["recorded_at"]))

    def close_with_count(self, cash_day_id: str, quantities: Mapping[int, int], responsible: str,
                         operation_id: str, reason: str = "", admin_token: str = "") -> tuple[CashDay, CountResult, str]:
        values, counted = _quantities(quantities)
        key = f"closing:{operation_id}"
        with self.repository._connection() as connection:
            existing = connection.execute(
                "SELECT id FROM cash_count_snapshots WHERE idempotency_key=?", (key,)
            ).fetchone()
        if existing:
            return self.repository.get(cash_day_id), self._count_by_id(existing["id"]), self.mail_status(cash_day_id)
        day = self.repository.get(cash_day_id)
        if day is None:
            raise CashDayNotFoundError(cash_day_id)
        totals = day.totals()
        difference = counted - totals.expected_cash
        policy = self.setting("counting")
        tolerance = int(policy.get("tolerance", 0))
        require_reason = policy.get("reason_mode", "ANY_DIFFERENCE") == "ANY_DIFFERENCE" and difference != 0
        require_reason = require_reason or abs(difference) > tolerance
        if require_reason and not reason.strip():
            raise InvalidCashDayError("El motivo de la diferencia es obligatorio.")
        admin_limit = int(policy.get("admin_limit", 0))
        if admin_limit > 0 and abs(difference) > admin_limit:
            self.require_admin(admin_token)
        closed_at = utc_now()
        day.close(closed_at=closed_at)
        count_id, closure_id = _id(), _id()
        outbox_key = f"cash-close:{cash_day_id}:v1"
        mail = self.setting("mail")
        mail_status = "PENDING" if mail.get("enabled") and mail.get("recipient") else "NOT_CONFIGURED"
        report_path = str(self.data_root / "Reports" / f"cierre-{closure_id}.pdf")
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT id FROM cash_count_snapshots WHERE idempotency_key=?", (key,)).fetchone()
            if existing:
                connection.rollback()
                existing_day = self.repository.get(cash_day_id)
                return existing_day, self._count_by_id(existing["id"]), self.mail_status(cash_day_id)
            cursor = connection.execute(
                "UPDATE cash_days SET status='CLOSED',closed_at=?,closing_total=?,closing_cash=?,closing_card_check=?,closing_expenses=?,closing_expected_cash=?,closing_entry_count=?,closing_withdrawals=?,session_duration_seconds=?,overtime_triggered=?,overtime_minutes=?,version=version+1 WHERE id=? AND status='OPEN'",
                (closed_at.isoformat(), totals.total, totals.cash, totals.card_check, totals.expenses,
                 totals.expected_cash, totals.entry_count, totals.withdrawals, day.session_duration_seconds,
                 None if day.overtime_triggered is None else int(day.overtime_triggered), day.overtime_minutes, cash_day_id),
            )
            if cursor.rowcount != 1:
                connection.rollback(); raise CashDayClosedError("la Caja ya fue cerrada")
            connection.execute(
                "INSERT INTO cash_count_snapshots(id,cash_day_id,count_type,sequence,quantities_json,counted_total,expected_total,difference,reason,responsible,status,idempotency_key,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (count_id, cash_day_id, "CLOSING", 1, _json(values), counted, totals.expected_cash,
                 difference, reason.strip(), responsible.strip(), "CONFIRMED", key, closed_at.isoformat()),
            )
            connection.execute(
                "INSERT INTO mail_outbox(id,cash_day_id,closure_id,idempotency_key,report_path,recipient,subject,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (_id(), cash_day_id, closure_id, outbox_key, report_path, str(mail.get("recipient", "")),
                 self._subject(mail, day), mail_status, closed_at.isoformat(), closed_at.isoformat()),
            )
            self._audit(connection, responsible, "CASH_CLOSE", "cash_day", "SUCCESS", cash_day_id,
                        {"closure_id": closure_id, "difference": difference, "count_id": count_id})
            connection.commit()
        closed = self.repository.get(cash_day_id)
        count = self._count_by_id(count_id)
        self.generate_close_pdf(closed, count, closure_id, Path(report_path))
        if mail_status == "PENDING":
            self.process_outbox(limit=1)
        return closed, count, self.mail_status(cash_day_id)

    def _count_by_id(self, count_id: str) -> CountResult:
        with self.repository._connection() as connection:
            row = connection.execute("SELECT * FROM cash_count_snapshots WHERE id=?", (count_id,)).fetchone()
        return self._count(row)

    @staticmethod
    def _subject(mail: dict, day: CashDay) -> str:
        template = str(mail.get("subject", "Cierre {fecha} - {sucursal}"))[:180]
        return template.replace("{fecha}", day.business_date.strftime("%d-%m-%Y")).replace("{sucursal}", day.unit)

    def generate_close_pdf(self, day: CashDay, count: CountResult, closure_id: str, destination: Path) -> Path:
        from .continuous_report import generate_continuous_daily_control
        return generate_continuous_daily_control(day, count, closure_id, destination)

    def mail_status(self, cash_day_id: str) -> str:
        with self.repository._connection() as connection:
            row = connection.execute("SELECT status FROM mail_outbox WHERE cash_day_id=?", (cash_day_id,)).fetchone()
        return row["status"] if row else "NOT_CONFIGURED"

    @staticmethod
    def _sanitize_error(error: Exception) -> str:
        if isinstance(error, (TimeoutError, smtplib.SMTPConnectError)):
            return "NETWORK_TIMEOUT"
        if isinstance(error, smtplib.SMTPAuthenticationError):
            return "AUTHENTICATION_FAILED"
        return "DELIVERY_FAILED"

    def process_outbox(self, limit: int = 10) -> int:
        mail = self.setting("mail")
        if not mail.get("enabled") or not mail.get("recipient"):
            return 0
        secret = self.secret_store.get(str(mail.get("secret_ref", "smtp")))
        if not secret:
            return 0
        with self.repository._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM mail_outbox WHERE status IN ('NOT_CONFIGURED','PENDING','ERROR') AND (next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY created_at LIMIT ?",
                (_now().isoformat(), int(limit)),
            ).fetchall()
        sent = 0
        for row in rows:
            try:
                from email.message import EmailMessage
                recipient = str(mail.get("recipient", "")).strip()
                with self.repository._connection() as connection:
                    connection.execute(
                        "UPDATE mail_outbox SET recipient=?,updated_at=? WHERE id=? AND status!='SENT'",
                        (recipient, _now().isoformat(), row["id"]),
                    )
                    connection.commit()
                message = EmailMessage()
                message["To"] = recipient
                message["From"] = str(mail.get("username", ""))
                message["Subject"] = row["subject"]
                message.set_content("Se adjunta el cierre de Caja y Arqueo.")
                report = Path(row["report_path"])
                message.add_attachment(report.read_bytes(), maintype="application", subtype="pdf", filename=report.name)
                context = ssl.create_default_context()
                with smtplib.SMTP(str(mail.get("host", "")), int(mail.get("port", 587)), timeout=15) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(str(mail.get("username", "")), secret)
                    smtp.send_message(message)
                self._mail_result(row["id"], "SENT", "SENT")
                sent += 1
            except Exception as error:
                detail = self._sanitize_error(error)
                self._mail_result(row["id"], "ERROR" if detail == "AUTHENTICATION_FAILED" else "PENDING", detail)
        return sent

    def retry_outbox(self, outbox_id: str | None = None) -> int:
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if outbox_id:
                connection.execute(
                    "UPDATE mail_outbox SET status='PENDING',next_attempt_at=NULL,last_error='',updated_at=? WHERE id=? AND status!='SENT'",
                    (_now().isoformat(), outbox_id),
                )
            else:
                connection.execute(
                    "UPDATE mail_outbox SET status='PENDING',next_attempt_at=NULL,last_error='',updated_at=? WHERE status IN ('NOT_CONFIGURED','ERROR','PENDING')",
                    (_now().isoformat(),),
                )
            connection.commit()
        return self.process_outbox()

    def _mail_result(self, outbox_id: str, status: str, detail: str) -> None:
        now = _now()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT attempts FROM mail_outbox WHERE id=?", (outbox_id,)).fetchone()
            attempts = (row["attempts"] if row else 0) + 1
            next_attempt = None if status == "SENT" else (now + timedelta(minutes=min(60, 2 ** attempts))).isoformat()
            connection.execute(
                "UPDATE mail_outbox SET status=?,attempts=?,next_attempt_at=?,last_error=?,updated_at=?,sent_at=? WHERE id=?",
                (status, attempts, next_attempt, "" if status == "SENT" else detail, now.isoformat(),
                 now.isoformat() if status == "SENT" else None, outbox_id),
            )
            connection.execute(
                "INSERT INTO mail_history(id,outbox_id,result,sanitized_detail,recorded_at) VALUES(?,?,?,?,?)",
                (_id(), outbox_id, status, detail, now.isoformat()),
            )
            connection.commit()
