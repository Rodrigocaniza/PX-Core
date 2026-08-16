"""Seguimiento de trabajos entre Pilar, Asuncion y laboratorios.

Circuito logistico puro: no toca importes, cierres, arqueos ni convenios.
Un trabajo mantiene un unico registro y avanza por estados; el atraso no es
un estado almacenado sino una condicion derivada del plazo comprometido, de
modo que un trabajo puede estar EN_LABORATORIO y atrasado a la vez sin
duplicar registros ni perder su etapa real.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time
from enum import Enum
from typing import Iterable, Mapping, Sequence

from .errors import InvalidCashDayError
from .models import BUSINESS_TIMEZONE, new_id, parse_business_date, utc_now


class TrackingStatus(str, Enum):
    """Etapas del circuito. El orden de declaracion es el orden del flujo."""

    SENT_FROM_PILAR = "ENVIADO_DESDE_PILAR"
    RECEIVED_IN_ASUNCION = "RECIBIDO_EN_ASUNCION"
    IN_LABORATORY = "EN_LABORATORIO"
    RECEIVED_FROM_LABORATORY = "RECIBIDO_DEL_LABORATORIO"
    SENT_TO_PILAR = "ENVIADO_A_PILAR"
    RECEIVED_IN_PILAR = "RECIBIDO_EN_PILAR"
    CLOSED = "CERRADO"


class ContactChannel(str, Enum):
    CALL = "LLAMADA"
    WHATSAPP = "WHATSAPP"
    OTHER = "OTRO"


#: Unica fuente de verdad de las transiciones permitidas.
ALLOWED_TRANSITIONS: Mapping[TrackingStatus, tuple[TrackingStatus, ...]] = {
    TrackingStatus.SENT_FROM_PILAR: (TrackingStatus.RECEIVED_IN_ASUNCION,),
    TrackingStatus.RECEIVED_IN_ASUNCION: (TrackingStatus.IN_LABORATORY,),
    TrackingStatus.IN_LABORATORY: (TrackingStatus.RECEIVED_FROM_LABORATORY,),
    TrackingStatus.RECEIVED_FROM_LABORATORY: (
        # Un trabajo puede volver al laboratorio si el trabajo vino mal.
        TrackingStatus.IN_LABORATORY,
        TrackingStatus.SENT_TO_PILAR,
    ),
    TrackingStatus.SENT_TO_PILAR: (TrackingStatus.RECEIVED_IN_PILAR,),
    TrackingStatus.RECEIVED_IN_PILAR: (TrackingStatus.CLOSED,),
    TrackingStatus.CLOSED: (),
}

#: Etapas en las que el trabajo esta fisicamente en poder del laboratorio y,
#: por lo tanto, un plazo vencido significa que hay que llamar.
LATENESS_APPLIES_TO = (TrackingStatus.IN_LABORATORY,)

DEFAULT_EXPECTED_TIME = time(15, 0)


def parse_expected_time(value: time | str | None) -> time | None:
    """Hora esperada tolerante a `15:30`, `15.30` y `1530`."""
    if value in (None, ""):
        return None
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    if isinstance(value, datetime):
        return value.timetz().replace(second=0, microsecond=0)
    text = str(value).strip().replace(".", ":")
    if text.isdigit() and len(text) == 4:
        text = f"{text[:2]}:{text[2:]}"
    for pattern in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).time().replace(second=0, microsecond=0)
        except ValueError:
            continue
    raise InvalidCashDayError(f"hora esperada invalida: {value!r}")


def business_deadline(expected_date: date, expected_time: time | None) -> datetime:
    """Instante de vencimiento en hora local del negocio."""
    return datetime.combine(
        expected_date, expected_time or DEFAULT_EXPECTED_TIME, tzinfo=BUSINESS_TIMEZONE,
    )


@dataclass(frozen=True)
class Laboratory:
    """Linea y WhatsApp son campos distintos a proposito: rara vez coinciden."""

    name: str
    phone_line: str = ""
    whatsapp: str = ""
    active: bool = True
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        if not name:
            raise InvalidCashDayError("el laboratorio requiere nombre")
        object.__setattr__(self, "name", name)
        for attribute in ("phone_line", "whatsapp"):
            object.__setattr__(self, attribute, str(getattr(self, attribute) or "").strip())
        active = self.active
        if isinstance(active, str):
            active = active.strip().lower() in {"1", "true", "si", "sí"}
        object.__setattr__(self, "active", bool(active))

    @property
    def has_contact_details(self) -> bool:
        return bool(self.phone_line or self.whatsapp)


@dataclass(frozen=True)
class TrackingTransition:
    """Traza inmutable de un cambio de etapa."""

    from_status: TrackingStatus | str | None
    to_status: TrackingStatus | str
    responsible: str
    note: str = ""
    recorded_at: datetime = field(default_factory=utc_now)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.from_status is not None:
            object.__setattr__(self, "from_status", TrackingStatus(self.from_status))
        object.__setattr__(self, "to_status", TrackingStatus(self.to_status))
        object.__setattr__(self, "responsible", str(self.responsible or "").strip())
        object.__setattr__(self, "note", str(self.note or "").strip())


@dataclass(frozen=True)
class ContactRecord:
    """Novedad de contacto con el laboratorio, para no llamar dos veces."""

    operator: str
    channel: ContactChannel | str = ContactChannel.CALL
    result: str = ""
    next_expected_date: date | str | None = None
    next_expected_time: time | str | None = None
    recorded_at: datetime = field(default_factory=utc_now)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        operator = str(self.operator or "").strip()
        if not operator:
            raise InvalidCashDayError("la novedad requiere operadora")
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "channel", ContactChannel(self.channel))
        object.__setattr__(self, "result", str(self.result or "").strip())
        if self.next_expected_date not in (None, ""):
            object.__setattr__(
                self, "next_expected_date", parse_business_date(self.next_expected_date),
            )
        else:
            object.__setattr__(self, "next_expected_date", None)
        object.__setattr__(self, "next_expected_time", parse_expected_time(self.next_expected_time))

    def summary(self) -> str:
        """Linea corta para la columna Ultima novedad."""
        hora = self.recorded_at.astimezone(BUSINESS_TIMEZONE).strftime("%H:%M")
        partes = [hora, self.operator, self.channel.value.lower()]
        if self.result:
            partes.append(self.result)
        return " — ".join(partes)


@dataclass(frozen=True)
class TrackedWork:
    """Un trabajo del circuito.

    Reutiliza la identidad existente cuando la hay: `order_id` y
    `cash_entry_id` enlazan con el trabajo/venta ya cargado en Caja. `envelope`
    y `customer_name` solo sostienen el caso en que Pilar registra el trabajo
    antes de que exista venta en Asuncion.
    """

    envelope: str
    customer_name: str
    status: TrackingStatus | str = TrackingStatus.SENT_FROM_PILAR
    origin_branch: str = "PILAR"
    laboratory_id: str | None = None
    expected_date: date | str | None = None
    expected_time: time | str | None = None
    confirmed_for_next_day: bool = False
    order_id: str | None = None
    cash_entry_id: str | None = None
    consultation_date: date | str | None = None
    observations: str = ""
    created_by: str = ""
    transitions: tuple[TrackingTransition, ...] = ()
    contacts: tuple[ContactRecord, ...] = ()
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        envelope = str(self.envelope or "").strip()
        customer = str(self.customer_name or "").strip()
        if not envelope and not customer:
            raise InvalidCashDayError("el trabajo requiere sobre o cliente")
        object.__setattr__(self, "envelope", envelope)
        object.__setattr__(self, "customer_name", customer)
        object.__setattr__(self, "status", TrackingStatus(self.status))
        object.__setattr__(self, "origin_branch", str(self.origin_branch or "").strip().upper())
        object.__setattr__(self, "observations", str(self.observations or "").strip())
        object.__setattr__(self, "created_by", str(self.created_by or "").strip())
        for attribute in ("expected_date", "consultation_date"):
            value = getattr(self, attribute)
            object.__setattr__(
                self, attribute, parse_business_date(value) if value not in (None, "") else None,
            )
        object.__setattr__(self, "expected_time", parse_expected_time(self.expected_time))
        object.__setattr__(self, "confirmed_for_next_day", bool(self.confirmed_for_next_day))
        object.__setattr__(self, "transitions", tuple(self.transitions))
        object.__setattr__(self, "contacts", tuple(self.contacts))

    # -- consultas ---------------------------------------------------------

    @property
    def deadline(self) -> datetime | None:
        if self.expected_date is None:
            return None
        return business_deadline(self.expected_date, self.expected_time)

    def is_overdue(self, now: datetime | None = None) -> bool:
        """Atraso derivado: vence el plazo y el trabajo sigue en laboratorio.

        Una confirmacion para el dia siguiente no borra el atraso por si sola:
        mueve el plazo. Si el nuevo plazo tambien vence, vuelve a estar
        atrasado sin intervencion.
        """
        if self.status not in LATENESS_APPLIES_TO:
            return False
        deadline = self.deadline
        if deadline is None:
            return False
        moment = now or datetime.now(BUSINESS_TIMEZONE)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=BUSINESS_TIMEZONE)
        return moment >= deadline

    @property
    def last_contact(self) -> ContactRecord | None:
        return self.contacts[-1] if self.contacts else None

    def last_news(self) -> str:
        contact = self.last_contact
        if contact is not None:
            return contact.summary()
        if self.transitions:
            ultima = self.transitions[-1]
            hora = ultima.recorded_at.astimezone(BUSINESS_TIMEZONE).strftime("%H:%M")
            return f"{hora} — {ultima.to_status.value}"
        return ""

    def can_transition_to(self, status: TrackingStatus | str) -> bool:
        return TrackingStatus(status) in ALLOWED_TRANSITIONS[self.status]

    # -- comandos ----------------------------------------------------------

    def transition_to(
        self,
        status: TrackingStatus | str,
        *,
        responsible: str = "",
        note: str = "",
        recorded_at: datetime | None = None,
    ) -> "TrackedWork":
        target = TrackingStatus(status)
        if not self.can_transition_to(target):
            raise InvalidCashDayError(
                f"transicion invalida: {self.status.value} -> {target.value}"
            )
        transicion = TrackingTransition(
            from_status=self.status, to_status=target, responsible=responsible,
            note=note, recorded_at=recorded_at or utc_now(),
        )
        cambios: dict = {
            "status": target,
            "transitions": self.transitions + (transicion,),
            "updated_at": transicion.recorded_at,
        }
        if target is not TrackingStatus.IN_LABORATORY:
            # El plazo pertenece a la estadia en laboratorio: al salir de ella
            # deja de existir y con el desaparece cualquier atraso heredado.
            cambios.update(
                expected_date=None, expected_time=None, confirmed_for_next_day=False,
            )
        return replace(self, **cambios)

    def send_to_laboratory(
        self,
        laboratory_id: str,
        *,
        expected_date: date | str,
        expected_time: time | str | None = None,
        responsible: str = "",
        note: str = "",
        recorded_at: datetime | None = None,
    ) -> "TrackedWork":
        if not str(laboratory_id or "").strip():
            raise InvalidCashDayError("el envio a laboratorio requiere laboratorio")
        enviado = self.transition_to(
            TrackingStatus.IN_LABORATORY, responsible=responsible, note=note,
            recorded_at=recorded_at,
        )
        return replace(
            enviado,
            laboratory_id=str(laboratory_id).strip(),
            expected_date=parse_business_date(expected_date),
            expected_time=parse_expected_time(expected_time) or DEFAULT_EXPECTED_TIME,
            confirmed_for_next_day=False,
        )

    def register_contact(self, contact: ContactRecord) -> "TrackedWork":
        """Registra la novedad y, si trae nuevo plazo, lo compromete."""
        cambios: dict = {
            "contacts": self.contacts + (contact,),
            "updated_at": contact.recorded_at,
        }
        if contact.next_expected_date is not None:
            cambios.update(
                expected_date=contact.next_expected_date,
                expected_time=contact.next_expected_time or self.expected_time
                or DEFAULT_EXPECTED_TIME,
                confirmed_for_next_day=True,
            )
        return replace(self, **cambios)


def group_overdue_by_laboratory(
    works: Iterable[TrackedWork],
    laboratories: Mapping[str, Laboratory] | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """Agrupa atrasados por laboratorio para llamar una vez por laboratorio."""
    catalogo = dict(laboratories or {})
    agrupado: dict[str | None, list[TrackedWork]] = {}
    for work in works:
        if work.is_overdue(now):
            agrupado.setdefault(work.laboratory_id, []).append(work)
    grupos = []
    for laboratory_id, pendientes in agrupado.items():
        laboratory = catalogo.get(laboratory_id) if laboratory_id else None
        grupos.append({
            "laboratory_id": laboratory_id,
            "laboratory": laboratory,
            "name": laboratory.name if laboratory else "Sin laboratorio",
            "phone_line": laboratory.phone_line if laboratory else "",
            "whatsapp": laboratory.whatsapp if laboratory else "",
            "count": len(pendientes),
            "works": tuple(sorted(pendientes, key=lambda item: (item.deadline or datetime.max.replace(tzinfo=BUSINESS_TIMEZONE), item.envelope))),
        })
    return sorted(grupos, key=lambda grupo: (-grupo["count"], grupo["name"]))


def operational_summary(
    works: Sequence[TrackedWork], now: datetime | None = None,
) -> dict[str, int]:
    """Indicadores de la barra superior. Solo excepciones y acciones."""
    por_estado = {status: 0 for status in TrackingStatus}
    for work in works:
        por_estado[work.status] += 1
    atrasados = sum(1 for work in works if work.is_overdue(now))
    confirmados = sum(
        1 for work in works
        if work.confirmed_for_next_day and not work.is_overdue(now)
        and work.status is TrackingStatus.IN_LABORATORY
    )
    return {
        "por_recibir_en_asuncion": por_estado[TrackingStatus.SENT_FROM_PILAR],
        "en_laboratorio": por_estado[TrackingStatus.IN_LABORATORY],
        "atrasados": atrasados,
        "confirmados_para_manana": confirmados,
        "listos_para_enviar_a_pilar": por_estado[TrackingStatus.RECEIVED_FROM_LABORATORY],
        "en_transito_a_pilar": por_estado[TrackingStatus.SENT_TO_PILAR],
    }


def reception_progress(works: Sequence[TrackedWork]) -> dict[str, int]:
    """Enviados desde Pilar contra recibidos en Asuncion.

    Recibido es cualquier etapa posterior a la recepcion: un trabajo que ya
    fue al laboratorio sigue contando como recibido.
    """
    enviados = len(works)
    pendientes = sum(1 for work in works if work.status is TrackingStatus.SENT_FROM_PILAR)
    return {
        "enviados": enviados,
        "recibidos": enviados - pendientes,
        "falta_recibir": pendientes,
    }


def overdue_alert(works: Sequence[TrackedWork], now: datetime | None = None) -> str:
    total = sum(1 for work in works if work.is_overdue(now))
    if not total:
        return ""
    sustantivo = "trabajo atrasado" if total == 1 else "trabajos atrasados"
    return f"{total} {sustantivo} — contactar laboratorios"
