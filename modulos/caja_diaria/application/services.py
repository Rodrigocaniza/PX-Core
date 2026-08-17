"""Servicios de aplicación para orquestar el dominio y el repositorio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Mapping, Sequence

from .ports import CashDayRepository, CarryForwardPolicy
from ..domain.errors import CashDayAlreadyExistsError, CashDayNotFoundError
from ..domain.models import (
    CashCount, CashDay, CashEntry, CashTotals, Order, OrderStatus, parse_business_date
)


#: Grupo canonico de la alerta de la cabecera: lo que hay que entregar y
#: todavia no se entrego. Lo usan por igual el contador de la alerta y la vista
#: que abre el clic, de modo que no puedan decir cosas distintas.
FILTRO_REQUIEREN_ATENCION = "Requieren atención"

#: Grupos operativos de Pedidos, en orden de urgencia. Son una condición
#: derivada de la fecha prometida, no estados guardados.
GRUPO_ATRASADOS = "Atrasados"
GRUPO_PARA_HOY = "Para hoy"
GRUPO_PROXIMOS = "Próximos"


class CashDayService:
    def __init__(self, repository: CashDayRepository, carry_forward_policy: CarryForwardPolicy | None = None) -> None:
        self.repository = repository
        self.carry_forward_policy = carry_forward_policy

    def suggested_opening_cash(self, *, business_date: date | str, unit: str) -> int | None:
        suggestion = self.opening_cash_suggestion(business_date=business_date, unit=unit)
        return suggestion.expected if suggestion else None

    def opening_cash_suggestion(
        self, *, business_date: date | str, unit: str
    ) -> "OpeningCashSuggestion | None":
        if self.carry_forward_policy is None:
            return None
        parsed_date = parse_business_date(business_date)
        normalized_unit = unit.strip().upper()
        previous = self.repository.get_latest_closed_before(parsed_date, normalized_unit)
        if previous is None:
            return None
        count = self.repository.get_latest_cash_count(previous.id)
        if count is not None:
            return OpeningCashSuggestion(count.counted_total, "ARQUEO_PREVIO", previous.id, count.id)
        return OpeningCashSuggestion(
            self.carry_forward_policy.opening_cash_for(previous, parsed_date),
            "CIERRE_ESPERADO", previous.id, None,
        )

    def open_day(
        self, *, business_date: date | str, unit: str, opening_cash: int | str,
        opened_by: str = "",
    ) -> CashDay:
        parsed_date = parse_business_date(business_date)
        normalized_unit = unit.strip().upper()
        if self.repository.get_by_date_and_unit(parsed_date, normalized_unit) is not None:
            raise CashDayAlreadyExistsError(
                f"ya existe una Caja para {parsed_date.isoformat()} / {normalized_unit}"
            )
        suggestion = self.opening_cash_suggestion(
            business_date=parsed_date, unit=normalized_unit
        )
        cash_day = CashDay.open(
            date=parsed_date, unit=normalized_unit, opening_cash=opening_cash,
            initial_cash_expected=suggestion.expected if suggestion else None,
            initial_cash_source_day_id=suggestion.source_day_id if suggestion else None,
            initial_cash_source_kind=suggestion.source_kind if suggestion else "NO_DISPONIBLE",
            initial_cash_source_count_id=suggestion.source_count_id if suggestion else None,
            opened_by=opened_by,
        )
        self.repository.save(cash_day)
        return cash_day

    def open_day_with_entries(
        self,
        *,
        business_date: date | str,
        unit: str,
        opening_cash: int | str,
        entries: Iterable[CashEntry],
    ) -> CashDay:
        """Crea y persiste un día completo en una sola escritura atómica."""
        parsed_date = parse_business_date(business_date)
        normalized_unit = unit.strip().upper()
        if self.repository.get_by_date_and_unit(parsed_date, normalized_unit) is not None:
            raise CashDayAlreadyExistsError(
                f"ya existe una Caja para {parsed_date.isoformat()} / {normalized_unit}"
            )
        cash_day = CashDay.open(date=parsed_date, unit=normalized_unit, opening_cash=opening_cash)
        cash_day.replace_entries(entries)
        self.repository.save(cash_day)
        return cash_day

    def get_day(self, cash_day_id: str) -> CashDay:
        cash_day = self.repository.get(cash_day_id)
        if cash_day is None:
            raise CashDayNotFoundError(f"Caja inexistente: {cash_day_id}")
        return cash_day

    def get_by_date_and_unit(self, business_date: date | str, unit: str) -> CashDay:
        cash_day = self.repository.get_by_date_and_unit(parse_business_date(business_date), unit.strip().upper())
        if cash_day is None:
            raise CashDayNotFoundError(f"Caja inexistente: {business_date} / {unit}")
        return cash_day

    def list_between(
        self, start_date: date | str, end_date: date | str, unit: str | None = None
    ) -> Sequence[CashDay]:
        return self.repository.list_between(
            parse_business_date(start_date),
            parse_business_date(end_date),
            unit.strip().upper() if unit else None,
        )

    def add_entry(self, cash_day_id: str, entry: CashEntry) -> CashEntry:
        cash_day = self.get_day(cash_day_id)
        assigned = cash_day.add_entry(entry)
        self.repository.save(cash_day)
        self._ensure_order(cash_day, assigned)
        return assigned

    def record_withdrawal(
        self, cash_day_id: str, amount: int | str, destination: str = "Administración",
        observations: str = "", performed_by: str = "",
    ) -> CashEntry:
        entry = CashEntry(
            description=f"RETIRO — {destination.strip() or 'Administración'}",
            withdrawal=amount, withdrawal_destination=destination,
            observations=observations, source_reference=observations,
            performed_by=performed_by, origin="cash-withdrawal",
        )
        if not entry.withdrawal:
            raise ValueError("El monto del retiro debe ser mayor a cero.")
        return self.add_entry(cash_day_id, entry)

    def update_entry(
        self, cash_day_id: str, entry: CashEntry, *, reason: str = "", user: str = ""
    ) -> CashEntry:
        cash_day = self.get_day(cash_day_id)
        updated = cash_day.update_entry(entry)
        self.repository.save(cash_day, audit_reason=reason, edited_by=user)
        self._ensure_order(cash_day, updated)
        return updated

    def _ensure_order(self, cash_day: CashDay, entry: CashEntry) -> Order | None:
        if entry.delivery_date is None or entry.status.value != "ACTIVE":
            return None
        order = Order(
            delivery_date=entry.delivery_date, branch=cash_day.unit,
            customer_name=entry.description, customer_document=entry.customer_document,
            customer_phone=entry.customer_phone,
            envelope=entry.envelope, saleswoman=entry.saleswoman,
            observations=entry.observations, cash_entry_id=entry.id,
            source_reference=entry.id,
        )
        return self.repository.save_order(order)

    def list_orders(
        self, *, filter_name: str = "Todos", today: date | str | None = None,
        branch: str | None = None,
    ):
        reference = parse_business_date(today or date.today())
        orders = list(self.repository.list_orders())
        if branch:
            objetivo = str(branch).strip().casefold()
            orders = [item for item in orders if item.branch.strip().casefold() == objetivo]
        if filter_name == FILTRO_REQUIEREN_ATENCION:
            # El grupo que origina la alerta de la cabecera: lo que ya vencio y
            # lo que vence hoy, sin lo ya entregado. Es una sola consulta para
            # que el numero de la alerta y lo que abre el clic no puedan
            # discrepar; antes la alerta sumaba dos grupos y el clic filtraba
            # solo uno, asi que abria vacio.
            orders = [
                item for item in orders
                if item.delivery_date <= reference
                and item.status is not OrderStatus.DELIVERED
            ]
        elif filter_name == "Hoy":
            orders = [item for item in orders if item.delivery_date == reference]
        elif filter_name == "Atrasados":
            orders = [item for item in orders if item.delivery_date < reference and item.status is not OrderStatus.DELIVERED]
        elif filter_name == "Próximos":
            orders = [item for item in orders if item.delivery_date > reference and item.status is not OrderStatus.DELIVERED]
        return sorted(orders, key=lambda item: (
            0 if item.delivery_date < reference and item.status is not OrderStatus.DELIVERED else
            1 if item.delivery_date == reference else 2,
            item.delivery_date, item.created_at,
        ))

    def order_operational_groups(
        self, *, today: date | str | None = None, branch: str | None = None,
    ):
        """Los tres grupos operativos, siempre en orden de urgencia.

        Devuelve los tres aunque estén vacíos: la pantalla decide cuáles muestra
        y, cuando no hay nada urgente, cae en `PRÓXIMOS` en vez de abrir en una
        hoja en blanco.
        """
        reference = parse_business_date(today or date.today())
        pendientes = [
            item for item in self.list_orders(filter_name="Todos", today=reference, branch=branch)
            if item.status is not OrderStatus.DELIVERED
        ]
        orden = lambda item: (item.delivery_date, item.created_at)  # noqa: E731
        return (
            (GRUPO_ATRASADOS,
             sorted([o for o in pendientes if o.delivery_date < reference], key=orden)),
            (GRUPO_PARA_HOY,
             sorted([o for o in pendientes if o.delivery_date == reference], key=orden)),
            (GRUPO_PROXIMOS,
             sorted([o for o in pendientes if o.delivery_date > reference], key=orden)),
        )

    def order_work_details(self, order_ids):
        return self.repository.order_work_details(list(order_ids))

    def latest_order_revisions(self):
        return self.repository.latest_order_revisions()

    def update_order_status(self, order_id: str, status: OrderStatus | str, *, reason: str = "", responsible: str = "Sistema") -> Order:
        return self.repository.update_order_status(order_id, status, reason=reason, responsible=responsible)

    def remove_entry(self, cash_day_id: str, entry_id: str) -> None:
        raise NotImplementedError("el borrado físico fue reemplazado por void_entry")

    def void_entry(
        self, cash_day_id: str, entry_id: str, reason: str, user: str = ""
    ) -> CashEntry:
        cash_day = self.get_day(cash_day_id)
        voided = cash_day.void_entry(entry_id, reason)
        self.repository.save(cash_day, audit_reason=reason, edited_by=user)
        return voided

    def import_entries(self, cash_day_id: str, entries: Iterable[CashEntry]) -> CashDay:
        """Reemplaza el lote completo en una única operación de repositorio."""
        cash_day = self.get_day(cash_day_id)
        cash_day.replace_entries(entries)
        self.repository.save(cash_day)
        return cash_day

    def totals(self, cash_day_id: str) -> CashTotals:
        return self.get_day(cash_day_id).totals()

    def close_day(self, cash_day_id: str, *, closed_at: datetime | None = None) -> CashDay:
        cash_day = self.get_day(cash_day_id)
        cash_day.close(closed_at=closed_at)
        self.repository.save(cash_day)
        return cash_day

    def record_cash_count(self, cash_day_id: str, quantities: Mapping[int, int]) -> CashCount:
        existing = self.repository.get_latest_cash_count(cash_day_id)
        if existing is not None:
            return existing
        cash_count = self.get_day(cash_day_id).count_cash(quantities)
        self.repository.save_cash_count(cash_count)
        return cash_count


@dataclass(frozen=True)
class OpeningCashSuggestion:
    expected: int
    source_kind: str
    source_day_id: str
    source_count_id: str | None
