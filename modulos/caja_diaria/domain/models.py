"""Modelos y cálculos puros de BC Caja.

Los importes son enteros en guaraníes. Ordenes, Cuotas y Saldo permanecen
deliberadamente como texto hasta resolver sus reglas de negocio.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from enum import Enum
from typing import Iterable, Mapping
from uuid import uuid4

from .errors import CashDayClosedError, InvalidCashCountError, InvalidCashDayError, InvalidMoneyError


DENOMINATIONS = (100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 100, 50)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def new_id() -> str:
    return str(uuid4())


def parse_business_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(value.strip(), pattern).date()
            except ValueError:
                continue
    raise InvalidCashDayError(f"fecha de caja inválida: {value!r}")


def money(value: int | str | None, *, field_name: str, optional: bool = False) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if optional:
            return None
        return 0
    if isinstance(value, bool):
        raise InvalidMoneyError(f"{field_name} debe ser un entero PYG")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip().replace(".", "").replace(" ", "")
        if not normalized or not normalized.lstrip("-").isdigit():
            raise InvalidMoneyError(f"{field_name} inválido: {value!r}")
        parsed = int(normalized)
    else:
        raise InvalidMoneyError(f"{field_name} debe ser un entero PYG")
    if parsed < 0:
        raise InvalidMoneyError(f"{field_name} no puede ser negativo")
    return parsed


class CashDayStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CashCountStatus(str, Enum):
    OK = "OK"
    SURPLUS = "SOBRA"
    SHORTAGE = "FALTA"


@dataclass(frozen=True)
class CashTotals:
    total: int = 0
    cash: int = 0
    card_check: int = 0
    expenses: int = 0
    expected_cash: int = 0
    entry_count: int = 0


@dataclass(frozen=True)
class CashEntry:
    description: str
    total: int | str | None = None
    cash: int | str | None = None
    card_check: int | str | None = None
    expenses: int | str | None = None
    envelope: str = ""
    frame_origin: str = ""
    code: str = ""
    frame: str = ""
    lens: str = ""
    prescription_doctor: str = ""
    orders: str = ""
    installments: str = ""
    balance: str = ""
    origin: str = "manual"
    source_reference: str = ""
    id: str = field(default_factory=new_id)
    cash_day_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise InvalidCashDayError("la descripción de una entrada es obligatoria")
        object.__setattr__(self, "description", self.description.strip())
        for name in ("total", "cash", "card_check", "expenses"):
            object.__setattr__(self, name, money(getattr(self, name), field_name=name, optional=True))
        for name in (
            "envelope", "frame_origin", "code", "frame", "lens", "prescription_doctor",
            "orders", "installments", "balance", "origin", "source_reference",
        ):
            value = getattr(self, name)
            object.__setattr__(self, name, "" if value is None else str(value).strip())

    def assigned_to(self, cash_day_id: str) -> "CashEntry":
        return replace(self, cash_day_id=cash_day_id, updated_at=utc_now())


@dataclass(frozen=True)
class CashCount:
    cash_day_id: str
    quantities: Mapping[int, int]
    counted_total: int
    expected_total: int
    difference: int
    status: CashCountStatus
    id: str = field(default_factory=new_id)
    recorded_at: datetime = field(default_factory=utc_now)

    @classmethod
    def calculate(cls, cash_day_id: str, quantities: Mapping[int, int], expected_total: int) -> "CashCount":
        normalized: dict[int, int] = {}
        for denomination, quantity in quantities.items():
            if denomination not in DENOMINATIONS:
                raise InvalidCashCountError(f"denominación no soportada: {denomination}")
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
                raise InvalidCashCountError(f"cantidad inválida para {denomination}: {quantity!r}")
            normalized[denomination] = quantity
        counted = sum(denomination * quantity for denomination, quantity in normalized.items())
        difference = counted - expected_total
        status = CashCountStatus.OK if difference == 0 else (
            CashCountStatus.SURPLUS if difference > 0 else CashCountStatus.SHORTAGE
        )
        return cls(cash_day_id, normalized, counted, expected_total, difference, status)


@dataclass
class CashDay:
    business_date: date | str
    unit: str
    opening_cash: int | str
    id: str = field(default_factory=new_id)
    status: CashDayStatus = CashDayStatus.OPEN
    entries: list[CashEntry] = field(default_factory=list)
    opened_at: datetime = field(default_factory=utc_now)
    closed_at: datetime | None = None
    closing_totals: CashTotals | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self.business_date = parse_business_date(self.business_date)
        self.unit = str(self.unit).strip().upper()
        if not self.unit:
            raise InvalidCashDayError("la unidad es obligatoria")
        parsed_opening = money(self.opening_cash, field_name="opening_cash")
        assert parsed_opening is not None
        self.opening_cash = parsed_opening
        self.status = CashDayStatus(self.status)
        self.entries = [entry if entry.cash_day_id == self.id else entry.assigned_to(self.id) for entry in self.entries]
        if self.status is CashDayStatus.CLOSED and (self.closed_at is None or self.closing_totals is None):
            raise InvalidCashDayError("una Caja CLOSED requiere fecha y snapshot de cierre")

    @classmethod
    def open(cls, *, date: date | str, unit: str, opening_cash: int | str) -> "CashDay":
        return cls(business_date=date, unit=unit, opening_cash=opening_cash)

    def _require_open(self) -> None:
        if self.status is CashDayStatus.CLOSED:
            raise CashDayClosedError("la Caja está cerrada")

    def add_entry(self, entry: CashEntry) -> CashEntry:
        self._require_open()
        assigned = entry if entry.cash_day_id == self.id else entry.assigned_to(self.id)
        if any(existing.id == assigned.id for existing in self.entries):
            raise InvalidCashDayError(f"entrada duplicada: {assigned.id}")
        self.entries.append(assigned)
        self.version += 1
        return assigned

    def update_entry(self, entry: CashEntry) -> CashEntry:
        self._require_open()
        assigned = entry if entry.cash_day_id == self.id else entry.assigned_to(self.id)
        for index, existing in enumerate(self.entries):
            if existing.id == assigned.id:
                self.entries[index] = assigned
                self.version += 1
                return assigned
        raise InvalidCashDayError(f"entrada inexistente: {entry.id}")

    def remove_entry(self, entry_id: str) -> None:
        self._require_open()
        remaining = [entry for entry in self.entries if entry.id != entry_id]
        if len(remaining) == len(self.entries):
            raise InvalidCashDayError(f"entrada inexistente: {entry_id}")
        self.entries = remaining
        self.version += 1

    def totals(self) -> CashTotals:
        total = sum(entry.total or 0 for entry in self.entries)
        cash = sum(entry.cash or 0 for entry in self.entries)
        card_check = sum(entry.card_check or 0 for entry in self.entries)
        expenses = sum(entry.expenses or 0 for entry in self.entries)
        return CashTotals(total, cash, card_check, expenses, self.opening_cash + cash - expenses, len(self.entries))

    def close(self, *, closed_at: datetime | None = None) -> "CashDay":
        self._require_open()
        self.closing_totals = self.totals()
        self.status = CashDayStatus.CLOSED
        self.closed_at = closed_at or utc_now()
        self.version += 1
        return self

    def count_cash(self, quantities: Mapping[int, int]) -> CashCount:
        return CashCount.calculate(self.id, quantities, self.totals().expected_cash)

    def replace_entries(self, entries: Iterable[CashEntry]) -> None:
        self._require_open()
        assigned = [entry if entry.cash_day_id == self.id else entry.assigned_to(self.id) for entry in entries]
        if len({entry.id for entry in assigned}) != len(assigned):
            raise InvalidCashDayError("el lote contiene IDs de entrada duplicados")
        self.entries = assigned
        self.version += 1
