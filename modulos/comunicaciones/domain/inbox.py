"""Dominio de la bandeja unificada, independiente de UI y proveedores."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class ConversationStatus(str, Enum):
    NUEVO = "NUEVO"
    EN_CURSO = "EN_CURSO"
    RESUELTO = "RESUELTO"


class Direction(str, Enum):
    ENTRANTE = "ENTRANTE"
    SALIENTE = "SALIENTE"


ALLOWED_TRANSITIONS = {
    ConversationStatus.NUEVO: {ConversationStatus.EN_CURSO, ConversationStatus.RESUELTO},
    ConversationStatus.EN_CURSO: {ConversationStatus.NUEVO, ConversationStatus.RESUELTO},
    ConversationStatus.RESUELTO: {ConversationStatus.EN_CURSO},
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def identifier() -> str:
    return str(uuid4())


@dataclass(frozen=True)
class Account:
    id: str
    business: str
    branch: str
    label: str
    provider: str = "SIMULADO"
    active: bool = True

    def __post_init__(self) -> None:
        for name in ("id", "business", "branch", "label"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} es obligatorio")


@dataclass(frozen=True)
class Conversation:
    id: str
    account_id: str
    contact_name: str
    contact_reference: str = ""
    status: ConversationStatus = ConversationStatus.NUEVO
    assigned_operator: str = ""
    subject: str = ""
    created_at: datetime = field(default_factory=now_utc)
    updated_at: datetime = field(default_factory=now_utc)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ConversationStatus(self.status))
        if not self.id or not self.account_id or not self.contact_name.strip():
            raise ValueError("conversación, cuenta y contacto son obligatorios")


@dataclass(frozen=True)
class Message:
    id: str
    conversation_id: str
    direction: Direction
    body: str
    occurred_at: datetime = field(default_factory=now_utc)
    operator: str = ""
    provider_reference: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "direction", Direction(self.direction))
        if not self.id or not self.conversation_id or not self.body.strip():
            raise ValueError("mensaje, conversación y contenido son obligatorios")


@dataclass(frozen=True)
class ConversationFilter:
    business: str = ""
    branch: str = ""
    account_id: str = ""
    status: ConversationStatus | None = None
    text: str = ""
    assigned_operator: str = ""


def validate_transition(current: ConversationStatus, target: ConversationStatus) -> None:
    current, target = ConversationStatus(current), ConversationStatus(target)
    if target == current:
        return
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"transición no permitida: {current.value} -> {target.value}")
