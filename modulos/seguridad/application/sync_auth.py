"""Autenticacion de sincronizacion, por instalacion y sin secreto compartido.

La mision lo pide explicito: no una contrasena global que todas las PCs
conocen. Una contrasena compartida tiene el problema de siempre — se filtra
desde la mas descuidada de las maquinas, no se puede revocar de a una, y todo
lo que llega al servidor es "alguien que la sabia".

Aca cada instalacion firma con su propia clave Ed25519, derivada de su secreto
sellado y por lo tanto imposible de reconstruir en otra PC. Gestion Central no
guarda ningun secreto: verifica con la clave publica, que viaja dentro de la
licencia firmada por el emisor. Es una cadena completa:

    emisor  --firma-->  licencia (installation_id + clave publica de sync)
    instalacion  --firma-->  cada operacion

Contra repeticion: cada operacion lleva `nonce` y `timestamp`. El servidor
rechaza un nonce repetido y un timestamp fuera de ventana. Los dos hacen falta
— solo el timestamp deja repetir dentro de la ventana, y solo el nonce obliga
a recordar todos los nonces de la historia.

Idempotencia: `idempotency_key` es de la operacion, no del envio. Reintentar el
mismo cierre con la misma clave no lo duplica; lo que cambia entre reintentos
son `nonce` y `timestamp`, que son del envio.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from ..canonical import b64u_decode, b64u_encode, canonical_json
from ..crypto.primitives import digest, public_key_from_bytes, random_bytes, sign, verify
from ..domain.license import CAPABILITY_SYNC, LicensePayload, format_instant, parse_instant
from ..errors import ReplayError, SecurityError, SignatureError
from .enrollment import InstallationSecret

CREDENTIAL_FORMAT = "bc.sync-auth.v1"

# Ventana de aceptacion del timestamp. Cubre el desfase razonable entre el
# reloj de la optica y el del servidor, y una demora de red generosa. Mas
# ancha alargaria la ventana de repeticion sin ganar nada.
DEFAULT_WINDOW = timedelta(minutes=5)

NONCE_BYTES = 16


@dataclass(frozen=True)
class SyncRequest:
    """Lo que se va a firmar. Cada campo entra en la firma; ninguno decora."""

    operation: str
    installation_id: str
    idempotency_key: str
    payload: Mapping[str, Any]

    def payload_hash(self) -> str:
        return digest(b"sync-payload", canonical_json(self.payload))


@dataclass(frozen=True)
class SyncCredential:
    """Sobre firmado que acompana a una operacion remota."""

    operation: str
    installation_id: str
    idempotency_key: str
    payload_hash: str
    nonce: str
    issued_at: datetime
    signature: bytes

    def signed_document(self) -> dict[str, Any]:
        return {
            "format": CREDENTIAL_FORMAT,
            "operation": self.operation,
            "installation_id": self.installation_id,
            "idempotency_key": self.idempotency_key,
            "payload_hash": self.payload_hash,
            "nonce": self.nonce,
            "issued_at": format_instant(self.issued_at),
        }

    def to_envelope(self) -> dict[str, Any]:
        return {**self.signed_document(), "signature": b64u_encode(self.signature)}

    @classmethod
    def from_envelope(cls, envelope: Mapping[str, Any]) -> "SyncCredential":
        if not isinstance(envelope, Mapping) or envelope.get("format") != CREDENTIAL_FORMAT:
            raise SecurityError("credencial de sincronizacion desconocida")
        try:
            return cls(
                operation=str(envelope["operation"]),
                installation_id=str(envelope["installation_id"]),
                idempotency_key=str(envelope["idempotency_key"]),
                payload_hash=str(envelope["payload_hash"]),
                nonce=str(envelope["nonce"]),
                issued_at=parse_instant(envelope["issued_at"]),
                signature=b64u_decode(str(envelope["signature"])),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise SecurityError("credencial de sincronizacion incompleta") from error


def issue_credential(
    secret: InstallationSecret, request: SyncRequest, *, now: datetime | None = None
) -> SyncCredential:
    """Firma una operacion con la clave de esta instalacion."""
    if request.installation_id != secret.installation_id:
        raise SecurityError("la operacion nombra otra instalacion")
    credential = SyncCredential(
        operation=request.operation,
        installation_id=request.installation_id,
        idempotency_key=request.idempotency_key,
        payload_hash=request.payload_hash(),
        nonce=b64u_encode(random_bytes(NONCE_BYTES)),
        issued_at=(now or datetime.now(timezone.utc)).replace(microsecond=0),
        signature=b"",
    )
    signature = sign(
        secret.sync_signing_key(), canonical_json(credential.signed_document())
    )
    return SyncCredential(
        operation=credential.operation,
        installation_id=credential.installation_id,
        idempotency_key=credential.idempotency_key,
        payload_hash=credential.payload_hash,
        nonce=credential.nonce,
        issued_at=credential.issued_at,
        signature=signature,
    )


# --------------------------------------------------------------------------
# Lado servidor
# --------------------------------------------------------------------------
class NonceLedger:
    """Nonces ya vistos, en su propia base. Es el estado del servidor, no del cliente.

    Se poda por antiguedad: un nonce mas viejo que la ventana ya no se puede
    reutilizar porque el timestamp lo rechaza primero, asi que guardarlo para
    siempre solo hace crecer la tabla.
    """

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS sync_nonces("
                " installation_id TEXT NOT NULL, nonce TEXT NOT NULL,"
                " seen_at TEXT NOT NULL, PRIMARY KEY(installation_id, nonce))"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database))
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def remember(self, installation_id: str, nonce: str, seen_at: datetime) -> None:
        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "INSERT INTO sync_nonces(installation_id, nonce, seen_at) VALUES(?,?,?)",
                    (installation_id, nonce, format_instant(seen_at)),
                )
            except sqlite3.IntegrityError as error:
                raise ReplayError("esa credencial ya se habia presentado") from error
            connection.commit()

    def prune(self, before: datetime) -> int:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM sync_nonces WHERE seen_at < ?", (format_instant(before),)
            )
            connection.commit()
            removed = cursor.rowcount
        return removed


@dataclass(frozen=True)
class VerifiedOperation:
    installation_id: str
    operation: str
    idempotency_key: str
    organization_id: str
    branch_id: str


def verify_credential(
    credential: SyncCredential,
    license_payload: LicensePayload,
    payload: Mapping[str, Any],
    *,
    ledger: NonceLedger | None = None,
    now: datetime | None = None,
    window: timedelta = DEFAULT_WINDOW,
) -> VerifiedOperation:
    """Verifica una operacion remota contra la licencia de quien dice enviarla.

    Quien llame ya tiene que haber verificado la licencia contra el emisor: aca
    se confia en `license_payload` porque venir de `verifier.verify_license` es
    parte del contrato. Se comprueba explicito que la licencia sea de la misma
    instalacion, para que un llamador distraido no cruce dos.
    """
    if not license_payload.allows(CAPABILITY_SYNC):
        raise SecurityError("la licencia de esa instalacion no autoriza sincronizacion")
    if license_payload.installation_id != credential.installation_id:
        raise SecurityError("la licencia presentada es de otra instalacion")
    if not license_payload.sync_public_key:
        raise SecurityError("la licencia no declara clave publica de sincronizacion")

    instant = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    if abs(instant - credential.issued_at) > window:
        raise SecurityError("la credencial esta fuera de la ventana de tiempo aceptada")

    expected_hash = digest(b"sync-payload", canonical_json(payload))
    if credential.payload_hash != expected_hash:
        raise SecurityError("el contenido no corresponde al que se firmo")

    try:
        verify(
            public_key_from_bytes(b64u_decode(license_payload.sync_public_key)),
            credential.signature,
            canonical_json(credential.signed_document()),
        )
    except (ValueError, SignatureError) as error:
        raise SignatureError("la operacion no esta firmada por esa instalacion") from error

    if ledger is not None:
        # El nonce se registra despues de verificar la firma: si no, cualquiera
        # podria llenar la tabla del servidor con basura sin firmar.
        ledger.remember(credential.installation_id, credential.nonce, instant)

    return VerifiedOperation(
        installation_id=credential.installation_id,
        operation=credential.operation,
        idempotency_key=credential.idempotency_key,
        organization_id=license_payload.organization_id,
        branch_id=license_payload.branch_id,
    )
