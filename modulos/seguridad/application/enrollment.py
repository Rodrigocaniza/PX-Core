"""Enrolamiento: darle identidad y secreto a una instalacion nueva.

Ocurre una sola vez por PC. Deja tres cosas:

  * `installation.json` — identidad publica, copiable y sin valor por si sola;
  * `installation.secret` — el secreto sellado por el sistema operativo;
  * una solicitud para el emisor, con los hashes de la huella de esta maquina.

El secreto en claro no toca el disco en ningun momento. Se genera en memoria,
se sella y se descarta; para volver a tenerlo hay que pedirselo al sistema
operativo, que solo lo entrega en esta maquina.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .. import SECURITY_SCHEMA_VERSION
from ..canonical import b64u_decode, b64u_encode
from ..crypto.primitives import SECRET_BYTES, derive_key, random_bytes
from ..domain.identity import InstallationIdentity, new_installation_id
from ..errors import AlreadyEnrolledError, NotEnrolledError, SealedStoreError
from ..infrastructure import fingerprint as fingerprint_module
from ..infrastructure.fingerprint import MachineFingerprint
from ..infrastructure.store import SecurityPaths, read_bytes, read_json, write_atomic, write_json

ENROLLMENT_REQUEST_FORMAT = "bc.enrollment-request.v1"

# Propositos de derivacion. Cada uno produce una clave independiente del mismo
# secreto; verlos juntos en un solo lugar es lo que evita que dos usos
# terminen compartiendo clave por descuido.
PURPOSE_DATA = "data-encryption-key"
PURPOSE_SYNC = "sync-authentication"
PURPOSE_LEASE = "lease-state-mac"
PURPOSE_SYNC_IDENTITY = "sync-identity-key"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass(frozen=True)
class EnrollmentRequest:
    """Lo que el emisor necesita para firmar. No lleva secretos: solo hashes."""

    installation_id: str
    binding: Mapping[str, str]
    secondary_required: int
    label: str
    requested_at: datetime
    security_schema_version: str
    sync_public_key: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "format": ENROLLMENT_REQUEST_FORMAT,
            "installation_id": self.installation_id,
            "binding": dict(self.binding),
            "secondary_required": self.secondary_required,
            "label": self.label,
            "requested_at": self.requested_at.isoformat(),
            "security_schema_version": self.security_schema_version,
            "sync_public_key": self.sync_public_key,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "EnrollmentRequest":
        from ..domain.license import parse_instant

        if document.get("format") != ENROLLMENT_REQUEST_FORMAT:
            raise ValueError("solicitud de enrolamiento desconocida")
        return cls(
            installation_id=str(document["installation_id"]),
            binding=dict(document["binding"]),
            secondary_required=int(document["secondary_required"]),
            label=str(document.get("label", "")),
            requested_at=parse_instant(document["requested_at"]),
            security_schema_version=str(document["security_schema_version"]),
            sync_public_key=str(document.get("sync_public_key", "")),
        )


@dataclass(frozen=True)
class InstallationSecret:
    """El secreto vivo, en memoria. Nunca se serializa."""

    installation_id: str
    raw: bytes

    def data_key(self) -> bytes:
        """Clave que envuelve la DEK de la base. No cifra datos directamente."""
        return derive_key(self.raw, PURPOSE_DATA, salt=self.installation_id.encode("utf-8"))

    def sync_key(self) -> bytes:
        return derive_key(self.raw, PURPOSE_SYNC, salt=self.installation_id.encode("utf-8"))

    def lease_key(self) -> bytes:
        return derive_key(self.raw, PURPOSE_LEASE, salt=self.installation_id.encode("utf-8"))

    def sync_signing_key(self):
        """Clave Ed25519 de sincronizacion, derivada y no almacenada.

        Deterministica a proposito: nace del mismo secreto sellado, asi que no
        hay un archivo mas que perder ni que proteger, y en otra PC no se puede
        reconstruir porque el secreto no abre.
        """
        from ..crypto.primitives import signing_key_from_bytes

        return signing_key_from_bytes(
            derive_key(self.raw, PURPOSE_SYNC_IDENTITY, salt=self.installation_id.encode("utf-8"))
        )

    def sync_public_key(self) -> bytes:
        from ..crypto.primitives import public_key_bytes

        return public_key_bytes(self.sync_signing_key().public_key())

    def __repr__(self) -> str:  # pragma: no cover - defensa contra logs accidentales
        return f"InstallationSecret(installation_id={self.installation_id!r}, raw=<oculto>)"


def is_enrolled(paths: SecurityPaths) -> bool:
    return paths.identity.is_file() and paths.secret.is_file()


def load_identity(paths: SecurityPaths) -> InstallationIdentity:
    document = read_json(paths.identity)
    if document is None:
        raise NotEnrolledError("esta instalacion no fue enrolada")
    return InstallationIdentity.from_document(document)


def enroll(
    paths: SecurityPaths,
    sealer,
    fingerprint: MachineFingerprint,
    *,
    label: str = "",
    force: bool = False,
) -> tuple[InstallationIdentity, EnrollmentRequest]:
    """Crea identidad y secreto. Idempotente por negativa: no pisa lo que existe.

    `force` re-enrola y por lo tanto **invalida la clave de datos vigente**. La
    base solo se recupera despues con la frase de recuperacion. Por eso no es
    el camino por defecto ni se hace sin pedirlo.
    """
    paths.ensure()
    if is_enrolled(paths) and not force:
        raise AlreadyEnrolledError(
            "ya hay una identidad de instalacion; re-enrolar invalida la clave de datos vigente"
        )

    installation_id = new_installation_id()
    secret = random_bytes(SECRET_BYTES)
    entropy = fingerprint.entropy(installation_id)
    sealed = sealer.seal(secret, entropy)
    # Se comprueba en el acto que lo sellado abre. Un secreto que se sella y no
    # se puede recuperar es una instalacion muerta que recien se descubriria al
    # reiniciar, con la base ya cifrada.
    if sealer.open(sealed, entropy) != secret:
        raise SealedStoreError("el sellado local no devolvio el mismo secreto")

    identity = InstallationIdentity(
        installation_id=installation_id,
        enrolled_at=utc_now(),
        sealer=getattr(sealer, "name", "desconocido"),
        security_schema_version=SECURITY_SCHEMA_VERSION,
        fingerprint_components=fingerprint.available(),
        label=label,
    )
    binding = fingerprint.hashed(installation_id)
    request = EnrollmentRequest(
        installation_id=installation_id,
        binding=binding,
        secondary_required=fingerprint_module.required_secondary(binding),
        label=label,
        requested_at=identity.enrolled_at,
        security_schema_version=SECURITY_SCHEMA_VERSION,
    )

    request = EnrollmentRequest(
        installation_id=request.installation_id,
        binding=request.binding,
        secondary_required=request.secondary_required,
        label=request.label,
        requested_at=request.requested_at,
        security_schema_version=request.security_schema_version,
        sync_public_key=b64u_encode(
            InstallationSecret(installation_id=installation_id, raw=secret).sync_public_key()
        ),
    )

    write_atomic(paths.secret, b64u_encode(sealed).encode("ascii"))
    write_json(paths.identity, identity.to_document())
    del secret
    return identity, request


def open_secret(
    paths: SecurityPaths, sealer, fingerprint: MachineFingerprint
) -> InstallationSecret:
    """Recupera el secreto pidiendoselo al sistema operativo.

    En otra PC esto falla, y falla aca: es el punto exacto donde una copia de
    la carpeta deja de servir. No hay camino alternativo que lo evite.
    """
    identity = load_identity(paths)
    sealed_text = read_bytes(paths.secret)
    if sealed_text is None:
        raise NotEnrolledError("falta el secreto sellado de la instalacion")
    try:
        sealed = b64u_decode(sealed_text.decode("ascii").strip())
    except (UnicodeDecodeError, ValueError) as error:
        raise SealedStoreError("el secreto sellado esta corrupto") from error
    raw = sealer.open(sealed, fingerprint.entropy(identity.installation_id))
    if len(raw) != SECRET_BYTES:
        raise SealedStoreError("el secreto recuperado no tiene el tamano esperado")
    return InstallationSecret(installation_id=identity.installation_id, raw=raw)
