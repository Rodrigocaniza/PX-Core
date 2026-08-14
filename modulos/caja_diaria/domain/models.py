"""Modelos y cálculos puros de BC Caja.

Los importes son enteros en guaraníes. Ordenes, Cuotas y Saldo permanecen
deliberadamente como texto hasta resolver sus reglas de negocio.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Iterable, Mapping
from uuid import uuid4

from .errors import CashDayClosedError, InvalidCashCountError, InvalidCashDayError, InvalidMoneyError


DENOMINATIONS = (100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 100, 50)
BUSINESS_TIMEZONE = timezone(timedelta(hours=-3), "America/Asuncion")


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


class CashEntryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    VOIDED = "VOIDED"


class CashCountStatus(str, Enum):
    OK = "OK"
    SURPLUS = "SOBRA"
    SHORTAGE = "FALTA"


class OrderOrigin(str, Enum):
    CASH_REGISTER = "CAJA"
    WHATSAPP = "WHATSAPP"
    WEB = "WEB"
    WORKSHOP = "TALLER"


class OrderStatus(str, Enum):
    PENDING = "PENDIENTE"
    READY = "LISTO"
    DELIVERED = "ENTREGADO"


@dataclass(frozen=True)
class SaleItem:
    description: str = "Producto"
    code: str = ""
    item_type: str = ""
    frame_price: int | str | None = None
    lens_price: int | str | None = None
    laboratory: str = ""
    prescription_doctor: str = ""
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        object.__setattr__(self, "description", str(self.description or "Producto").strip())
        for name in ("code", "item_type", "laboratory", "prescription_doctor"):
            object.__setattr__(self, name, str(getattr(self, name) or "").strip())
        for name in ("frame_price", "lens_price"):
            object.__setattr__(self, name, money(getattr(self, name), field_name=name, optional=True))

    @property
    def subtotal(self) -> int:
        return (self.frame_price or 0) + (self.lens_price or 0)


@dataclass
class SaleDraft:
    items: list[SaleItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(item.subtotal for item in self.items)

    def add(self, item: SaleItem) -> None:
        self.items.append(item)

    def edit(self, index: int, item: SaleItem) -> None:
        self.items[index] = item

    def remove(self, index: int) -> SaleItem:
        return self.items.pop(index)


@dataclass(frozen=True)
class Order:
    delivery_date: date | str
    branch: str
    customer_name: str
    saleswoman: str
    origin: OrderOrigin | str = OrderOrigin.CASH_REGISTER
    source_reference: str = ""
    customer_document: str = ""
    customer_phone: str = ""
    envelope: str = ""
    status: OrderStatus | str = OrderStatus.PENDING
    observations: str = ""
    cash_entry_id: str | None = None
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "delivery_date", parse_business_date(self.delivery_date))
        object.__setattr__(self, "origin", OrderOrigin(self.origin))
        object.__setattr__(self, "status", OrderStatus(self.status))
        for name in ("branch", "customer_name", "saleswoman"):
            value = str(getattr(self, name) or "").strip()
            if not value:
                raise InvalidCashDayError(f"{name} es obligatorio")
            object.__setattr__(self, name, value)
        for name in (
            "source_reference", "customer_document", "customer_phone",
            "envelope", "observations",
        ):
            object.__setattr__(self, name, str(getattr(self, name) or "").strip())

    def transition_to(self, status: OrderStatus | str) -> "Order":
        target = OrderStatus(status)
        allowed = {
            OrderStatus.PENDING: {OrderStatus.READY},
            OrderStatus.READY: {OrderStatus.DELIVERED},
            OrderStatus.DELIVERED: set(),
        }
        if target not in allowed[self.status]:
            raise InvalidCashDayError(
                f"transición de pedido inválida: {self.status.value} → {target.value}"
            )
        return replace(self, status=target, updated_at=utc_now())


@dataclass(frozen=True)
class CashTotals:
    total: int = 0
    cash: int = 0
    card_check: int = 0
    expenses: int = 0
    expected_cash: int = 0
    entry_count: int = 0
    withdrawals: int = 0


@dataclass(frozen=True)
class SessionHours:
    """Resultado auditable del horario de una Caja cerrada.

    ``overtime_minutes`` conserva los minutos reales transcurridos desde el
    final de la tolerancia. No aplica redondeo. En domingos, donde todavía no
    existe política, ambos campos quedan NULL.
    """

    duration_seconds: int
    overtime_triggered: bool | None
    overtime_minutes: int | None


def calculate_session_hours(
    *, business_date: date, opened_at: datetime, closed_at: datetime
) -> SessionHours:
    if opened_at.tzinfo is None or closed_at.tzinfo is None:
        raise InvalidCashDayError("apertura y cierre requieren zona horaria")
    duration_seconds = int((closed_at - opened_at).total_seconds())
    if duration_seconds < 0:
        raise InvalidCashDayError("la hora de cierre no puede ser anterior a la apertura")

    weekday = business_date.weekday()
    if weekday <= 4:
        tolerance_end = time(18, 10)
    elif weekday == 5:
        tolerance_end = time(12, 10)
    else:
        return SessionHours(duration_seconds, None, None)

    local_close_at = closed_at.astimezone(BUSINESS_TIMEZONE)
    tolerance_end_at = datetime.combine(
        local_close_at.date(), tolerance_end, tzinfo=BUSINESS_TIMEZONE
    )
    overtime_seconds = int((local_close_at - tolerance_end_at).total_seconds())
    overtime_minutes = max(0, overtime_seconds // 60)
    triggered = overtime_minutes > 0
    return SessionHours(duration_seconds, triggered, overtime_minutes)


def client_balance_from_classification(
    total: int | None,
    cash: int | None,
    card_check: int | None,
    agreement_amount: int | None,
) -> int:
    """Saldo cliente: convenio liquida la deuda sin ser ingreso de caja."""
    return max(
        0,
        (total or 0) - (cash or 0) - (card_check or 0) - (agreement_amount or 0),
    )

@dataclass(frozen=True)
class CashEntry:
    description: str
    total: int | str | None = None
    cash: int | str | None = None
    card_check: int | str | None = None
    expenses: int | str | None = None
    withdrawal: int | str | None = None
    withdrawal_destination: str = ""
    performed_by: str = ""
    outflow_type: str = ""
    envelope: str = ""
    frame_origin: str = ""
    code: str = ""
    frame: str = ""
    lens: str = ""
    laboratory: str = ""
    prescription_doctor: str = ""
    orders: str = ""
    agreement_amount: int | str | None = None
    installments: str = ""
    balance: str = ""
    origin: str = "manual"
    source_reference: str = ""
    customer_document: str = ""
    saleswoman: str = ""
    customer_phone: str = ""
    delivery_date: date | str | None = None
    observations: str = ""
    items: tuple[SaleItem, ...] = ()
    id: str = field(default_factory=new_id)
    cash_day_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    status: CashEntryStatus = CashEntryStatus.ACTIVE
    voided_at: datetime | None = None
    void_reason: str = ""
    revision: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise InvalidCashDayError("la descripción de una entrada es obligatoria")
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "status", CashEntryStatus(self.status))
        for name in ("total", "cash", "card_check", "agreement_amount", "expenses", "withdrawal"):
            object.__setattr__(self, name, money(getattr(self, name), field_name=name, optional=True))
        for name in (
            "envelope", "frame_origin", "code", "frame", "lens", "laboratory", "prescription_doctor",
            "orders", "installments", "balance", "origin", "source_reference",
            "customer_document", "customer_phone", "saleswoman", "observations", "withdrawal_destination",
            "performed_by",
            "outflow_type",
        ):
            value = getattr(self, name)
            object.__setattr__(self, name, "" if value is None else str(value).strip())
        inferred_outflow_type = self.outflow_type.upper()
        if not inferred_outflow_type and self.expenses:
            inferred_outflow_type = "GASTO"
        if not inferred_outflow_type and self.withdrawal:
            inferred_outflow_type = "ENTREGA_ADMINISTRACION"
        if inferred_outflow_type not in {"", "GASTO", "ENTREGA_ADMINISTRACION"}:
            raise InvalidCashDayError("el tipo de salida de caja no es válido")
        if self.expenses and self.withdrawal:
            raise InvalidCashDayError("una salida no puede ser gasto y entrega simultáneamente")
        if inferred_outflow_type == "GASTO" and not self.expenses:
            raise InvalidCashDayError("un gasto requiere monto")
        if inferred_outflow_type == "ENTREGA_ADMINISTRACION" and not self.withdrawal:
            raise InvalidCashDayError("una entrega a administración requiere monto")
        object.__setattr__(self, "outflow_type", inferred_outflow_type)
        if self.delivery_date in (None, ""):
            object.__setattr__(self, "delivery_date", None)
        else:
            object.__setattr__(self, "delivery_date", parse_business_date(self.delivery_date))
        object.__setattr__(self, "items", tuple(
            item if isinstance(item, SaleItem) else SaleItem(**item) for item in self.items
        ))
        if self.items:
            object.__setattr__(self, "total", sum(item.subtotal for item in self.items))

        pending_before_agreement = max(0, (self.total or 0) - (self.cash or 0) - (self.card_check or 0))
        if (self.agreement_amount or 0) > pending_before_agreement:
            raise InvalidCashDayError("el monto convenio excede el total pendiente")
        if self.agreement_amount and not self.orders:
            raise InvalidCashDayError("ingresÃ¡ el nombre o identificaciÃ³n del convenio")
        if self.agreement_amount:
            object.__setattr__(self, "balance", str(self.client_balance_amount))

    @property
    def client_balance_amount(self) -> int:
        """Deuda del cliente; el convenio es financiación separada, no saldo."""
        return client_balance_from_classification(
            self.total, self.cash, self.card_check, self.agreement_amount
        )
    @property
    def effective_items(self) -> tuple[SaleItem, ...]:
        if self.items:
            return self.items
        if self.expenses or self.withdrawal:
            return ()
        return (SaleItem(
            description=self.description, code=self.code, item_type=self.frame_origin,
            frame_price=self.frame, lens_price=self.lens, laboratory=self.laboratory,
            prescription_doctor=self.prescription_doctor,
        ),)
        object.__setattr__(self, "void_reason", str(self.void_reason or "").strip())
        if self.status is CashEntryStatus.VOIDED:
            if self.voided_at is None or not self.void_reason:
                raise InvalidCashDayError("una entrada anulada requiere fecha y motivo")
        elif self.voided_at is not None or self.void_reason:
            raise InvalidCashDayError("una entrada activa no puede tener datos de anulación")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 0:
            raise InvalidCashDayError("la revisión de una entrada es inválida")

    def assigned_to(self, cash_day_id: str) -> "CashEntry":
        return replace(self, cash_day_id=cash_day_id, updated_at=utc_now())

    def edited(self, **changes) -> "CashEntry":
        if self.status is CashEntryStatus.VOIDED:
            raise InvalidCashDayError("una entrada anulada no puede editarse")
        protected = {"id", "cash_day_id", "created_at", "status", "voided_at", "void_reason", "revision"}
        if protected.intersection(changes):
            raise InvalidCashDayError("la edición intentó modificar campos protegidos")
        return replace(self, **changes, revision=self.revision + 1, updated_at=utc_now())

    def void(self, reason: str) -> "CashEntry":
        normalized = str(reason or "").strip()
        if not normalized:
            raise InvalidCashDayError("el motivo de anulación es obligatorio")
        if self.status is CashEntryStatus.VOIDED:
            raise InvalidCashDayError("la entrada ya está anulada")
        return replace(
            self,
            status=CashEntryStatus.VOIDED,
            voided_at=utc_now(),
            void_reason=normalized,
            revision=self.revision + 1,
            updated_at=utc_now(),
        )


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
    initial_cash_expected: int | str | None = None
    initial_cash_difference: int | str | None = None
    initial_cash_source_day_id: str | None = None
    initial_cash_source_kind: str = ""
    initial_cash_source_count_id: str | None = None
    opened_by: str = ""
    id: str = field(default_factory=new_id)
    status: CashDayStatus = CashDayStatus.OPEN
    entries: list[CashEntry] = field(default_factory=list)
    opened_at: datetime = field(default_factory=utc_now)
    closed_at: datetime | None = None
    closing_totals: CashTotals | None = None
    session_duration_seconds: int | None = None
    overtime_triggered: bool | None = None
    overtime_minutes: int | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self.business_date = parse_business_date(self.business_date)
        self.unit = str(self.unit).strip().upper()
        if not self.unit:
            raise InvalidCashDayError("la unidad es obligatoria")
        parsed_opening = money(self.opening_cash, field_name="opening_cash")
        assert parsed_opening is not None
        self.opening_cash = parsed_opening
        self.initial_cash_expected = money(
            self.initial_cash_expected, field_name="caja inicial esperada", optional=True
        )
        self.initial_cash_difference = (
            None if self.initial_cash_expected is None
            else self.opening_cash - self.initial_cash_expected
        )
        self.initial_cash_source_day_id = (
            str(self.initial_cash_source_day_id).strip() if self.initial_cash_source_day_id else None
        )
        self.initial_cash_source_kind = str(self.initial_cash_source_kind or "").strip()
        self.initial_cash_source_count_id = (
            str(self.initial_cash_source_count_id).strip() if self.initial_cash_source_count_id else None
        )
        self.opened_by = str(self.opened_by or "").strip()
        self.status = CashDayStatus(self.status)
        self.entries = [entry if entry.cash_day_id == self.id else entry.assigned_to(self.id) for entry in self.entries]
        if self.status is CashDayStatus.CLOSED:
            if self.closed_at is None or self.closing_totals is None:
                raise InvalidCashDayError("una Caja CLOSED requiere fecha y snapshot de cierre")
            if self.session_duration_seconds is None:
                session = calculate_session_hours(
                    business_date=self.business_date,
                    opened_at=self.opened_at,
                    closed_at=self.closed_at,
                )
                self.session_duration_seconds = session.duration_seconds
                self.overtime_triggered = session.overtime_triggered
                self.overtime_minutes = session.overtime_minutes

    @classmethod
    def open(
        cls, *, date: date | str, unit: str, opening_cash: int | str,
        initial_cash_expected: int | str | None = None,
        initial_cash_source_day_id: str | None = None, opened_by: str = "",
        initial_cash_source_kind: str = "", initial_cash_source_count_id: str | None = None,
    ) -> "CashDay":
        return cls(
            business_date=date, unit=unit, opening_cash=opening_cash,
            initial_cash_expected=initial_cash_expected,
            initial_cash_source_day_id=initial_cash_source_day_id, opened_by=opened_by,
            initial_cash_source_kind=initial_cash_source_kind,
            initial_cash_source_count_id=initial_cash_source_count_id,
        )

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
        raise InvalidCashDayError("el borrado físico no está permitido; use void_entry")

    def void_entry(self, entry_id: str, reason: str) -> CashEntry:
        self._require_open()
        for index, existing in enumerate(self.entries):
            if existing.id == entry_id:
                voided = existing.void(reason)
                self.entries[index] = voided
                self.version += 1
                return voided
        raise InvalidCashDayError(f"entrada inexistente: {entry_id}")

    def totals(self) -> CashTotals:
        active = [entry for entry in self.entries if entry.status is CashEntryStatus.ACTIVE]
        total = sum(entry.total or 0 for entry in active)
        cash = sum(entry.cash or 0 for entry in active)
        card_check = sum(entry.card_check or 0 for entry in active)
        expenses = sum(entry.expenses or 0 for entry in active)
        withdrawals = sum(entry.withdrawal or 0 for entry in active)
        return CashTotals(
            total, cash, card_check, expenses,
            self.opening_cash + cash - expenses - withdrawals, len(active), withdrawals,
        )

    def close(self, *, closed_at: datetime | None = None) -> "CashDay":
        self._require_open()
        actual_closed_at = closed_at or utc_now()
        session = calculate_session_hours(
            business_date=self.business_date,
            opened_at=self.opened_at,
            closed_at=actual_closed_at,
        )
        self.closing_totals = self.totals()
        self.status = CashDayStatus.CLOSED
        self.closed_at = actual_closed_at
        self.session_duration_seconds = session.duration_seconds
        self.overtime_triggered = session.overtime_triggered
        self.overtime_minutes = session.overtime_minutes
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
