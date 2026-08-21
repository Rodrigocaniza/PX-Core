"""La factura del proveedor, tal como existe en el papel.

Una factura real se registra **una sola vez**, a nivel empresa. No hay una carga
por sucursal: eso sería la misma factura existiendo dos veces, con dos verdades
posibles. Lo que sí se reparte es la mercadería física, y ese reparto es un dato
de la línea, no otra factura.

Los importes son enteros en guaraníes, igual que en Caja y en el resto del
núcleo comercial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from .models import Destination, new_id


def _texto(valor: object) -> str:
    return str(valor or "").strip()


def _entero_no_negativo(valor: object, etiqueta: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ValueError(f"{etiqueta} debe ser un entero PYG no negativo")
    return valor


class PurchaseCondition(str, Enum):
    """Cómo se pactó la factura. De acá sale si hay vencimiento."""

    CONTADO = "CONTADO"
    CREDITO = "CREDITO"


class PurchaseStatus(str, Enum):
    """Dónde está la factura.

    Sólo dos. No hay `ANULADA`: las notas de crédito y las devoluciones exceden
    este slice, y media anulación improvisada sería peor que ninguna. Lo que se
    hace mientras tanto es impedir la mutación destructiva.
    """

    BORRADOR = "BORRADOR"
    CONFIRMADA = "CONFIRMADA"


@dataclass(frozen=True)
class Distribution:
    """Cuántas unidades de una línea van a una sucursal."""

    destination: Destination | str
    quantity: int

    def __post_init__(self) -> None:
        try:
            destino = Destination(self.destination)
        except ValueError as exc:
            raise ValueError(f"destino inválido: {self.destination!r}") from exc
        object.__setattr__(self, "destination", destino)

        if (isinstance(self.quantity, bool) or not isinstance(self.quantity, int)
                or self.quantity <= 0):
            raise ValueError("la cantidad distribuida tiene que ser positiva")


@dataclass(frozen=True)
class PurchaseLine:
    """Una línea de la factura.

    No lleva una bandera propia que diga si mueve stock: eso se deriva de la
    naturaleza del artículo, igual que en el slice 1. Una bandera de línea
    permitiría armazones que no ingresan y composturas que sí.

    Tampoco lleva total: es cantidad por costo unitario.
    """

    article_id: str
    line_number: int
    quantity: int
    unit_cost: int
    description: str = ""
    notes: str = ""
    distributions: tuple[Distribution, ...] = ()
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not _texto(self.article_id):
            raise ValueError("la línea necesita artículo del catálogo")

        if (isinstance(self.line_number, bool)
                or not isinstance(self.line_number, int) or self.line_number <= 0):
            raise ValueError("el número de línea tiene que ser positivo")

        if (isinstance(self.quantity, bool) or not isinstance(self.quantity, int)
                or self.quantity <= 0):
            raise ValueError("la cantidad comprada tiene que ser positiva")

        _entero_no_negativo(self.unit_cost, "el costo unitario")

        object.__setattr__(self, "description", _texto(self.description))
        object.__setattr__(self, "notes", _texto(self.notes))
        object.__setattr__(self, "distributions", tuple(self.distributions))

        destinos = [d.destination for d in self.distributions]
        if len(destinos) != len(set(destinos)):
            raise ValueError(
                "un destino no puede aparecer dos veces en la misma línea: "
                "son dos cantidades para el mismo lugar")

    @property
    def line_total(self) -> int:
        return self.quantity * self.unit_cost

    @property
    def distributed_quantity(self) -> int:
        return sum(d.quantity for d in self.distributions)

    def cantidad_para(self, destino: Destination) -> int:
        for distribucion in self.distributions:
            if distribucion.destination is destino:
                return distribucion.quantity
        return 0


@dataclass(frozen=True)
class Purchase:
    """La factura de compra.

    `due_date` **no se recibe**: se deriva de la fecha del documento y el plazo.
    Pasarlo es un `TypeError`, deliberadamente, por el mismo motivo por el que
    `tracks_stock` tampoco se recibe — un vencimiento cargado a mano podría
    contradecir al plazo que dice tener.
    """

    supplier_id: str
    document_date: date
    document_number: str
    condition: PurchaseCondition | str
    document_total: int
    created_by: str
    lines: tuple[PurchaseLine, ...] = ()
    stamped_number: str = ""
    receipt_reference: str = ""
    credit_days: int | None = None
    notes: str = ""
    status: PurchaseStatus | str = PurchaseStatus.BORRADOR
    event_id: str | None = None
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not _texto(self.supplier_id):
            raise ValueError("la compra necesita proveedor")

        numero = _texto(self.document_number)
        if not numero:
            raise ValueError("la compra necesita número de documento")
        object.__setattr__(self, "document_number", numero)

        if not isinstance(self.document_date, date):
            raise ValueError("la fecha del documento tiene que ser una fecha")

        try:
            condicion = PurchaseCondition(self.condition)
        except ValueError as exc:
            raise ValueError(f"condición inválida: {self.condition!r}") from exc
        object.__setattr__(self, "condition", condicion)

        object.__setattr__(self, "status", PurchaseStatus(self.status))
        _entero_no_negativo(self.document_total, "el total del documento")

        creador = _texto(self.created_by)
        if not creador:
            raise ValueError("la compra necesita saber quién la cargó")
        object.__setattr__(self, "created_by", creador)

        for campo in ("stamped_number", "receipt_reference", "notes"):
            object.__setattr__(self, campo, _texto(getattr(self, campo)))

        if condicion is PurchaseCondition.CREDITO:
            plazo = self.credit_days
            if (plazo is None or isinstance(plazo, bool)
                    or not isinstance(plazo, int) or plazo < 0):
                raise ValueError("una compra a crédito necesita plazo en días")
        elif self.credit_days is not None:
            raise ValueError(
                "una compra al contado no tiene plazo: si lo tiene, es a crédito")

        object.__setattr__(self, "lines", tuple(self.lines))
        numeros = [linea.line_number for linea in self.lines]
        if len(numeros) != len(set(numeros)):
            raise ValueError("dos líneas no pueden tener el mismo número")

        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc))

    @property
    def due_date(self) -> date | None:
        """Derivado. Única fuente de verdad del vencimiento."""
        if self.condition is not PurchaseCondition.CREDITO:
            return None
        return self.document_date + timedelta(days=self.credit_days)

    @property
    def lines_total(self) -> int:
        """Lo que suman las líneas. Contrasta con lo que dice el papel."""
        return sum(linea.line_total for linea in self.lines)

    @property
    def confirmada(self) -> bool:
        return self.status is PurchaseStatus.CONFIRMADA


# Tipo del hecho que emite la confirmación. Se nombra una sola vez para que no
# convivan "PURCHASE_CONFIRMED" y "COMPRA_CONFIRMADA".
EVENTO_COMPRA_CONFIRMADA = "PURCHASE_CONFIRMED"

# De dónde viene el hecho. Mismo criterio.
ORIGEN_COMPRAS = "COMPRAS"

# Cómo se nombra la compra como documento de origen de un movimiento de stock.
DOCUMENTO_COMPRA = "COMPRA"
