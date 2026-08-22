from __future__ import annotations

from threading import Event
from typing import Protocol

from .model import SyncEvent
from .security import (
    AuthenticatedMessage, SecurityAdapter, SecurityIdentityProvider,
    SignedMessage, SyncSignerAuthProvider,
)
from .store import SyncStore


class Transport(Protocol):
    def send(self, target: str, message: SignedMessage) -> None: ...


class SyncNode:
    def __init__(self, installation_id: str, branch_id: str, store: SyncStore,
                 security: SecurityAdapter) -> None:
        self.installation_id = installation_id
        self.branch_id = branch_id.upper()
        self.store = store
        self.security = security
        self.identity_provider: SecurityIdentityProvider | None = None
        self.auth_provider: SyncSignerAuthProvider | None = None

    @classmethod
    def secured(cls, store: SyncStore, identity_provider: SecurityIdentityProvider,
                auth_provider: SyncSignerAuthProvider) -> "SyncNode":
        identity = identity_provider.current_sync_identity()
        node = cls(identity.installation_id, identity.branch_id, store, security=None)  # type: ignore[arg-type]
        node.identity_provider, node.auth_provider = identity_provider, auth_provider
        return node

    def publish(self, event_type: str, payload: dict, idempotency_key: str,
                *, occurred_at: str | None = None) -> str:
        if self.identity_provider is not None:
            identity = self.identity_provider.current_sync_identity()
            self.installation_id, self.branch_id = identity.installation_id, identity.branch_id.upper()
        event = SyncEvent.create(installation_id=self.installation_id, branch_id=self.branch_id,
                                 event_type=event_type, payload=payload,
                                 idempotency_key=idempotency_key, occurred_at=occurred_at)
        return self.store.enqueue(event)

    def resume(self, target: str, transport: Transport) -> int:
        sent = 0
        for event in self.store.pending():
            self.store.mark_attempt(event)
            try:
                if self.auth_provider is not None and self.identity_provider is not None:
                    identity = self.identity_provider.current_sync_identity()
                    if (identity.installation_id != event.installation_id or
                            identity.branch_id.upper() != event.branch_id.upper()):
                        raise PermissionError("la identidad vigente no corresponde al evento en outbox")
                    message = self.auth_provider.sign_event(event.wire_dict())
                else:
                    message = self.security.sign(self.installation_id, event.wire_dict())
                transport.send(target, message)
            except Exception as exc:
                self.store.mark_attempt(event, str(exc))
                continue
            self.store.acknowledge(event)
            sent += 1
        return sent

    def receive(self, message: SignedMessage | AuthenticatedMessage) -> bool:
        if isinstance(message, AuthenticatedMessage):
            if self.auth_provider is None:
                raise PermissionError("receptor sin BC Seguridad")
            identity = self.auth_provider.verify_event(message)
            event = SyncEvent.from_wire(message.body)
            if event.installation_id != identity.installation_id:
                raise PermissionError("installation_id verificado no coincide")
            if event.branch_id.upper() != identity.branch_id.upper():
                raise PermissionError("branch_id verificado no coincide")
            return self.store.receive(event)
        if self.security.is_revoked(message.installation_id):
            raise PermissionError("installation_id revocada")
        self.security.verify(message)
        if message.installation_id != str(message.body.get("installation_id")):
            raise PermissionError("identidad firmada no coincide con el evento")
        return self.store.receive(SyncEvent.from_wire(message.body), nonce=message.nonce)


class AutoResumeWorker:
    """Reintenta al arrancar y periódicamente; el proceso puede detenerlo limpiamente."""
    def __init__(self, node: SyncNode, target: str, transport: Transport,
                 *, interval_seconds: float = 30.0) -> None:
        self.node, self.target, self.transport = node, target, transport
        self.interval_seconds = max(0.1, interval_seconds)

    def run_forever(self, stop: Event) -> None:
        while not stop.is_set():
            self.node.resume(self.target, self.transport)
            stop.wait(self.interval_seconds)
