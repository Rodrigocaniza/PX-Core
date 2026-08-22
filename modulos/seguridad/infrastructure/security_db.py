"""Acceso a las tres tablas de seguridad que viven en la base de negocio.

Deliberadamente no importa nada de Caja: abre la base por ruta y toca solo
`security_state`, `security_keyring` y `security_audit`. Asi la misma capa
sirve a Caja, a Historial, a Inventario y a lo que venga, sin que ninguno de
ellos tenga que prestarle su repositorio.

Las conexiones son cortas y con `busy_timeout`: la Caja esta abierta mientras
esto corre, y un lock de cinco segundos es preferible a mantener una conexion
viva compitiendo por el WAL.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping
from uuid import uuid4

from .. import SECURITY_SCHEMA_VERSION
from ..canonical import b64u_decode, b64u_encode, canonical_json
from ..crypto.primitives import mac, mac_equal
from ..errors import KeyringError, SecurityError

STATE_LEASE = "lease"

# Eventos de la bitacora. Nombres estables: se buscan en produccion meses
# despues y una prueba los compara literalmente.
EVENT_ENROLLED = "ENROLAMIENTO"
EVENT_LICENSE_INSTALLED = "LICENCIA_INSTALADA"
EVENT_AUTHORIZATION = "VALIDACION"
EVENT_REVOCATION_INSTALLED = "REVOCACION_INSTALADA"
EVENT_LEASE_RENEWED = "LEASE_RENOVADO"
EVENT_DATA_PROTECTED = "DATOS_PROTEGIDOS"
EVENT_DATA_ROLLBACK = "DATOS_REVERTIDOS"
EVENT_KEYRING_RECOVERED = "LLAVERO_RECUPERADO"
EVENT_SYNC_AUTH = "SYNC_AUTENTICACION"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _now_text() -> str:
    return utc_now().isoformat()


@contextmanager
def connect(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def tables_present(database_path: str | Path) -> bool:
    """Si la 033 todavia no corrio, la capa se comporta como si no existiera."""
    if not Path(database_path).is_file():
        return False
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN"
            " ('security_state','security_keyring','security_audit')"
        ).fetchall()
    return len(rows) == 3


# --------------------------------------------------------------------------
# Bitacora
# --------------------------------------------------------------------------
_FORBIDDEN_DETAIL_TOKENS = frozenset(
    {
        "key", "keys", "clave", "claves", "secret", "secreto", "dek", "kek",
        "password", "passphrase", "frase", "private", "privada", "mac",
        "signature", "firma", "seed", "entropy", "entropia",
    }
)


def _tokens(name: str) -> list[str]:
    return [
        token
        for token in "".join(
            character if character.isalnum() else " " for character in str(name).lower()
        ).split()
    ]


def _reject_secrets(details: Mapping[str, Any]) -> dict[str, Any]:
    """Filtro duro: la bitacora no acepta nada que se parezca a material secreto.

    Es un control de codigo, no una advertencia en un comentario. Un dia alguien
    va a agregar un campo de diagnostico con la clave adentro, y este filtro lo
    convierte en una prueba roja en vez de en una filtracion.

    Dos precisiones que evitan que sea inutil por exceso:

      * Se compara por palabra y no por subcadena. `machine` contiene "mac" y no
        es un MAC; rechazarlo habria empujado a apagar el filtro.
      * Un nombre terminado en `_id` es un identificador, no material: `dek_id` e
        `issuer_key_id` nombran una clave sin decirla, y auditar sin poder
        nombrar cual clave firmo no serviria de nada.
    """
    for name in details:
        if str(name).lower().endswith("_id"):
            continue
        if set(_tokens(name)) & _FORBIDDEN_DETAIL_TOKENS:
            raise SecurityError(f"la bitacora de seguridad no acepta el campo '{name}'")
    return dict(details)


def record_event(
    database_path: str | Path,
    *,
    event: str,
    outcome: str,
    reason: str = "",
    installation_id: str = "",
    details: Mapping[str, Any] | None = None,
) -> str:
    """Escribe una linea de bitacora. Nunca levanta hacia arriba por un fallo de disco.

    Una auditoria que rompe el arranque convierte un problema de registro en
    una optica cerrada. El fallo de escritura se traga a proposito; lo que no
    se traga es el intento de escribir un secreto, que es un error de programa.
    """
    payload = json.dumps(_reject_secrets(details or {}), ensure_ascii=False, sort_keys=True)
    identifier = str(uuid4())
    try:
        with connect(database_path) as connection:
            connection.execute(
                "INSERT INTO security_audit(id, occurred_at, installation_id, event,"
                " outcome, reason, detail_json, security_schema_version)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (
                    identifier, _now_text(), installation_id, event, outcome, reason,
                    payload, SECURITY_SCHEMA_VERSION,
                ),
            )
    except sqlite3.Error:
        return ""
    return identifier


def read_audit(database_path: str | Path, *, limit: int = 200) -> list[dict[str, Any]]:
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM security_audit ORDER BY occurred_at DESC, rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------
# Estado sellado
# --------------------------------------------------------------------------
def write_state(database_path: str | Path, key: str, document: Mapping[str, Any], state_key: bytes) -> None:
    body = canonical_json(document)
    with connect(database_path) as connection:
        connection.execute(
            "INSERT INTO security_state(key, value_json, mac, updated_at) VALUES(?,?,?,?)"
            " ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,"
            " mac=excluded.mac, updated_at=excluded.updated_at",
            (key, body.decode("utf-8"), b64u_encode(mac(state_key, body)), _now_text()),
        )


def read_state(
    database_path: str | Path, key: str, state_key: bytes
) -> dict[str, Any] | None:
    """`None` si no hay. Error si hay y el MAC no cierra: eso es manipulacion."""
    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT value_json, mac FROM security_state WHERE key=?", (key,)
        ).fetchone()
    if row is None:
        return None
    body = row["value_json"].encode("utf-8")
    try:
        presented = b64u_decode(row["mac"])
    except ValueError as error:
        raise SecurityError(f"el estado '{key}' tiene un MAC ilegible") from error
    if not mac_equal(presented, mac(state_key, body)):
        raise SecurityError(f"el estado '{key}' fue modificado fuera de BC")
    return json.loads(row["value_json"])


# --------------------------------------------------------------------------
# Llavero
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class WrappedKey:
    id: str
    wrap_kind: str
    installation_id: str
    wrapped_dek: bytes
    salt: bytes
    dek_id: str
    created_at: str


def _row_to_wrapped(row: sqlite3.Row) -> WrappedKey:
    return WrappedKey(
        id=row["id"],
        wrap_kind=row["wrap_kind"],
        installation_id=row["installation_id"],
        wrapped_dek=b64u_decode(row["wrapped_dek"]),
        salt=b64u_decode(row["salt"]) if row["salt"] else b"",
        dek_id=row["dek_id"],
        created_at=row["created_at"],
    )


def active_wraps(database_path: str | Path) -> list[WrappedKey]:
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM security_keyring WHERE active=1 ORDER BY created_at"
        ).fetchall()
    return [_row_to_wrapped(row) for row in rows]


def keyring_configured(database_path: str | Path) -> bool:
    """Si alguna vez se creo una clave de datos para esta base.

    Distinto de "hay una envoltura activa": una envoltura se puede desactivar,
    y la base sigue cifrada. Confundir las dos cosas haria que desactivar una
    fila del llavero equivalga a apagar la proteccion, y BC abriria mostrando
    criptograma y guardando lo nuevo en claro al lado de lo viejo cifrado.
    El trigger de la 033 impide el DELETE, asi que una fila siempre queda.
    """
    with connect(database_path) as connection:
        return connection.execute(
            "SELECT 1 FROM security_keyring LIMIT 1"
        ).fetchone() is not None


def find_wrap(database_path: str | Path, wrap_kind: str) -> WrappedKey | None:
    for wrap in active_wraps(database_path):
        if wrap.wrap_kind == wrap_kind:
            return wrap
    return None


def store_wrap(
    database_path: str | Path,
    *,
    wrap_kind: str,
    dek_id: str,
    wrapped_dek: bytes,
    installation_id: str = "",
    salt: bytes = b"",
    created_by: str = "",
) -> str:
    """Guarda una envoltura y desactiva la anterior del mismo tipo.

    Desactiva en vez de borrar: si la envoltura nueva resultara ilegible, la
    vieja sigue estando y la base no se pierde. El trigger de la 033 impide el
    DELETE justamente para que esto no sea una decision de quien programa.
    """
    identifier = str(uuid4())
    with connect(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE security_keyring SET active=0 WHERE dek_id=? AND wrap_kind=? AND active=1",
            (dek_id, wrap_kind),
        )
        connection.execute(
            "INSERT INTO security_keyring(id, wrap_kind, installation_id, wrapped_dek,"
            " salt, dek_id, active, created_at, created_by) VALUES(?,?,?,?,?,?,1,?,?)",
            (
                identifier, wrap_kind, installation_id, b64u_encode(wrapped_dek),
                b64u_encode(salt) if salt else "", dek_id, _now_text(), created_by,
            ),
        )
    return identifier


def deactivate_wrap(database_path: str | Path, wrap_id: str) -> None:
    with connect(database_path) as connection:
        connection.execute("UPDATE security_keyring SET active=0 WHERE id=?", (wrap_id,))


def require_wrap(database_path: str | Path, wrap_kind: str) -> WrappedKey:
    wrap = find_wrap(database_path, wrap_kind)
    if wrap is None:
        raise KeyringError(f"no hay envoltura activa de tipo '{wrap_kind}' en el llavero")
    return wrap
