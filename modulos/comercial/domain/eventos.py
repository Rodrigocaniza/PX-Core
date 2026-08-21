"""BC Event Spine V1 — la representación durable de los hechos del negocio.

No es un event bus. No hace falta uno todavía y montarlo ahora sería inventar
infraestructura antes que necesidad. Lo que sí hace falta, y no se puede
agregar después sin migrar dos veces, es que un hecho relevante tenga
identidad, origen, actor, momento, payload mínimo, efectos derivados y una
clave que impida que reprocesarlo lo aplique dos veces.

El ledger de inventario es el primer consumidor. Los que vienen después
—`PURCHASE_CONFIRMED` generando entradas de stock, `SALE_COMPLETED` generando
movimiento de caja, salida de stock, trabajo y bandeja de FactuFácil— cuelgan
de la misma tabla sin cambiarle la forma.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from .models import Destination, new_id


class EventProcessingState(str, Enum):
    """En qué quedó el hecho.

    `NO_APLICA` no es un fracaso: es un hecho que se registró y que, para este
    módulo, no tenía consecuencias. Distinguirlo de `PENDIENTE` es lo que
    permite mirar la cola de pendientes y que signifique algo.
    """

    PENDIENTE = "PENDIENTE"
    PROCESADO = "PROCESADO"
    FALLIDO = "FALLIDO"
    NO_APLICA = "NO_APLICA"


def _texto(valor: object) -> str:
    return str(valor or "").strip()


@dataclass(frozen=True)
class DomainEvent:
    """Un hecho que ocurrió, tal como se registra.

    `idempotency_key` es la parte que hace que esto sirva: dos veces el mismo
    hecho es el mismo hecho, no dos.
    """

    event_type: str
    source: str
    entity_type: str
    actor: str
    idempotency_key: str
    entity_id: str | None = None
    destination: Destination | str | None = None
    occurred_at: datetime | None = None
    recorded_at: datetime | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    processing_state: EventProcessingState | str = EventProcessingState.PENDIENTE
    processed_at: datetime | None = None
    failure_reason: str = ""
    event_id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        for campo in ("event_type", "source", "entity_type", "actor", "idempotency_key"):
            valor = _texto(getattr(self, campo))
            if not valor:
                raise ValueError(f"el hecho necesita {campo}")
            object.__setattr__(self, campo, valor)

        if self.destination is not None:
            try:
                object.__setattr__(self, "destination", Destination(self.destination))
            except ValueError as exc:
                raise ValueError(f"destino inválido: {self.destination!r}") from exc

        object.__setattr__(
            self, "processing_state", EventProcessingState(self.processing_state))

        if self.occurred_at is None:
            object.__setattr__(self, "occurred_at", datetime.now(timezone.utc))

        object.__setattr__(self, "failure_reason", _texto(self.failure_reason))

    @property
    def payload_json(self) -> str:
        """El payload tal como se guarda. Mínimo: lo que hace falta para
        entender el hecho, no una copia del sistema entero."""
        return json.dumps(dict(self.payload), ensure_ascii=False, sort_keys=True)

    def procesado(self, *, momento: datetime | None = None) -> "DomainEvent":
        return self.con_estado(EventProcessingState.PROCESADO, momento=momento)

    def fallido(self, motivo: str, *, momento: datetime | None = None) -> "DomainEvent":
        return self.con_estado(
            EventProcessingState.FALLIDO, momento=momento, motivo=motivo)

    def con_estado(
        self,
        estado: EventProcessingState,
        *,
        momento: datetime | None = None,
        motivo: str = "",
    ) -> "DomainEvent":
        """Avanzar el estado es lo único que un hecho registrado admite.

        Todo lo demás —tipo, origen, actor, momento, payload— es inmutable, y
        la base lo hace cumplir con un trigger, no sólo esta clase.
        """
        return DomainEvent(
            event_type=self.event_type,
            source=self.source,
            entity_type=self.entity_type,
            actor=self.actor,
            idempotency_key=self.idempotency_key,
            entity_id=self.entity_id,
            destination=self.destination,
            occurred_at=self.occurred_at,
            recorded_at=self.recorded_at,
            payload=self.payload,
            processing_state=estado,
            processed_at=momento or datetime.now(timezone.utc),
            failure_reason=motivo or self.failure_reason,
            event_id=self.event_id,
        )


@dataclass(frozen=True)
class EventEffect:
    """Qué produjo un hecho.

    Sin esto, "efectos derivados" sería una promesa. Con esto se puede ir del
    evento a sus movimientos y del movimiento al evento que lo causó.
    """

    event_id: str
    effect_kind: str
    effect_table: str
    effect_id: str
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        for campo in ("event_id", "effect_kind", "effect_table", "effect_id"):
            valor = _texto(getattr(self, campo))
            if not valor:
                raise ValueError(f"el efecto necesita {campo}")
            object.__setattr__(self, campo, valor)


# Tipos de efecto que el sistema sabe producir hoy. La lista crece con cada
# slice; que sea explícita evita que "STOCK_MOVEMENT" y "MOVIMIENTO_STOCK"
# terminen conviviendo.
EFECTO_MOVIMIENTO_DE_STOCK = "STOCK_MOVEMENT"
