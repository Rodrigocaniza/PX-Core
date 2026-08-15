from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class Unit(str, Enum):
    OPTICA_ASUNCION = "OPTICA_ASUNCION"
    OPTICA_PILAR = "OPTICA_PILAR"
    CONSULTORIO_ASUNCION = "CONSULTORIO_ASUNCION"
    CONSULTORIO_PILAR = "CONSULTORIO_PILAR"

    @property
    def label(self) -> str:
        return {
            self.OPTICA_ASUNCION: "Óptica Asunción",
            self.OPTICA_PILAR: "Óptica Pilar",
            self.CONSULTORIO_ASUNCION: "Consultorio Asunción",
            self.CONSULTORIO_PILAR: "Consultorio Pilar",
        }[self]


class Role(str, Enum):
    ADMIN_CENTRAL = "ADMIN_CENTRAL"
    SUPERVISOR = "SUPERVISOR"
    AUDITOR = "AUDITOR"
    OPERADOR_LOCAL = "OPERADOR_LOCAL"


PERMISSIONS = {
    Role.ADMIN_CENTRAL: frozenset({"dashboard.read", "users.manage", "alerts.manage", "audit.read", "sync.write"}),
    Role.SUPERVISOR: frozenset({"dashboard.read", "alerts.manage", "audit.read"}),
    Role.AUDITOR: frozenset({"dashboard.read", "audit.read"}),
    Role.OPERADOR_LOCAL: frozenset({"dashboard.read", "sync.write"}),
}


@dataclass(frozen=True)
class Principal:
    username: str
    role: Role
    unit: Unit | None = None

    def allows(self, permission: str, unit: Unit | None = None) -> bool:
        if permission not in PERMISSIONS[self.role]:
            return False
        return self.unit is None or unit is None or self.unit == unit


@dataclass(frozen=True)
class CashSnapshot:
    event_id: str
    unit: Unit
    business_date: str
    status: str
    opening_cash: int
    income: int
    cash: int
    card_check: int
    expenses: int
    withdrawals: int
    expected_cash: int
    counted_cash: int | None
    entry_count: int
    source_updated_at: datetime

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id es obligatorio")
        if self.status not in {"OPEN", "CLOSED"}:
            raise ValueError("estado de caja inválido")
        for name in ("opening_cash", "income", "cash", "card_check", "expenses", "withdrawals", "expected_cash", "entry_count"):
            if isinstance(getattr(self, name), bool) or getattr(self, name) < 0:
                raise ValueError(f"{name} no puede ser negativo")
        if self.counted_cash is not None and self.counted_cash < 0:
            raise ValueError("counted_cash no puede ser negativo")
        if self.source_updated_at.tzinfo is None:
            raise ValueError("source_updated_at requiere zona horaria")

    @property
    def difference(self) -> int | None:
        return None if self.counted_cash is None else self.counted_cash - self.expected_cash


@dataclass(frozen=True)
class Alert:
    id: str
    unit: Unit
    kind: str
    severity: str
    message: str
    status: str
    created_at: datetime
    acknowledged_by: str | None = None
