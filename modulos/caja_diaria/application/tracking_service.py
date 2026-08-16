"""Servicio del circuito de seguimiento Pilar / laboratorios.

Orquesta el dominio de `domain.tracking` contra el repositorio SQLite local.
No envia correo, no toca importes y no requiere red: la operacion completa
funciona sin internet, igual que el resto de BC Caja.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, Mapping, Sequence

from ..domain.errors import InvalidCashDayError
from ..domain.models import BUSINESS_TIMEZONE, parse_business_date
from ..domain.tracking import (
    DEFAULT_EXPECTED_TIME,
    ContactChannel,
    ContactRecord,
    Laboratory,
    TrackedWork,
    TrackingStatus,
    group_overdue_by_laboratory,
    operational_summary,
    overdue_alert,
    parse_expected_time,
    reception_progress,
)

TRACKING_SETTING_KEY = "tracking"


@dataclass(frozen=True)
class BoardRow:
    """Fila lista para la grilla: el laboratorio ya viene resuelto.

    La operadora ve linea y WhatsApp en la misma fila; no tiene que preguntar
    de que laboratorio se trata ni entrar a otra pantalla a buscar el numero.
    """

    work: TrackedWork
    laboratory: Laboratory | None
    overdue: bool

    @property
    def envelope(self) -> str:
        return self.work.envelope

    @property
    def customer_name(self) -> str:
        return self.work.customer_name

    @property
    def status_label(self) -> str:
        if self.overdue:
            return "ATRASADO"
        if self.work.confirmed_for_next_day and self.work.status is TrackingStatus.IN_LABORATORY:
            return "CONFIRMADO_PARA_MAÑANA"
        return self.work.status.value

    @property
    def laboratory_name(self) -> str:
        return self.laboratory.name if self.laboratory else ""

    @property
    def phone_line(self) -> str:
        return self.laboratory.phone_line if self.laboratory else ""

    @property
    def whatsapp(self) -> str:
        return self.laboratory.whatsapp if self.laboratory else ""

    @property
    def expected_label(self) -> str:
        if self.work.expected_date is None:
            return ""
        fecha = self.work.expected_date.strftime("%d-%m")
        hora = (self.work.expected_time or DEFAULT_EXPECTED_TIME).strftime("%H:%M")
        return f"{fecha} {hora}"

    @property
    def last_news(self) -> str:
        return self.work.last_news()


class TrackingService:
    def __init__(self, repository) -> None:
        self.repository = repository

    # -- configuracion -----------------------------------------------------

    def settings(self) -> dict:
        with self.repository._connection() as connection:
            row = connection.execute(
                "SELECT value_json FROM app_settings WHERE key = ?", (TRACKING_SETTING_KEY,),
            ).fetchone()
        return json.loads(row["value_json"]) if row else {}

    def default_expected_time(self) -> time:
        """Hora esperada por defecto, configurable y nunca cableada."""
        configurado = self.settings().get("default_expected_time")
        try:
            return parse_expected_time(configurado) or DEFAULT_EXPECTED_TIME
        except InvalidCashDayError:
            return DEFAULT_EXPECTED_TIME

    # -- laboratorios ------------------------------------------------------

    def save_laboratory(
        self, *, name: str, phone_line: str = "", whatsapp: str = "",
        active: bool = True, laboratory_id: str | None = None,
    ) -> Laboratory:
        datos = dict(name=name, phone_line=phone_line, whatsapp=whatsapp, active=active)
        if laboratory_id:
            datos["id"] = laboratory_id
        return self.repository.save_laboratory(Laboratory(**datos))

    def list_laboratories(self, *, only_active: bool = False) -> Sequence[Laboratory]:
        return self.repository.list_laboratories(only_active=only_active)

    def laboratory_catalog(self) -> dict[str, Laboratory]:
        return {lab.id: lab for lab in self.repository.list_laboratories()}

    # -- alta desde Pilar --------------------------------------------------

    def register_pilar_batch(
        self, works: Iterable[Mapping], *, consultation_date: date | str,
        created_by: str, origin_branch: str = "PILAR",
    ) -> list[TrackedWork]:
        """Nidia carga la consulta del viernes y la marca enviada desde Pilar."""
        consulta = parse_business_date(consultation_date)
        registrados = []
        for datos in works:
            work = TrackedWork(
                envelope=str(datos.get("envelope", "")),
                customer_name=str(datos.get("customer_name", "")),
                observations=str(datos.get("observations", "")),
                order_id=datos.get("order_id"),
                cash_entry_id=datos.get("cash_entry_id"),
                consultation_date=consulta, created_by=created_by,
                origin_branch=origin_branch,
            )
            registrados.append(self.repository.save_tracked_work(work))
        return registrados

    # -- transiciones ------------------------------------------------------

    def _load(self, work_id: str) -> TrackedWork:
        work = self.repository.get_tracked_work(work_id)
        if work is None:
            raise InvalidCashDayError(f"trabajo inexistente: {work_id}")
        return work

    def _advance(
        self, work_id: str, status: TrackingStatus, *, responsible: str, note: str = "",
    ) -> TrackedWork:
        actualizado = self._load(work_id).transition_to(
            status, responsible=responsible, note=note,
        )
        return self.repository.save_tracked_work(actualizado)

    def receive_in_asuncion(self, work_id: str, *, responsible: str, note: str = "") -> TrackedWork:
        return self._advance(
            work_id, TrackingStatus.RECEIVED_IN_ASUNCION, responsible=responsible, note=note,
        )

    def receive_batch_in_asuncion(
        self, work_ids: Iterable[str], *, responsible: str,
    ) -> list[TrackedWork]:
        return [self.receive_in_asuncion(work_id, responsible=responsible) for work_id in work_ids]

    def send_to_laboratory(
        self, work_id: str, laboratory_id: str, *, expected_date: date | str,
        expected_time: time | str | None = None, responsible: str, note: str = "",
    ) -> TrackedWork:
        if self.repository.get_laboratory(laboratory_id) is None:
            raise InvalidCashDayError(f"laboratorio inexistente: {laboratory_id}")
        actualizado = self._load(work_id).send_to_laboratory(
            laboratory_id, expected_date=expected_date,
            expected_time=expected_time or self.default_expected_time(),
            responsible=responsible, note=note,
        )
        return self.repository.save_tracked_work(actualizado)

    def receive_from_laboratory(
        self, work_id: str, *, responsible: str, note: str = "",
    ) -> TrackedWork:
        return self._advance(
            work_id, TrackingStatus.RECEIVED_FROM_LABORATORY, responsible=responsible, note=note,
        )

    def send_batch_to_pilar(
        self, work_ids: Iterable[str], *, responsible: str, note: str = "",
    ) -> list[TrackedWork]:
        """La encomienda viaja como lote, pero cada trabajo conserva su traza."""
        return [
            self._advance(work_id, TrackingStatus.SENT_TO_PILAR, responsible=responsible, note=note)
            for work_id in work_ids
        ]

    def receive_in_pilar(self, work_id: str, *, responsible: str, note: str = "") -> TrackedWork:
        return self._advance(
            work_id, TrackingStatus.RECEIVED_IN_PILAR, responsible=responsible, note=note,
        )

    def close_work(self, work_id: str, *, responsible: str, note: str = "") -> TrackedWork:
        return self._advance(work_id, TrackingStatus.CLOSED, responsible=responsible, note=note)

    # -- contactos ---------------------------------------------------------

    def register_contact(
        self, work_id: str, *, operator: str, channel: ContactChannel | str = ContactChannel.CALL,
        result: str = "", next_expected_date: date | str | None = None,
        next_expected_time: time | str | None = None,
        recorded_at: datetime | None = None,
    ) -> TrackedWork:
        contacto = ContactRecord(
            operator=operator, channel=channel, result=result,
            next_expected_date=next_expected_date,
            next_expected_time=next_expected_time,
            **({"recorded_at": recorded_at} if recorded_at else {}),
        )
        return self.repository.save_tracked_work(self._load(work_id).register_contact(contacto))

    def confirm_for_next_day(
        self, work_id: str, *, operator: str, next_expected_date: date | str,
        next_expected_time: time | str | None = None,
        channel: ContactChannel | str = ContactChannel.CALL, result: str = "",
        recorded_at: datetime | None = None,
    ) -> TrackedWork:
        """Azucar sobre `register_contact`: confirmar es registrar la novedad."""
        return self.register_contact(
            work_id, operator=operator, channel=channel,
            result=result or "Confirmado para el dia siguiente",
            next_expected_date=next_expected_date,
            next_expected_time=next_expected_time or self.default_expected_time(),
            recorded_at=recorded_at,
        )

    def contact_history(self, work_id: str) -> Sequence[ContactRecord]:
        return self._load(work_id).contacts

    # -- vistas ------------------------------------------------------------

    def list_works(
        self, *, consultation_date: date | str | None = None, status: str | None = None,
        laboratory_id: str | None = None,
    ) -> Sequence[TrackedWork]:
        return self.repository.list_tracked_works(
            consultation_date=parse_business_date(consultation_date)
            if consultation_date not in (None, "") else None,
            status=status or None, laboratory_id=laboratory_id or None,
        )

    def board(
        self, *, consultation_date: date | str | None = None, status: str | None = None,
        laboratory_id: str | None = None, only_overdue: bool = False,
        origin_branch: str | None = None, now: datetime | None = None,
    ) -> dict:
        """Todo lo que la pantalla necesita, resuelto en una sola consulta."""
        momento = now or datetime.now(BUSINESS_TIMEZONE)
        works = list(self.list_works(
            consultation_date=consultation_date, status=status, laboratory_id=laboratory_id,
        ))
        if origin_branch:
            works = [work for work in works if work.origin_branch == origin_branch.strip().upper()]
        catalogo = self.laboratory_catalog()
        filas = [
            BoardRow(
                work=work, laboratory=catalogo.get(work.laboratory_id),
                overdue=work.is_overdue(momento),
            )
            for work in works
        ]
        if only_overdue:
            filas = [fila for fila in filas if fila.overdue]
        # Las excepciones primero: atrasado, luego lo que vence antes.
        filas.sort(key=lambda fila: (
            0 if fila.overdue else 1,
            fila.work.deadline or datetime.max.replace(tzinfo=BUSINESS_TIMEZONE),
            fila.work.envelope,
        ))
        return {
            "rows": filas,
            "summary": operational_summary(works, momento),
            "reception": reception_progress(works),
            "overdue_groups": group_overdue_by_laboratory(works, catalogo, momento),
            "alert": overdue_alert(works, momento),
        }
