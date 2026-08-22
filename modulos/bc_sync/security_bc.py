"""Adapter real hacia BC Seguridad V1; no contiene criptografía ni revocación."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from .security import (
    AuthenticatedMessage, SecurityAuthorizationError, SecurityIdentity,
)


class VerifiedRemoteLicenseProvider(Protocol):
    """Registro servidor gobernado por BC Seguridad, nunca por Sync."""
    def verified_license_for_sync(self, installation_id: str) -> Any: ...


@dataclass(frozen=True)
class _AuthorizedLocal:
    identity: SecurityIdentity
    secret: Any
    license_payload: Any


class BCSecurityIdentityProvider:
    """Obtiene identidad/licencia vigentes del verificador canónico de Seguridad."""
    def __init__(self, verification_context: Any) -> None:
        self.context = verification_context

    @staticmethod
    def _modules():
        try:
            from modulos.seguridad.application import enrollment, verifier
            from modulos.seguridad.domain.license import CAPABILITY_SYNC
        except ImportError as exc:
            raise RuntimeError(
                "BC Seguridad V1 aún no está compuesto en esta rama; promover su PR primero"
            ) from exc
        return enrollment, verifier, CAPABILITY_SYNC

    def _authorized(self) -> _AuthorizedLocal:
        enrollment, verifier, capability_sync = self._modules()
        decision = verifier.authorize(self.context)
        if not decision.allowed:
            raise SecurityAuthorizationError(f"BC Seguridad DENY: {decision.reason}")
        signed_license = verifier.load_license(self.context.paths)
        if signed_license is None:
            raise SecurityAuthorizationError("BC Seguridad DENY: licencia ausente")
        payload = signed_license.payload
        if not payload.allows(capability_sync):
            raise SecurityAuthorizationError("BC Seguridad DENY: licencia sin bc.sync")
        if payload.installation_id != decision.installation_id:
            raise SecurityAuthorizationError("BC Seguridad DENY: installation mismatch")
        secret = enrollment.open_secret(
            self.context.paths, self.context.sealer, self.context.fingerprint
        )
        return _AuthorizedLocal(
            SecurityIdentity(payload.installation_id, payload.branch_id, payload.license_id,
                             payload.security_schema_version), secret, payload)

    def current_sync_identity(self) -> SecurityIdentity:
        return self._authorized().identity


class BCSecuritySyncAuthProvider:
    """Firma y verifica usando exclusivamente primitivas públicas de Seguridad V1."""
    OPERATION = "bc.sync.event.v1"

    def __init__(self, identity_provider: BCSecurityIdentityProvider,
                 remote_licenses: VerifiedRemoteLicenseProvider,
                 nonce_database: str | Path) -> None:
        self.identity_provider = identity_provider
        self.remote_licenses = remote_licenses
        self.nonce_database = Path(nonce_database)

    @staticmethod
    def _sync_auth():
        try:
            from modulos.seguridad.application import sync_auth
        except ImportError as exc:
            raise RuntimeError(
                "BC Seguridad V1 aún no está compuesto en esta rama; promover su PR primero"
            ) from exc
        return sync_auth

    def sign_event(self, body: Mapping[str, Any]) -> AuthenticatedMessage:
        authorized = self.identity_provider._authorized()
        self._validate_metadata(body, authorized.identity)
        sync_auth = self._sync_auth()
        request = sync_auth.SyncRequest(
            operation=self.OPERATION,
            installation_id=authorized.identity.installation_id,
            idempotency_key=str(body["idempotency_key"]), payload=dict(body))
        credential = sync_auth.issue_credential(authorized.secret, request)
        return AuthenticatedMessage(dict(body), credential.to_envelope())

    def verify_event(self, message: AuthenticatedMessage) -> SecurityIdentity:
        sync_auth = self._sync_auth()
        credential = sync_auth.SyncCredential.from_envelope(message.credential)
        claimed_installation = str(message.body.get("installation_id", ""))
        if credential.installation_id != claimed_installation:
            raise SecurityAuthorizationError("installation_id autodeclarado no coincide")
        # Este proveedor verifica firma/licencia/revocación antes de devolver el payload.
        license_payload = self.remote_licenses.verified_license_for_sync(claimed_installation)
        ledger = sync_auth.NonceLedger(self.nonce_database)
        verified = sync_auth.verify_credential(
            credential, license_payload, dict(message.body), ledger=ledger)
        identity = SecurityIdentity(
            verified.installation_id, verified.branch_id, license_payload.license_id,
            license_payload.security_schema_version)
        self._validate_metadata(message.body, identity)
        if credential.operation != self.OPERATION:
            raise SecurityAuthorizationError("operación autenticada incorrecta")
        return identity

    @staticmethod
    def _validate_metadata(body: Mapping[str, Any], identity: SecurityIdentity) -> None:
        required = ("installation_id", "branch_id", "event_id", "timestamp",
                    "schema_version", "idempotency_key")
        if any(not body.get(name) for name in required):
            raise SecurityAuthorizationError("metadata autenticada incompleta")
        if str(body["installation_id"]) != identity.installation_id:
            raise SecurityAuthorizationError("installation_id inconsistente")
        if str(body["branch_id"]).upper() != identity.branch_id.upper():
            raise SecurityAuthorizationError("branch_id inconsistente")
