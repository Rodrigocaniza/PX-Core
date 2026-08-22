"""Emisor de licencias. **No forma parte del cliente.**

Este modulo vive en el repositorio porque el codigo del emisor tiene que poder
revisarse, pero la clave privada no vive aca ni entra al paquete: se genera en
la maquina de administracion, se guarda sellada por el sistema operativo con
ambito de usuario y se respalda fuera de linea. Un `bc_caja.exe` no importa
nada de este archivo, y hay una prueba que lo verifica.

Que puede hacer el emisor:
  * generar el par de claves;
  * firmar una licencia para una instalacion concreta;
  * firmar una lista de revocacion.

Que no puede hacer nadie sin la clave privada: ninguna de las tres.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .. import SECURITY_SCHEMA_VERSION
from ..canonical import b64u_encode
from ..crypto.primitives import (
    generate_signing_key,
    key_id,
    public_key_bytes,
    sign,
    signing_key_bytes,
    signing_key_from_bytes,
)
from ..domain.license import (
    KNOWN_CAPABILITIES,
    LicensePayload,
    RevocationList,
    SignedLicense,
    SignedRevocationList,
)
from ..errors import SecurityError
from ..infrastructure.store import write_json
from ..trust import TRUST_FORMAT

ISSUER_KEY_FORMAT = "bc.issuer-key.v1"

DEFAULT_LEASE_DAYS = 30
DEFAULT_GRACE_DAYS = 14


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass(frozen=True)
class IssuerKey:
    """Par de claves del emisor. `private` solo existe en la maquina que emite."""

    private: Any
    key_id: str
    label: str

    @property
    def public_raw(self) -> bytes:
        return public_key_bytes(self.private.public_key())


def generate(label: str) -> IssuerKey:
    private = generate_signing_key()
    return IssuerKey(
        private=private, key_id=key_id(public_key_bytes(private.public_key())), label=label
    )


def export_private(issuer_key: IssuerKey, sealer, entropy: bytes) -> dict[str, Any]:
    """Clave privada sellada por el sistema operativo de la maquina emisora.

    Nunca se escribe en claro, ni siquiera "temporalmente". Un respaldo fuera
    de linea se hace con `export_private_plaintext`, que existe aparte
    justamente para que aparezca en una revision de codigo.
    """
    return {
        "format": ISSUER_KEY_FORMAT,
        "key_id": issuer_key.key_id,
        "label": issuer_key.label,
        "sealed_private_key": b64u_encode(
            sealer.seal(signing_key_bytes(issuer_key.private), entropy)
        ),
        "public_key": b64u_encode(issuer_key.public_raw),
    }


def export_private_plaintext(issuer_key: IssuerKey) -> str:
    """Clave privada en claro, para el respaldo fuera de linea. Se llama a mano.

    Existe porque la alternativa es peor: una clave de emisor sellada por DPAPI
    y sin copia se pierde con la maquina, y con ella la posibilidad de emitir
    una licencia nueva o de revocar una vieja. El respaldo va a papel o a un
    gestor de contrasenas, nunca a este repositorio ni a la carpeta de BC.

    Tiene nombre largo y explicito a proposito: que aparezca en un `grep` y en
    una revision de codigo es parte del control.
    """
    return b64u_encode(signing_key_bytes(issuer_key.private))


def import_private(document: Mapping[str, Any], sealer, entropy: bytes) -> IssuerKey:
    from ..canonical import b64u_decode

    if document.get("format") != ISSUER_KEY_FORMAT:
        raise SecurityError("archivo de clave de emisor desconocido")
    raw = sealer.open(b64u_decode(str(document["sealed_private_key"])), entropy)
    private = signing_key_from_bytes(raw)
    derived = key_id(public_key_bytes(private.public_key()))
    if derived != str(document.get("key_id", derived)):
        raise SecurityError("el key_id del archivo no corresponde a la clave que contiene")
    return IssuerKey(private=private, key_id=derived, label=str(document.get("label", "")))


def trust_document(issuer_keys: Sequence[IssuerKey]) -> dict[str, Any]:
    """Almacen de confianza para empaquetar en el cliente. Solo claves publicas."""
    return {
        "format": TRUST_FORMAT,
        "issuers": [
            {
                "key_id": item.key_id,
                "label": item.label,
                "public_key": b64u_encode(item.public_raw),
                "active": True,
            }
            for item in issuer_keys
        ],
    }


# --------------------------------------------------------------------------
# Emision
# --------------------------------------------------------------------------
def issue_license(
    issuer_key: IssuerKey,
    *,
    license_id: str,
    installation_id: str,
    organization_id: str,
    branch_id: str,
    business_name: str,
    binding: Mapping[str, str],
    secondary_required: int,
    capabilities: Sequence[str],
    sync_public_key: str = "",
    lease_days: int = DEFAULT_LEASE_DAYS,
    grace_days: int = DEFAULT_GRACE_DAYS,
    valid_days: int | None = None,
    app_version: str = "",
    revocation_id: str = "",
    notes: str = "",
    issued_at: datetime | None = None,
) -> SignedLicense:
    if not binding:
        raise SecurityError("no se emite una licencia sin binding: no ataria a ninguna maquina")
    unknown = sorted(set(capabilities) - set(KNOWN_CAPABILITIES))
    if unknown:
        raise SecurityError(f"capacidades desconocidas: {', '.join(unknown)}")
    if lease_days <= 0 or grace_days < 0:
        raise SecurityError("un lease no positivo dejaria la instalacion sin poder abrir offline")
    issued = issued_at or utc_now()
    payload = LicensePayload(
        license_id=license_id,
        installation_id=installation_id,
        organization_id=organization_id,
        branch_id=branch_id,
        business_name=business_name,
        capabilities=tuple(capabilities),
        issued_at=issued,
        expires_at=issued + timedelta(days=valid_days) if valid_days else None,
        lease_days=lease_days,
        grace_days=grace_days,
        binding=dict(binding),
        secondary_required=secondary_required,
        security_schema_version=SECURITY_SCHEMA_VERSION,
        app_version=app_version,
        revocation_id=revocation_id or license_id,
        issuer_key_id=issuer_key.key_id,
        sync_public_key=sync_public_key,
        notes=notes,
    )
    from ..canonical import canonical_json

    signature = sign(issuer_key.private, canonical_json(payload.to_document()))
    return SignedLicense(payload=payload, signature=signature, key_id=issuer_key.key_id)


def issue_revocations(
    issuer_key: IssuerKey,
    *,
    serial: int,
    revoked_installations: Sequence[str] = (),
    revoked_licenses: Sequence[str] = (),
    reasons: Mapping[str, str] | None = None,
    issued_at: datetime | None = None,
) -> SignedRevocationList:
    if serial <= 0:
        raise SecurityError("el serial de revocacion arranca en 1 y solo sube")
    revocations = RevocationList(
        serial=serial,
        issued_at=issued_at or utc_now(),
        revoked_installations=tuple(revoked_installations),
        revoked_licenses=tuple(revoked_licenses),
        reasons=dict(reasons or {}),
        issuer_key_id=issuer_key.key_id,
    )
    from ..canonical import canonical_json

    signature = sign(issuer_key.private, canonical_json(revocations.to_document()))
    return SignedRevocationList(
        revocations=revocations, signature=signature, key_id=issuer_key.key_id
    )


def save_envelope(path: str | Path, envelope: Mapping[str, Any]) -> Path:
    target = Path(path)
    write_json(target, envelope)
    return target


def load_envelope(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
