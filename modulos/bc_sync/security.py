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
    def sign(self, installation_id: str, body: Mapping[str, Any]) -> SignedMessage: ...
    def verify(self, message: SignedMessage) -> None: ...
    def is_revoked(self, installation_id: str) -> bool: ...
