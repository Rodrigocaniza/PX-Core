"""El llavero: como se obtiene la clave que cifra los datos, y como se recupera.

Hay **una sola** clave de datos por base, la DEK. No se deriva del secreto de
la instalacion: se genera al azar una vez y se guarda envuelta de dos maneras
independientes.

    DEK  --envuelta con-->  clave de instalacion   (secreto sellado por DPAPI)
    DEK  --envuelta con-->  clave de recuperacion  (scrypt de una frase)

Por que no derivar la DEK del secreto de instalacion, que seria mas corto:
porque entonces re-enrolar la PC —o cambiarla— dejaria la base ilegible para
siempre. Con envolturas separadas, re-enrolar solo pide volver a envolver la
misma DEK con el secreto nuevo, y la frase de recuperacion es el camino cuando
la PC ya no existe. La mision prohibe cifrar sin estrategia de recuperacion, y
esta es la estrategia.

La frase de recuperacion se muestra **una vez**, al enrolar. No se guarda en
ningun lado: guardarla al lado de la base seria exactamente la clave junto a
los datos que la mision prohibe.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from ..crypto.primitives import (
    AEAD_KEY_BYTES,
    aead_open,
    aead_seal,
    derive_key,
    derive_key_from_passphrase,
    random_bytes,
)
from ..errors import KeyringError
from ..infrastructure import security_db
from .enrollment import InstallationSecret

WRAP_INSTALLATION = "installation"
WRAP_RECOVERY = "recovery"

RECOVERY_SALT_BYTES = 16
_RECOVERY_GROUPS = 8
_RECOVERY_GROUP_CHARS = 5


@dataclass(frozen=True)
class DataKey:
    """La DEK viva. Solo en memoria; nunca se serializa ni se registra."""

    raw: bytes
    dek_id: str

    def __repr__(self) -> str:  # pragma: no cover - defensa contra logs accidentales
        return f"DataKey(dek_id={self.dek_id!r}, raw=<oculto>)"


def dek_identifier(dek: bytes) -> str:
    """Nombre publico de una DEK, derivado y no la DEK misma.

    Sirve para saber si dos envolturas guardan la misma clave sin abrirlas.
    """
    return derive_key(dek, "dek-identifier", length=16).hex()


def generate_recovery_passphrase() -> str:
    """Frase de recuperacion de ~160 bits, en grupos legibles para transcribir a mano.

    base32 sin padding y en mayusculas: se dicta por telefono y se escribe en
    un papel sin ambiguedad entre l/1 o O/0 mas alla de la que base32 ya evita.
    """
    raw = random_bytes(_RECOVERY_GROUPS * _RECOVERY_GROUP_CHARS)
    encoded = base64.b32encode(raw).decode("ascii").rstrip("=")
    groups = [
        encoded[index : index + _RECOVERY_GROUP_CHARS]
        for index in range(0, _RECOVERY_GROUPS * _RECOVERY_GROUP_CHARS, _RECOVERY_GROUP_CHARS)
    ]
    return "-".join(groups)


def normalize_passphrase(passphrase: str) -> str:
    """Tolera como la escribio una persona: espacios, minusculas, guiones de mas."""
    cleaned = "".join(character for character in passphrase.upper() if character.isalnum())
    if not cleaned:
        raise KeyringError("la frase de recuperacion esta vacia")
    return cleaned


# --------------------------------------------------------------------------
# Creacion
# --------------------------------------------------------------------------
def create_data_key(
    database_path: str | Path, secret: InstallationSecret, *, created_by: str = ""
) -> tuple[DataKey, str]:
    """Crea la DEK y sus dos envolturas. Devuelve la clave y la frase de recuperacion.

    Si ya existe una DEK, no crea otra: dos claves de datos sobre la misma base
    significa que la mitad de los datos no se abre con la que quedo.
    """
    if security_db.find_wrap(database_path, WRAP_INSTALLATION) is not None:
        raise KeyringError("esta base ya tiene una clave de datos")
    dek = random_bytes(AEAD_KEY_BYTES)
    dek_id = dek_identifier(dek)
    passphrase = generate_recovery_passphrase()

    security_db.store_wrap(
        database_path,
        wrap_kind=WRAP_INSTALLATION,
        dek_id=dek_id,
        wrapped_dek=_wrap(secret.data_key(), dek, dek_id, WRAP_INSTALLATION),
        installation_id=secret.installation_id,
        created_by=created_by,
    )
    salt = random_bytes(RECOVERY_SALT_BYTES)
    security_db.store_wrap(
        database_path,
        wrap_kind=WRAP_RECOVERY,
        dek_id=dek_id,
        wrapped_dek=_wrap(
            derive_key_from_passphrase(normalize_passphrase(passphrase), salt),
            dek,
            dek_id,
            WRAP_RECOVERY,
        ),
        salt=salt,
        created_by=created_by,
    )
    return DataKey(raw=dek, dek_id=dek_id), passphrase


def _associated_data(dek_id: str, wrap_kind: str) -> bytes:
    """Ata la envoltura a su tipo y a su DEK.

    Sin esto, mover el criptograma de la fila 'recovery' a la fila
    'installation' pasaria desapercibido hasta que alguien intentara abrirlo.
    """
    return f"bc.keyring.v1|{dek_id}|{wrap_kind}".encode("utf-8")


def _wrap(key_encryption_key: bytes, dek: bytes, dek_id: str, wrap_kind: str) -> bytes:
    return aead_seal(key_encryption_key, dek, _associated_data(dek_id, wrap_kind))


# --------------------------------------------------------------------------
# Apertura
# --------------------------------------------------------------------------
def open_with_installation(database_path: str | Path, secret: InstallationSecret) -> DataKey:
    wrap = security_db.require_wrap(database_path, WRAP_INSTALLATION)
    dek = aead_open(
        secret.data_key(), wrap.wrapped_dek, _associated_data(wrap.dek_id, WRAP_INSTALLATION)
    )
    return DataKey(raw=dek, dek_id=wrap.dek_id)


def open_with_recovery(database_path: str | Path, passphrase: str) -> DataKey:
    wrap = security_db.require_wrap(database_path, WRAP_RECOVERY)
    key = derive_key_from_passphrase(normalize_passphrase(passphrase), wrap.salt)
    dek = aead_open(key, wrap.wrapped_dek, _associated_data(wrap.dek_id, WRAP_RECOVERY))
    return DataKey(raw=dek, dek_id=wrap.dek_id)


def rewrap_for_installation(
    database_path: str | Path,
    data_key: DataKey,
    secret: InstallationSecret,
    *,
    created_by: str = "",
) -> None:
    """Vuelve a envolver la MISMA DEK con el secreto de una instalacion nueva.

    Es el camino de la recuperacion en otra PC: se abre con la frase, se
    re-envuelve con el secreto local, y a partir de ahi todo vuelve a ser
    transparente. La DEK no cambia, asi que no hay que recifrar un solo dato.
    """
    security_db.store_wrap(
        database_path,
        wrap_kind=WRAP_INSTALLATION,
        dek_id=data_key.dek_id,
        wrapped_dek=_wrap(secret.data_key(), data_key.raw, data_key.dek_id, WRAP_INSTALLATION),
        installation_id=secret.installation_id,
        created_by=created_by,
    )


def reset_recovery_passphrase(
    database_path: str | Path, data_key: DataKey, *, created_by: str = ""
) -> str:
    """Emite una frase de recuperacion nueva para la misma DEK y desactiva la anterior."""
    passphrase = generate_recovery_passphrase()
    salt = random_bytes(RECOVERY_SALT_BYTES)
    security_db.store_wrap(
        database_path,
        wrap_kind=WRAP_RECOVERY,
        dek_id=data_key.dek_id,
        wrapped_dek=_wrap(
            derive_key_from_passphrase(normalize_passphrase(passphrase), salt),
            data_key.raw,
            data_key.dek_id,
            WRAP_RECOVERY,
        ),
        salt=salt,
        created_by=created_by,
    )
    return passphrase


def has_data_key(database_path: str | Path) -> bool:
    """Hay una envoltura de instalacion activa, es decir: se puede abrir hoy."""
    return security_db.find_wrap(database_path, WRAP_INSTALLATION) is not None


def protection_configured(database_path: str | Path) -> bool:
    """Esta base tiene clave de datos, se pueda abrir hoy o no."""
    return security_db.keyring_configured(database_path)
