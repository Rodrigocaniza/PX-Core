"""Trabajos operativos de la óptica: composturas y trabajos de taller.

Un trabajo operativo es lo que la óptica hace sobre los lentes de alguien:
poner un tornillo, cambiar una plaqueta, soldar un armazón. Tiene origen,
responsable, estado, causa y traza, y **no es inventario físico**: ni crea, ni
consume, ni ajusta stock en ninguno de sus estados. Ese es el invariante del
que cuelga todo el módulo, y por eso este archivo no importa nada del núcleo
comercial: no puede mover stock porque no conoce a quien lo mueve.

El estado operativo y el estado económico son dos ejes distintos. `status` dice
dónde está el trabajo; el cobro vive en la caja y el trabajo solo lo referencia.
Una compostura puede estar `LISTO` y sin cobrar, y una cobrada puede seguir sin
entregar.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import Enum
from typing import Mapping, Sequence

from .errors import InvalidCashDayError
from .models import new_id, parse_business_date, utc_now


class JobStatus(str, Enum):
    """Etapas del trabajo. El orden de declaración es el orden del flujo."""

    RECEIVED = "RECIBIDO"
    IN_WORKSHOP = "EN_TALLER"
    READY = "LISTO"
    DELIVERED = "ENTREGADO"
    VOIDED = "ANULADO"


ETIQUETA_ESTADO = {
    JobStatus.RECEIVED: "RECIBIDO",
    JobStatus.IN_WORKSHOP: "EN TALLER",
    JobStatus.READY: "LISTO",
    JobStatus.DELIVERED: "ENTREGADO",
    JobStatus.VOIDED: "ANULADO",
}


class JobEvent(str, Enum):
    CREATED = "CREADO"
    RESPONSIBLE_ASSIGNED = "RESPONSABLE_ASIGNADO"
    RESPONSIBLE_CHANGED = "RESPONSABLE_CAMBIADO"
    SENT_TO_WORKSHOP = "ENVIADO_A_TALLER"
    MARKED_READY = "MARCADO_LISTO"
    DELIVERED = "ENTREGADO"
    VOIDED = "ANULADO"
    REOPENED = "REABIERTO"
    DATA_CHANGED = "DATOS_MODIFICADOS"
    PAYMENT_LINKED = "COBRO_VINCULADO"
    COMMISSION_ACCRUED = "COMISION_DEVENGADA"
    COMMISSION_COMPENSATED = "COMISION_COMPENSADA"


#: Única fuente de verdad de las transiciones permitidas. Lo que no está acá no
#: pasa, y no pasa ruidosamente: `InvalidCashDayError`, nunca en silencio.
#:
#: `RECIBIDO -> LISTO` está permitido a propósito: un tornillo se pone en el
#: mostrador en dos minutos y no pasa por ningún taller. Obligar a un paso
#: intermedio ficticio sería pedirle a la operadora que mienta para poder
#: avanzar, y a los diez días nadie sabría cuáles pasaron de verdad por taller.
ALLOWED_TRANSITIONS: Mapping[JobStatus, tuple[JobStatus, ...]] = {
    JobStatus.RECEIVED: (JobStatus.IN_WORKSHOP, JobStatus.READY, JobStatus.VOIDED),
    JobStatus.IN_WORKSHOP: (JobStatus.READY, JobStatus.RECEIVED, JobStatus.VOIDED),
    JobStatus.READY: (JobStatus.DELIVERED, JobStatus.IN_WORKSHOP, JobStatus.VOIDED),
    # Entregado no es el final absoluto: el cliente vuelve al día siguiente
    # porque el trabajo vino mal. Pero volver atrás desde acá no es avanzar el
    # circuito, es reabrirlo, y por eso exige motivo.
    JobStatus.DELIVERED: (JobStatus.IN_WORKSHOP,),
    JobStatus.VOIDED: (),
}

#: Las transiciones que van para atrás. No se prohíben -la realidad las tiene-
#: pero no pueden pasar sin que alguien diga por qué.
TRANSICIONES_QUE_EXIGEN_MOTIVO: frozenset[tuple[JobStatus, JobStatus]] = frozenset({
    (JobStatus.IN_WORKSHOP, JobStatus.RECEIVED),
    (JobStatus.READY, JobStatus.IN_WORKSHOP),
    (JobStatus.DELIVERED, JobStatus.IN_WORKSHOP),
})

#: Estados desde los que reabrir es reabrir, y no simplemente retroceder. El
#: evento que se registra es `REABIERTO`, que es lo que después se busca.
ESTADOS_REABRIBLES: frozenset[JobStatus] = frozenset({
    JobStatus.READY, JobStatus.DELIVERED,
})

#: Un trabajo está pendiente mientras no se entregó ni se anuló.
ESTADOS_ABIERTOS: tuple[JobStatus, ...] = (
    JobStatus.RECEIVED, JobStatus.IN_WORKSHOP, JobStatus.READY,
)

#: Sucursales. Mismo vocabulario que `cash_register_branches` y `domain_events`:
#: no se inventa un catálogo paralelo.
SUCURSALES: tuple[str, ...] = ("ASUNCION", "PILAR")

#: El estado en el que se devenga la comisión.
#:
#: Es `LISTO` y no `ENTREGADO`, y la razón sale del flujo real: la comisión de
#: compostura remunera **hacer el trabajo**, no venderlo ni entregarlo. Cuando
#: el trabajo llega a `LISTO`, quien lo hizo ya lo hizo; que el cliente pase a
#: retirarlo mañana, la semana que viene o nunca es una circunstancia del
#: cliente, y hacerla condición del pago dejaría trabajo hecho sin remunerar por
#: un motivo ajeno a quien lo hizo.
#:
#: Lo que se paga es el trabajo, así que anular después de `LISTO` compensa
#: -el trabajo dejó de existir como hecho válido- pero entregar no vuelve a
#: devengar: ya se devengó.
ESTADO_DE_DEVENGO = JobStatus.READY


def normalizar_sucursal(value: str | None) -> str:
    sucursal = str(value or "").strip().upper()
    if sucursal not in SUCURSALES:
        raise InvalidCashDayError(
            f"Sucursal desconocida: {value!r}. Las sucursales son {', '.join(SUCURSALES)}.")
    return sucursal


def _texto(value: str | None) -> str:
    return str(value or "").strip()


def _estado(value: JobStatus | str) -> JobStatus:
    if isinstance(value, JobStatus):
        return value
    try:
        return JobStatus(str(value).strip().upper())
    except ValueError as error:
        raise InvalidCashDayError(f"Estado de trabajo desconocido: {value!r}.") from error


def puede_transicionar(desde: JobStatus, hasta: JobStatus) -> bool:
    return hasta in ALLOWED_TRANSITIONS[desde]


def exige_motivo(desde: JobStatus, hasta: JobStatus) -> bool:
    return (desde, hasta) in TRANSICIONES_QUE_EXIGEN_MOTIVO


def evento_de_transicion(desde: JobStatus, hasta: JobStatus) -> JobEvent:
    """Qué se registra cuando el trabajo pasa de un estado al otro.

    Volver atrás desde `LISTO` o `ENTREGADO` es `REABIERTO` y no
    `ENVIADO_A_TALLER`: la diferencia importa cuando alguien pregunta cuántos
    trabajos hubo que rehacer, que es una pregunta distinta de cuántos pasaron
    por taller.
    """
    if hasta is JobStatus.IN_WORKSHOP and desde in ESTADOS_REABRIBLES:
        return JobEvent.REOPENED
    return {
        JobStatus.IN_WORKSHOP: JobEvent.SENT_TO_WORKSHOP,
        JobStatus.READY: JobEvent.MARKED_READY,
        JobStatus.DELIVERED: JobEvent.DELIVERED,
        JobStatus.VOIDED: JobEvent.VOIDED,
        # Volver de taller a recibido es deshacer el envío, no crear nada.
        JobStatus.RECEIVED: JobEvent.REOPENED,
    }[hasta]


@dataclass(frozen=True)
class JobHistoryEntry:
    """Un hecho de la vida del trabajo. Append-only: nunca se reescribe."""

    event_type: JobEvent
    actor: str
    occurred_at: datetime
    id: str = field(default_factory=new_id)
    from_status: JobStatus | None = None
    to_status: JobStatus | None = None
    reason: str = ""
    detail: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", JobEvent(self.event_type))
        object.__setattr__(self, "actor", _texto(self.actor))
        if not self.actor:
            raise InvalidCashDayError("Todo hecho registrado tiene un actor.")
        if self.from_status is not None:
            object.__setattr__(self, "from_status", _estado(self.from_status))
        if self.to_status is not None:
            object.__setattr__(self, "to_status", _estado(self.to_status))
        object.__setattr__(self, "reason", _texto(self.reason))
        if self.event_type in (JobEvent.VOIDED, JobEvent.REOPENED) and not self.reason:
            raise InvalidCashDayError(
                "Anular o reabrir un trabajo exige decir por qué.")


@dataclass(frozen=True)
class ServiceJob:
    """El trabajo operativo.

    Inmutable: cada cambio devuelve un trabajo nuevo con un hecho más en su
    historia. Así no existe la mutación silenciosa que después nadie puede
    explicar.
    """

    reference: str
    branch: str
    customer_name: str
    job_type: str
    description: str
    received_by: str

    id: str = field(default_factory=new_id)
    customer_phone: str = ""
    observations: str = ""
    responsible: str = ""
    responsible_user_id: str | None = None
    delivered_by: str = ""
    status: JobStatus = JobStatus.RECEIVED
    received_at: datetime = field(default_factory=utc_now)
    promised_date: date | None = None
    workshop_return_at: datetime | None = None
    ready_at: datetime | None = None
    delivered_at: datetime | None = None
    voided_at: datetime | None = None
    charged_amount: int | None = None
    cash_entry_id: str | None = None
    order_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    history: tuple[JobHistoryEntry, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _estado(self.status))
        object.__setattr__(self, "branch", normalizar_sucursal(self.branch))
        for campo in ("reference", "customer_name", "description", "received_by",
                      "customer_phone", "observations", "responsible", "delivered_by",
                      "job_type"):
            object.__setattr__(self, campo, _texto(getattr(self, campo)))
        if not self.reference:
            raise InvalidCashDayError("El trabajo necesita un número de referencia.")
        if not self.customer_name:
            raise InvalidCashDayError("El trabajo necesita el nombre del cliente.")
        if not self.description:
            raise InvalidCashDayError("El trabajo necesita decir qué hay que hacer.")
        if not self.job_type:
            raise InvalidCashDayError("El trabajo necesita un tipo.")
        if not self.received_by:
            raise InvalidCashDayError("El trabajo necesita quién lo recibió.")
        if self.promised_date is not None:
            object.__setattr__(self, "promised_date", parse_business_date(self.promised_date))
        if self.charged_amount is not None:
            monto = int(self.charged_amount)
            if monto < 0:
                raise InvalidCashDayError("El importe cobrado no puede ser negativo.")
            object.__setattr__(self, "charged_amount", monto)

    # -- lecturas ----------------------------------------------------------

    @property
    def status_label(self) -> str:
        return ETIQUETA_ESTADO[self.status]

    @property
    def is_open(self) -> bool:
        return self.status in ESTADOS_ABIERTOS

    @property
    def is_charged(self) -> bool:
        """Si hay un cobro real detrás. Es independiente del estado operativo."""
        return bool(self.cash_entry_id)

    @property
    def next_sequence(self) -> int:
        return len(self.history) + 1

    def allowed_transitions(self) -> tuple[JobStatus, ...]:
        return ALLOWED_TRANSITIONS[self.status]

    # -- escrituras --------------------------------------------------------

    def _con_hecho(self, hecho: JobHistoryEntry, **cambios) -> "ServiceJob":
        return replace(self, history=self.history + (hecho,),
                       updated_at=hecho.occurred_at, **cambios)

    def registrar_creacion(self, *, actor: str, occurred_at: datetime | None = None) -> "ServiceJob":
        cuando = occurred_at or self.created_at
        hecho = JobHistoryEntry(
            event_type=JobEvent.CREATED, actor=actor, occurred_at=cuando,
            to_status=self.status,
            detail={"tipo": self.job_type, "sucursal": self.branch,
                    "cliente": self.customer_name},
        )
        trabajo = replace(self, history=self.history + (hecho,))
        if trabajo.responsible or trabajo.responsible_user_id:
            return trabajo._registrar_responsable(
                actor=actor, occurred_at=cuando, evento=JobEvent.RESPONSIBLE_ASSIGNED,
                nombre=trabajo.responsible, user_id=trabajo.responsible_user_id)
        return trabajo

    def _registrar_responsable(self, *, actor: str, occurred_at: datetime,
                               evento: JobEvent, nombre: str,
                               user_id: str | None) -> "ServiceJob":
        hecho = JobHistoryEntry(
            event_type=evento, actor=actor, occurred_at=occurred_at,
            detail={"responsable": nombre, "responsable_id": user_id or ""},
        )
        return replace(self, history=self.history + (hecho,),
                       responsible=nombre, responsible_user_id=user_id,
                       updated_at=occurred_at)

    def asignar_responsable(self, nombre: str, *, actor: str, user_id: str | None = None,
                            occurred_at: datetime | None = None) -> "ServiceJob":
        nombre = _texto(nombre)
        if not nombre:
            raise InvalidCashDayError("El responsable necesita un nombre.")
        if self.status is JobStatus.VOIDED:
            raise InvalidCashDayError("Un trabajo anulado no cambia de responsable.")
        evento = (JobEvent.RESPONSIBLE_CHANGED if (self.responsible or self.responsible_user_id)
                  else JobEvent.RESPONSIBLE_ASSIGNED)
        return self._registrar_responsable(
            actor=actor, occurred_at=occurred_at or utc_now(), evento=evento,
            nombre=nombre, user_id=user_id)

    def transicionar(self, destino: JobStatus | str, *, actor: str, reason: str = "",
                     delivered_by: str = "", occurred_at: datetime | None = None,
                     ) -> "ServiceJob":
        """Mueve el trabajo de estado, o falla diciendo por qué no puede."""
        destino = _estado(destino)
        cuando = occurred_at or utc_now()
        if destino is self.status:
            raise InvalidCashDayError(
                f"El trabajo ya está {ETIQUETA_ESTADO[destino]}.")
        if not puede_transicionar(self.status, destino):
            raise InvalidCashDayError(
                f"Un trabajo {ETIQUETA_ESTADO[self.status]} no puede pasar a "
                f"{ETIQUETA_ESTADO[destino]}.")
        motivo = _texto(reason)
        if (exige_motivo(self.status, destino) or destino is JobStatus.VOIDED) and not motivo:
            raise InvalidCashDayError(
                f"Pasar de {ETIQUETA_ESTADO[self.status]} a {ETIQUETA_ESTADO[destino]} "
                f"exige decir por qué.")

        cambios: dict[str, object] = {"status": destino}
        if destino is JobStatus.IN_WORKSHOP:
            cambios["workshop_return_at"] = None
        elif destino is JobStatus.READY:
            cambios["workshop_return_at"] = self.workshop_return_at or cuando
            cambios["ready_at"] = cuando
        elif destino is JobStatus.DELIVERED:
            entrego = _texto(delivered_by) or _texto(actor)
            if not entrego:
                raise InvalidCashDayError("Entregar exige saber quién entregó.")
            cambios["delivered_by"] = entrego
            cambios["delivered_at"] = cuando
        elif destino is JobStatus.VOIDED:
            cambios["voided_at"] = cuando

        hecho = JobHistoryEntry(
            event_type=evento_de_transicion(self.status, destino), actor=actor,
            occurred_at=cuando, from_status=self.status, to_status=destino,
            reason=motivo,
        )
        return self._con_hecho(hecho, **cambios)

    def vincular_cobro(self, cash_entry_id: str, *, actor: str, amount: int | None = None,
                       occurred_at: datetime | None = None) -> "ServiceJob":
        """Referencia el cobro que ya ocurrió en la caja.

        No crea el cobro y no lo puede crear: el dinero entra por venta, y esto
        solo deja dicho cuál venta pagó este trabajo. Vincular dos veces el
        mismo trabajo a cobros distintos duplicaría el importe en dos lugares,
        así que se rechaza.
        """
        referencia = _texto(cash_entry_id)
        if not referencia:
            raise InvalidCashDayError("El cobro necesita una referencia de caja.")
        if self.cash_entry_id and self.cash_entry_id != referencia:
            raise InvalidCashDayError(
                "El trabajo ya tiene un cobro vinculado. Corregirlo es una anulación "
                "de la venta, no un segundo cobro.")
        monto = self.charged_amount if amount is None else int(amount)
        if monto is not None and monto < 0:
            raise InvalidCashDayError("El importe cobrado no puede ser negativo.")
        cuando = occurred_at or utc_now()
        hecho = JobHistoryEntry(
            event_type=JobEvent.PAYMENT_LINKED, actor=actor, occurred_at=cuando,
            detail={"cash_entry_id": referencia, "importe": monto},
        )
        return self._con_hecho(hecho, cash_entry_id=referencia, charged_amount=monto)

    def actualizar_datos(self, *, actor: str, occurred_at: datetime | None = None,
                         **campos) -> "ServiceJob":
        """Corrige los datos del cliente o del trabajo dejando dicho qué cambió."""
        editables = {"customer_name", "customer_phone", "description", "observations",
                     "job_type", "promised_date"}
        desconocidos = set(campos) - editables
        if desconocidos:
            raise InvalidCashDayError(
                f"No se pueden editar estos campos: {', '.join(sorted(desconocidos))}.")
        if self.status is JobStatus.VOIDED:
            raise InvalidCashDayError("Un trabajo anulado no se edita.")
        cambios = {campo: valor for campo, valor in campos.items()
                   if valor is not None and getattr(self, campo) != valor}
        if not cambios:
            return self
        antes = {campo: str(getattr(self, campo)) for campo in cambios}
        cuando = occurred_at or utc_now()
        hecho = JobHistoryEntry(
            event_type=JobEvent.DATA_CHANGED, actor=actor, occurred_at=cuando,
            detail={"antes": antes,
                    "despues": {c: str(v) for c, v in cambios.items()}},
        )
        return self._con_hecho(hecho, **cambios)


def siguiente_referencia(existentes: Sequence[str], *, prefijo: str = "T") -> str:
    """El próximo número legible de trabajo.

    Correlativo y sin huecos que confundan al mostrador: se toma el mayor que
    ya existe y se le suma uno. Deriva de lo guardado y no de un contador
    aparte, que es lo que evita que dos cajas reinicien la numeración cada una
    por su lado después de una restauración.
    """
    mayor = 0
    for referencia in existentes:
        texto = str(referencia or "").strip().upper()
        if not texto.startswith(f"{prefijo}-"):
            continue
        sufijo = texto[len(prefijo) + 1:]
        if sufijo.isdigit():
            mayor = max(mayor, int(sufijo))
    return f"{prefijo}-{mayor + 1:05d}"
