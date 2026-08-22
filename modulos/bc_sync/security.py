"""Puertos de BC Seguridad. Sync no administra usuarios ni secretos globales."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Any


@dataclass(frozen=True)
class SignedMessage:
    installation_id: str
    nonce: str
    timestamp: str
    body: Mapping[str, Any]
    signature: str


class SecurityAdapter(Protocol):
    """Compatibilidad V1 para tests previos; no usar en despliegues nuevos."""
    def sign(self, installation_id: str, body: Mapping[str, Any]) -> SignedMessage: ...
    def verify(self, message: SignedMessage) -> None: ...
    def is_revoked(self, installation_id: str) -> bool: ...


class SecurityAuthorizationError(PermissionError):
    """BC Seguridad denegó una operación de Sync sin exponer secretos."""


@dataclass(frozen=True)
class SecurityIdentity:
    installation_id: str
    branch_id: str
    license_id: str
    security_schema_version: str


@dataclass(frozen=True)
class AuthenticatedMessage:
    """Evento y credencial opaca emitida íntegramente por BC Seguridad."""
    body: Mapping[str, Any]
    credential: Mapping[str, Any]


class SecurityIdentityProvider(Protocol):
    def current_sync_identity(self) -> SecurityIdentity: ...


class SyncSignerAuthProvider(Protocol):
    def sign_event(self, body: Mapping[str, Any]) -> AuthenticatedMessage: ...
    def verify_event(self, message: AuthenticatedMessage) -> SecurityIdentity: ...
