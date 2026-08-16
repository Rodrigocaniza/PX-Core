"""Seguimiento de trabajos entre Pilar, Asuncion y laboratorios.

Circuito logistico puro: no toca importes, cierres, arqueos ni convenios.
Un trabajo mantiene un unico registro y avanza por estados; el atraso no es
un estado almacenado sino una condicion derivada del plazo comprometido, de
modo que un trabajo puede estar EN_LABORATORIO y atrasado a la vez sin
duplicar registros ni perder su etapa real.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
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

class ReceptionIssue(str, Enum):
    """Discrepancias reales al recibir un lote.

    No son etapas del circuito: son condiciones que conviven con la etapa y se
    resuelven recibiendo o corrigiendo. Por eso no entran en `TrackingStatus`.
    """

    NOT_ARRIVED = "NO_LLEGO"
    NOT_IN_LIST = "NO_ESTABA_EN_LISTA"


#: Rotulo con el que la operadora lee la discrepancia en la propia fila.
ETIQUETA_DISCREPANCIA = {
    ReceptionIssue.NOT_ARRIVED: "NO LLEGÓ",
    ReceptionIssue.NOT_IN_LIST: "NO ESTABA EN LISTA",
}


class NextAction(str, Enum):
    """Unica autoridad sobre que corresponde hacer con un trabajo."""

    RECEIVE_IN_ASUNCION = "RECIBIR_EN_ASUNCION"
    SEND_TO_LABORATORY = "ENVIAR_A_LABORATORIO"
    CONTACT_LABORATORY = "CONTACTAR_LABORATORIO"
    RECEIVE_FROM_LABORATORY = "RECIBIR_DEL_LABORATORIO"
    SEND_TO_PILAR = "ENVIAR_A_PILAR"
    RECEIVE_IN_PILAR = "RECIBIR_EN_PILAR"
    RESOLVE_RECEPTION = "RESOLVER_RECEPCION"
    NONE = "NINGUNA"


#: Texto del boton principal para cada accion. La operadora lee que hacer.
ETIQUETA_ACCION = {
    NextAction.RECEIVE_IN_ASUNCION: "Recibir en Asunción",
    NextAction.SEND_TO_LABORATORY: "Enviar a laboratorio",
    NextAction.CONTACT_LABORATORY: "Contactar laboratorio",
    NextAction.RECEIVE_FROM_LABORATORY: "Recibir del laboratorio",
    NextAction.SEND_TO_PILAR: "Enviar a Pilar",
    NextAction.RECEIVE_IN_PILAR: "Recibir en Pilar",
    NextAction.RESOLVE_RECEPTION: "Resolver recepción",
    NextAction.NONE: "Sin acción pendiente",
}

#: Etapa a la que lleva cada accion. `None` cuando la accion no transiciona.
TRANSICION_DE_ACCION = {
    NextAction.RECEIVE_IN_ASUNCION: TrackingStatus.RECEIVED_IN_ASUNCION,
    NextAction.SEND_TO_LABORATORY: TrackingStatus.IN_LABORATORY,
    NextAction.RECEIVE_FROM_LABORATORY: TrackingStatus.RECEIVED_FROM_LABORATORY,
    NextAction.SEND_TO_PILAR: TrackingStatus.SENT_TO_PILAR,
    NextAction.RECEIVE_IN_PILAR: TrackingStatus.RECEIVED_IN_PILAR,
    NextAction.CONTACT_LABORATORY: None,
    NextAction.RESOLVE_RECEPTION: None,
    NextAction.NONE: None,
}


def next_action(
    status: TrackingStatus | str, *, overdue: bool = False,
    reception_issue: ReceptionIssue | str | None = None,
) -> NextAction:
    """Que corresponde hacer ahora. Fuente unica para dominio, servicio y UI.

    Ninguna otra capa decide esto: la barra de acciones, las alertas y las
    operaciones masivas preguntan aca, de modo que no puedan discrepar.
    """
    etapa = TrackingStatus(status)
    if reception_issue is not None and ReceptionIssue(reception_issue) is ReceptionIssue.NOT_ARRIVED:
        # Figuraba en el envio pero no aparecio: no avanza hasta resolverse.
        return NextAction.RESOLVE_RECEPTION
    if etapa is TrackingStatus.SENT_FROM_PILAR:
        return NextAction.RECEIVE_IN_ASUNCION
    if etapa is TrackingStatus.RECEIVED_IN_ASUNCION:
        return NextAction.SEND_TO_LABORATORY
    if etapa is TrackingStatus.IN_LABORATORY:
        return (NextAction.CONTACT_LABORATORY if overdue
                else NextAction.RECEIVE_FROM_LABORATORY)
    if etapa is TrackingStatus.RECEIVED_FROM_LABORATORY:
        return NextAction.SEND_TO_PILAR
    if etapa is TrackingStatus.SENT_TO_PILAR:
        return NextAction.RECEIVE_IN_PILAR
    return NextAction.NONE


#: Sucursal de proceso por defecto: donde se reciben los trabajos de la
#: consulta y desde donde se despachan a los laboratorios.
SUCURSAL_PROCESO_POR_DEFECTO = "ASUNCION"

#: Que sucursal tiene la proxima accion en cada etapa. `ORIGEN` es la que
#: mando el trabajo (Pilar en el caso canonico) y `PROCESO` la que lo recibe y
#: gestiona con los laboratorios. La responsabilidad se deriva de la etapa, no
#: de quien cargo el trabajo ni de que cajera esta operando.
ORIGEN, PROCESO, NADIE = "ORIGEN", "PROCESO", None
RESPONSABLE_POR_ETAPA: Mapping[TrackingStatus, str | None] = {
    # Salio de la consulta: le toca recibirlo a la sucursal de proceso.
    TrackingStatus.SENT_FROM_PILAR: PROCESO,
    TrackingStatus.RECEIVED_IN_ASUNCION: PROCESO,
    TrackingStatus.IN_LABORATORY: PROCESO,
    TrackingStatus.RECEIVED_FROM_LABORATORY: PROCESO,
    # Va en encomienda de vuelta: le toca recibirlo a la sucursal de origen.
    TrackingStatus.SENT_TO_PILAR: ORIGEN,
    # Circuito completo: ya no hay proxima accion.
    TrackingStatus.RECEIVED_IN_PILAR: NADIE,
    TrackingStatus.CLOSED: NADIE,
}


def normalizar_sucursal(valor: str | None) -> str:
    return str(valor or "").strip().upper()


def sucursal_responsable(
    status: TrackingStatus | str, *, origin_branch: str,
    processing_branch: str = SUCURSAL_PROCESO_POR_DEFECTO,
) -> str | None:
    """Sucursal a la que le toca la proxima accion, o None si termino."""
    rol = RESPONSABLE_POR_ETAPA[TrackingStatus(status)]
    if rol is NADIE:
        return None
    return normalizar_sucursal(origin_branch if rol is ORIGEN else processing_branch)


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
class PilarShipment:
    """Envio agrupado de Pilar a Asuncion.

    El lote existe para cargar y recibir en bloque, no para reemplazar al
    trabajo: cada `TrackedWork` conserva su id, su traza y su estado propio, y
    el lote solo deriva su condicion de los trabajos que contiene.
    """

    shipped_on: date | str
    operator: str
    origin_branch: str = "PILAR"
    destination_branch: str = "ASUNCION"
    consultation_date: date | str | None = None
    note: str = ""
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        operator = str(self.operator or "").strip()
        if not operator:
            raise InvalidCashDayError("el envio requiere operadora")
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "shipped_on", parse_business_date(self.shipped_on))
        for attribute in ("origin_branch", "destination_branch"):
            valor = str(getattr(self, attribute) or "").strip().upper()
            if not valor:
                raise InvalidCashDayError(f"{attribute} es obligatorio")
            object.__setattr__(self, attribute, valor)
        if self.consultation_date not in (None, ""):
            object.__setattr__(
                self, "consultation_date", parse_business_date(self.consultation_date),
            )
        else:
            object.__setattr__(self, "consultation_date", self.shipped_on)
        object.__setattr__(self, "note", str(self.note or "").strip())


def shipment_progress(works: Sequence[TrackedWork]) -> dict:
    """Condicion del lote derivada de sus trabajos, nunca almacenada."""
    progreso = reception_progress(works)
    if not works:
        estado = "VACIO"
    elif progreso["falta_recibir"] == 0:
        estado = "RECIBIDO_COMPLETO"
    elif progreso["recibidos"] == 0:
        estado = "ENVIADO"
    else:
        estado = "RECEPCION_PARCIAL"
    return {**progreso, "estado": estado}


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
    processing_branch: str = SUCURSAL_PROCESO_POR_DEFECTO
    reception_issue: ReceptionIssue | str | None = None
    order_id: str | None = None
    cash_entry_id: str | None = None
    shipment_id: str | None = None
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
        object.__setattr__(self, "origin_branch", normalizar_sucursal(self.origin_branch))
        object.__setattr__(
            self, "processing_branch",
            normalizar_sucursal(self.processing_branch) or SUCURSAL_PROCESO_POR_DEFECTO)
        object.__setattr__(self, "observations", str(self.observations or "").strip())
        object.__setattr__(self, "created_by", str(self.created_by or "").strip())
        for attribute in ("expected_date", "consultation_date"):
            value = getattr(self, attribute)
            object.__setattr__(
                self, attribute, parse_business_date(value) if value not in (None, "") else None,
            )
        object.__setattr__(self, "expected_time", parse_expected_time(self.expected_time))
        object.__setattr__(self, "confirmed_for_next_day", bool(self.confirmed_for_next_day))
        if self.reception_issue not in (None, ""):
            object.__setattr__(self, "reception_issue", ReceptionIssue(self.reception_issue))
        else:
            object.__setattr__(self, "reception_issue", None)
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

    def next_action(self, now: datetime | None = None) -> NextAction:
        return next_action(
            self.status, overdue=self.is_overdue(now),
            reception_issue=self.reception_issue,
        )

    @property
    def responsible_branch(self) -> str | None:
        """Sucursal con la proxima accion. None si el circuito termino."""
        return sucursal_responsable(
            self.status, origin_branch=self.origin_branch,
            processing_branch=self.processing_branch,
        )

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
        if (target is TrackingStatus.RECEIVED_IN_ASUNCION
                and self.reception_issue is ReceptionIssue.NOT_ARRIVED):
            # Aparecio despues de todo: la discrepancia queda resuelta. En
            # cambio NO_ESTABA_EN_LISTA persiste, porque documenta que el
            # trabajo entro fuera del envio declarado.
            cambios["reception_issue"] = None
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


def reception_reconciliation(works: Sequence[TrackedWork]) -> dict[str, int]:
    """Declarados / Recibidos / No llego / Extra sobre un conjunto de trabajos.

    Unica cuenta de la recepcion. El servicio la aplica al lote y el tablero al
    conjunto visible, de modo que la linea que lee la operadora y la que audita
    el lote no puedan discrepar.

    `recibidos` cuenta solo entre los declarados: si sumara los extra, los
    numeros no cerrarian contra el total que Pilar envio.
    """
    extra = sum(1 for w in works if w.reception_issue is ReceptionIssue.NOT_IN_LIST)
    no_llego = sum(1 for w in works if w.reception_issue is ReceptionIssue.NOT_ARRIVED)
    recibidos = sum(
        1 for w in works
        if w.status is not TrackingStatus.SENT_FROM_PILAR and w.reception_issue is None
    )
    return {"declarados": len(works) - extra, "recibidos": recibidos,
            "no_llego": no_llego, "extra": extra}


def reconciliation_line(datos: Mapping[str, int]) -> str:
    """`Declarados 15 · Recibidos 14 · No llegó 1 · Extra 1`, en una sola linea.

    Los ceros no se ocultan: la operadora tiene que poder confirmar que la
    recepcion cerro sin discrepancias, y una linea que cambia de forma segun el
    caso obliga a releerla entera.
    """
    return " · ".join((
        f"Declarados {datos['declarados']}",
        f"Recibidos {datos['recibidos']}",
        f"No llegó {datos['no_llego']}",
        f"Extra {datos['extra']}",
    ))


def etiqueta_dia(valor: date, hoy: date | None = None) -> str:
    """`Hoy`, `Mañana` o `dd-mm`.

    La operadora razona en dias relativos, no en fechas: "Hoy 17:30" se lee de
    un golpe y "16-08 17:30" obliga a compararla con el calendario.
    """
    referencia = hoy or date.today()
    if valor == referencia:
        return "Hoy"
    if valor == referencia + timedelta(days=1):
        return "Mañana"
    return valor.strftime("%d-%m")


def overdue_alert(works: Sequence[TrackedWork], now: datetime | None = None) -> str:
    total = sum(1 for work in works if work.is_overdue(now))
    if not total:
        return ""
    sustantivo = "trabajo atrasado" if total == 1 else "trabajos atrasados"
    return f"{total} {sustantivo} — contactar laboratorios"
