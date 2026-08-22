"""El documento de autorizacion y su sobre firmado.

Separacion deliberada en dos objetos:

  * `LicensePayload` es lo que el emisor afirma. Es un dato inerte.
  * `SignedLicense` es ese dato mas la firma que lo respalda.

Nada del cliente construye un `LicensePayload` de la nada y lo trata como
autorizacion: para llegar a un payload confiable hay que pasar por
`verifier.py`, que exige la firma. El tipo hace visible esa frontera.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from ..canonical import b64u_decode, b64u_encode, canonical_json
from ..errors import LicenseFormatError

LICENSE_FORMAT = "bc.license.v1"
REVOCATION_FORMAT = "bc.revocation.v1"

# Capacidades conocidas. La lista no es un permiso: es el vocabulario. Que una
# capacidad exista aca no autoriza nada; autorizarla es que el emisor la firme.
CAPABILITY_CAJA = "bc.caja"
CAPABILITY_HISTORIAL = "bc.historial"
CAPABILITY_INVENTARIO = "bc.inventario"
CAPABILITY_SYNC = "bc.sync"
KNOWN_CAPABILITIES = (
    CAPABILITY_CAJA,
    CAPABILITY_HISTORIAL,
    CAPABILITY_INVENTARIO,
    CAPABILITY_SYNC,
)


def parse_instant(text: str) -> datetime:
    """Instante ISO-8601, siempre en UTC.

    Un instante sin zona seria el reloj de quien lo escribio, y una licencia
    emitida en una zona y verificada en otra vencería en momentos distintos.
    """
    if not isinstance(text, str) or not text:
        raise LicenseFormatError("instante ausente")
    try:
        value = datetime.fromisoformat(text)
    except ValueError as error:
        raise LicenseFormatError("instante con formato invalido") from error
    if value.tzinfo is None:
        raise LicenseFormatError("instante sin zona horaria")
    return value.astimezone(timezone.utc)


def format_instant(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("no se serializan instantes sin zona")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class LicensePayload:
    """Lo que el emisor afirma sobre una instalacion."""

    license_id: str
    installation_id: str
    organization_id: str
    branch_id: str
    business_name: str
    capabilities: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime | None
    lease_days: int
    grace_days: int
    binding: Mapping[str, str]
    secondary_required: int
    security_schema_version: str
    app_version: str
    revocation_id: str
    issuer_key_id: str
    # Clave publica de sincronizacion de ESTA instalacion. Que viaje dentro
    # de la licencia firmada es lo que la convierte en una identidad que
    # Gestion Central puede verificar sin conocer ningun secreto compartido.
    sync_public_key: str = ""
    notes: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "format": LICENSE_FORMAT,
            "license_id": self.license_id,
            "installation_id": self.installation_id,
            "organization_id": self.organization_id,
            "branch_id": self.branch_id,
            "business_name": self.business_name,
            "capabilities": list(self.capabilities),
            "issued_at": format_instant(self.issued_at),
            "expires_at": format_instant(self.expires_at) if self.expires_at else None,
            "lease_days": self.lease_days,
            "grace_days": self.grace_days,
            "binding": dict(self.binding),
            "secondary_required": self.secondary_required,
            "security_schema_version": self.security_schema_version,
            "app_version": self.app_version,
            "revocation_id": self.revocation_id,
            "issuer_key_id": self.issuer_key_id,
            "sync_public_key": self.sync_public_key,
            "notes": self.notes,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "LicensePayload":
        if document.get("format") != LICENSE_FORMAT:
            raise LicenseFormatError("formato de licencia desconocido")
        required = (
            "license_id", "installation_id", "organization_id", "branch_id",
            "business_name", "capabilities", "issued_at", "lease_days",
            "grace_days", "binding", "secondary_required",
            "security_schema_version", "revocation_id", "issuer_key_id",
        )
        missing = [name for name in required if name not in document]
        if missing:
            raise LicenseFormatError(f"faltan campos: {', '.join(sorted(missing))}")
        binding = document["binding"]
        if not isinstance(binding, Mapping) or not binding:
            raise LicenseFormatError("una licencia sin binding no ata nada")
        if not all(isinstance(value, str) for value in binding.values()):
            raise LicenseFormatError("el binding solo lleva hashes")
        capabilities = document["capabilities"]
        if not isinstance(capabilities, list):
            raise LicenseFormatError("capabilities tiene que ser una lista")
        expires_raw = document.get("expires_at")
        return cls(
            license_id=str(document["license_id"]),
            installation_id=str(document["installation_id"]),
            organization_id=str(document["organization_id"]),
            branch_id=str(document["branch_id"]),
            business_name=str(document["business_name"]),
            capabilities=tuple(str(item) for item in capabilities),
            issued_at=parse_instant(document["issued_at"]),
            expires_at=parse_instant(expires_raw) if expires_raw else None,
            lease_days=int(document["lease_days"]),
            grace_days=int(document["grace_days"]),
            binding=dict(binding),
            secondary_required=int(document["secondary_required"]),
            security_schema_version=str(document["security_schema_version"]),
            app_version=str(document.get("app_version", "")),
            revocation_id=str(document["revocation_id"]),
            issuer_key_id=str(document["issuer_key_id"]),
            sync_public_key=str(document.get("sync_public_key", "")),
            notes=str(document.get("notes", "")),
        )

    def allows(self, capability: str) -> bool:
        return capability in self.capabilities

    def lease_expires_from(self, validated_at: datetime) -> datetime:
        return validated_at + timedelta(days=self.lease_days)


@dataclass(frozen=True)
class SignedLicense:
    """Payload canonico mas firma. Se guarda y se transporta asi."""

    payload: LicensePayload
    signature: bytes
    key_id: str

    def signed_bytes(self) -> bytes:
        return canonical_json(self.payload.to_document())

    def to_envelope(self) -> dict[str, Any]:
        return {
            "format": LICENSE_FORMAT,
            "key_id": self.key_id,
            "payload": self.payload.to_document(),
            "signature": b64u_encode(self.signature),
        }

    @classmethod
    def from_envelope(cls, envelope: Mapping[str, Any]) -> "SignedLicense":
        if not isinstance(envelope, Mapping) or envelope.get("format") != LICENSE_FORMAT:
            raise LicenseFormatError("sobre de licencia desconocido")
        for name in ("key_id", "payload", "signature"):
            if name not in envelope:
                raise LicenseFormatError(f"al sobre le falta {name}")
        try:
            signature = b64u_decode(str(envelope["signature"]))
        except (ValueError, TypeError) as error:
            raise LicenseFormatError("firma ilegible") from error
        return cls(
            payload=LicensePayload.from_document(envelope["payload"]),
            signature=signature,
            key_id=str(envelope["key_id"]),
        )


@dataclass(frozen=True)
class RevocationList:
    """Lista de revocacion firmada.

    `serial` es monotono y el cliente guarda el mayor que vio: sin eso, volver
    a poner una lista vieja bastaria para deshacer una revocacion.
    """

    serial: int
    issued_at: datetime
    revoked_installations: tuple[str, ...] = ()
    revoked_licenses: tuple[str, ...] = ()
    reasons: Mapping[str, str] = field(default_factory=dict)
    issuer_key_id: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "format": REVOCATION_FORMAT,
            "serial": self.serial,
            "issued_at": format_instant(self.issued_at),
            "revoked_installations": sorted(self.revoked_installations),
            "revoked_licenses": sorted(self.revoked_licenses),
            "reasons": dict(self.reasons),
            "issuer_key_id": self.issuer_key_id,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "RevocationList":
        if document.get("format") != REVOCATION_FORMAT:
            raise LicenseFormatError("formato de revocacion desconocido")
        return cls(
            serial=int(document["serial"]),
            issued_at=parse_instant(document["issued_at"]),
            revoked_installations=tuple(document.get("revoked_installations", ())),
            revoked_licenses=tuple(document.get("revoked_licenses", ())),
            reasons=dict(document.get("reasons", {})),
            issuer_key_id=str(document.get("issuer_key_id", "")),
        )

    def revokes(self, *, installation_id: str, license_id: str) -> str:
        """Devuelve el motivo si esta revocada, o cadena vacia si no lo esta."""
        if installation_id in self.revoked_installations:
            return self.reasons.get(installation_id, "instalacion revocada")
        if license_id in self.revoked_licenses:
            return self.reasons.get(license_id, "licencia revocada")
        return ""


@dataclass(frozen=True)
class SignedRevocationList:
    revocations: RevocationList
    signature: bytes
    key_id: str

    def signed_bytes(self) -> bytes:
        return canonical_json(self.revocations.to_document())

    def to_envelope(self) -> dict[str, Any]:
        return {
            "format": REVOCATION_FORMAT,
            "key_id": self.key_id,
            "payload": self.revocations.to_document(),
            "signature": b64u_encode(self.signature),
        }

    @classmethod
    def from_envelope(cls, envelope: Mapping[str, Any]) -> "SignedRevocationList":
        if not isinstance(envelope, Mapping) or envelope.get("format") != REVOCATION_FORMAT:
            raise LicenseFormatError("sobre de revocacion desconocido")
        for name in ("key_id", "payload", "signature"):
            if name not in envelope:
                raise LicenseFormatError(f"al sobre de revocacion le falta {name}")
        try:
            signature = b64u_decode(str(envelope["signature"]))
        except (ValueError, TypeError) as error:
            raise LicenseFormatError("firma de revocacion ilegible") from error
        return cls(
            revocations=RevocationList.from_document(envelope["payload"]),
            signature=signature,
            key_id=str(envelope["key_id"]),
        )
