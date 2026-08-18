"""Modelos puros del núcleo comercial de la óptica.

Los importes son enteros en guaraníes, igual que en Caja. Este módulo fija el
vocabulario del que van a colgar Compras, Stock, Ventas y Trabajos: si algo se
nombra mal acá, después hay que migrar dos veces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


def new_id() -> str:
    return str(uuid4())


# Una venta sin cliente identificado no crea un cliente ficticio: normaliza a
# esta constante. Es vocabulario, no una fila en una tabla.
CONSUMIDOR_FINAL = "Consumidor final"


def nombre_de_cliente(valor: str | None) -> str:
    """Nombre a guardar en una venta, con el vacío resuelto de una sola forma."""
    limpio = (valor or "").strip()
    return limpio or CONSUMIDOR_FINAL


class ArticleNature(str, Enum):
    """Qué es el ítem. De acá se deriva si mueve stock, y sólo de acá.

    `PRODUCTO_STOCKEABLE`: armazón, líquido, estuche.
    `SERVICIO_NO_STOCKEABLE`: compostura, ajuste, consulta.
    `TRABAJO_BAJO_PEDIDO`: cristal recetado, insumo pedido para un trabajo.
    `PRODUCCION_INTERNA`: lo que la óptica arma y después vende.
    """

    PRODUCTO_STOCKEABLE = "PRODUCTO_STOCKEABLE"
    SERVICIO_NO_STOCKEABLE = "SERVICIO_NO_STOCKEABLE"
    TRABAJO_BAJO_PEDIDO = "TRABAJO_BAJO_PEDIDO"
    PRODUCCION_INTERNA = "PRODUCCION_INTERNA"

    @property
    def mueve_stock(self) -> bool:
        return self in _NATURALEZAS_QUE_MUEVEN_STOCK

    @property
    def label(self) -> str:
        return {
            ArticleNature.PRODUCTO_STOCKEABLE: "Producto stockeable",
            ArticleNature.SERVICIO_NO_STOCKEABLE: "Servicio no stockeable",
            ArticleNature.TRABAJO_BAJO_PEDIDO: "Trabajo bajo pedido",
            ArticleNature.PRODUCCION_INTERNA: "Producción interna",
        }[self]


_NATURALEZAS_QUE_MUEVEN_STOCK = frozenset({
    ArticleNature.PRODUCTO_STOCKEABLE,
    ArticleNature.PRODUCCION_INTERNA,
})


class CostStatus(str, Enum):
    """El costo de un trabajo de laboratorio no siempre existe cuando se vende.

    No se inventa un número: se declara que falta conciliar. `Compras` resuelve
    el estado cuando llega la factura real del laboratorio.
    """

    CONOCIDO = "CONOCIDO"
    PENDIENTE_DE_CONCILIACION = "PENDIENTE_DE_CONCILIACION"


class Destination(str, Enum):
    """Destinos de la operación.

    Es el mismo vocabulario que ya usan `cash_register_branches`,
    `tracked_works.origin_branch` y `orders.branch`. No hay tabla nueva: crear
    un catálogo de sucursales al lado del que ya funciona sería exactamente el
    sistema paralelo que se pidió evitar.
    """

    ASUNCION = "ASUNCION"
    PILAR = "PILAR"


class AdministrativeExitReason(str, Enum):
    """Por qué salió del stock algo que no se vendió.

    Espeja `administrative_exit_reasons`, sembrada en la migración 022. El
    movimiento que los consume es el slice del ledger; acá está el vocabulario.
    """

    ROTO = "ROTO"
    RAYADO = "RAYADO"
    PERDIDA = "PERDIDA"
    DETERIORO = "DETERIORO"
    USO_INTERNO = "USO_INTERNO"
    ERROR_INVENTARIO = "ERROR_INVENTARIO"
    OTRO = "OTRO"


class AdministrativeEntryReason(str, Enum):
    """Por qué entró al stock algo que no vino por una compra.

    Espeja `administrative_entry_reasons`, sembrada en la migración 023. Todos
    exigen observación: un ingreso sin factura y sin explicación sería stock
    aparecido de la nada.
    """

    STOCK_ENCONTRADO = "STOCK_ENCONTRADO"
    CORRECCION_INVENTARIO = "CORRECCION_INVENTARIO"
    FUERA_DE_CIRCUITO = "FUERA_DE_CIRCUITO"
    OTRO = "OTRO"


class StockMovementKind(str, Enum):
    """Movimientos válidos del ledger.

    Una compra histórica **nunca** se modifica ni se borra para sacar stock: lo
    que corresponde es registrar la salida administrativa o el ajuste auditado.

    El slice 1 dejó `TRANSFERENCIA` como un solo miembro. El ledger lo abre en
    dos patas porque un único valor no puede decir de qué lado del traslado
    está el destino, y el signo del movimiento se deriva justamente de eso.
    Nada consumía todavía el nombre viejo, así que se corrige acá y no queda
    una tercera forma de escribir lo mismo.
    """

    INGRESO_COMPRA = "INGRESO_COMPRA"
    INGRESO_PRODUCCION = "INGRESO_PRODUCCION"
    INGRESO_ADMINISTRATIVO = "INGRESO_ADMINISTRATIVO"
    AJUSTE_POSITIVO = "AJUSTE_POSITIVO"
    TRANSFERENCIA_ENTRADA = "TRANSFERENCIA_ENTRADA"

    VENTA = "VENTA"
    SALIDA_ADMINISTRATIVA = "SALIDA_ADMINISTRATIVA"
    DEVOLUCION_PROVEEDOR = "DEVOLUCION_PROVEEDOR"
    AJUSTE_NEGATIVO = "AJUSTE_NEGATIVO"
    TRANSFERENCIA_SALIDA = "TRANSFERENCIA_SALIDA"

    @property
    def signo(self) -> int:
        """+1 si entra, -1 si sale.

        Es derivado, igual que `tracks_stock`. Una columna de signo al lado del
        tipo permitiría una venta que suma.
        """
        return 1 if self in _MOVIMIENTOS_DE_ENTRADA else -1

    @property
    def es_entrada(self) -> bool:
        return self.signo == 1

    @property
    def exige_motivo(self) -> bool:
        """Lo que entra o sale sin una venta ni una compra detrás se explica."""
        return self in _MOVIMIENTOS_QUE_EXIGEN_MOTIVO


_MOVIMIENTOS_DE_ENTRADA = frozenset({
    StockMovementKind.INGRESO_COMPRA,
    StockMovementKind.INGRESO_PRODUCCION,
    StockMovementKind.INGRESO_ADMINISTRATIVO,
    StockMovementKind.AJUSTE_POSITIVO,
    StockMovementKind.TRANSFERENCIA_ENTRADA,
})

_MOVIMIENTOS_QUE_EXIGEN_MOTIVO = frozenset({
    StockMovementKind.INGRESO_ADMINISTRATIVO,
    StockMovementKind.SALIDA_ADMINISTRATIVA,
    StockMovementKind.AJUSTE_POSITIVO,
    StockMovementKind.AJUSTE_NEGATIVO,
})

# La excepción al bloqueo de stock negativo es administrativa. Una venta no
# puede pedirla: para eso existe el bloqueo.
_MOVIMIENTOS_QUE_ADMITEN_NEGATIVO = frozenset({
    StockMovementKind.SALIDA_ADMINISTRATIVA,
    StockMovementKind.AJUSTE_NEGATIVO,
})


def _texto(valor: object) -> str:
    return str(valor or "").strip()


@dataclass(frozen=True)
class Category:
    name: str
    active: bool = True
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        nombre = _texto(self.name)
        if not nombre:
            raise ValueError("la categoría necesita nombre")
        object.__setattr__(self, "name", nombre)


@dataclass(frozen=True)
class Brand:
    name: str
    active: bool = True
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        nombre = _texto(self.name)
        if not nombre:
            raise ValueError("la marca necesita nombre")
        object.__setattr__(self, "name", nombre)


@dataclass(frozen=True)
class Supplier:
    """Un proveedor.

    `document` es el RUC o CI cuando existe. Cuando hay identidad fiscal fiable
    el duplicado se bloquea en la base; cuando no la hay, no se inventa una.

    Los datos de contacto son los que la carga de una factura real pide y nada
    más. Esto no es un CRM.
    """

    name: str
    kind: str = "PROVEEDOR"
    document: str = ""
    phone: str = ""
    address: str = ""
    email: str = ""
    contact_name: str = ""
    laboratory_id: str | None = None
    active: bool = True
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        nombre = _texto(self.name)
        if not nombre:
            raise ValueError("el proveedor necesita nombre")
        object.__setattr__(self, "name", nombre)
        clase = _texto(self.kind).upper() or "PROVEEDOR"
        if clase not in {"PROVEEDOR", "LABORATORIO", "AMBOS"}:
            raise ValueError(f"clase de proveedor inválida: {self.kind!r}")
        object.__setattr__(self, "kind", clase)
        for campo in ("document", "phone", "address", "email", "contact_name"):
            object.__setattr__(self, campo, _texto(getattr(self, campo)))


@dataclass(frozen=True)
class Article:
    """Un ítem del catálogo.

    No recibe `tracks_stock`: pasárselo es un `TypeError`, y eso es deliberado.
    Si moviera stock fuera un dato editable, nada impediría un armazón que no
    descuenta y una compostura que sí.
    """

    sku: str
    name: str
    nature: ArticleNature | str
    category_id: str | None = None
    brand_id: str | None = None
    supplier_id: str | None = None
    unit: str = "UNIDAD"
    sale_price: int | None = None
    #: Donde esta fisicamente en el local. Sin esto, encontrar un armazon en
    #: una gondola de trescientos es cuestion de suerte.
    location: str = ""
    #: Cuando avisar que se esta por acabar. Opcional: la optica no lo tiene
    #: definido para todo, y ponerle uno por defecto seria inventarlo.
    min_stock: int | None = None
    #: El que le puso el proveedor, si le puso alguno. No reemplaza al SKU.
    barcode: str | None = None
    notes: str = ""
    active: bool = True
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        sku = _texto(self.sku).upper()
        if not sku:
            raise ValueError("el artículo necesita SKU")
        object.__setattr__(self, "sku", sku)

        nombre = _texto(self.name)
        if not nombre:
            raise ValueError("el artículo necesita nombre")
        object.__setattr__(self, "name", nombre)

        try:
            naturaleza = ArticleNature(self.nature)
        except ValueError as exc:
            raise ValueError(f"naturaleza de artículo inválida: {self.nature!r}") from exc
        object.__setattr__(self, "nature", naturaleza)

        object.__setattr__(self, "unit", _texto(self.unit).upper() or "UNIDAD")
        object.__setattr__(self, "notes", _texto(self.notes))

        precio = self.sale_price
        if precio is not None:
            if isinstance(precio, bool) or not isinstance(precio, int) or precio < 0:
                raise ValueError("sale_price debe ser un entero PYG no negativo")

        object.__setattr__(self, "location", _texto(self.location))
        object.__setattr__(self, "barcode", _texto(self.barcode) or None)

        minimo = self.min_stock
        if minimo is not None:
            if isinstance(minimo, bool) or not isinstance(minimo, int) or minimo < 0:
                raise ValueError("min_stock debe ser un entero no negativo")

    @property
    def tracks_stock(self) -> bool:
        """Derivado de la naturaleza. Única fuente de verdad."""
        return self.nature.mueve_stock


@dataclass(frozen=True)
class AdministrativeExitReasonRow:
    """Fila del catálogo sembrado, tal como vive en la base."""

    code: str
    label: str
    requires_note: bool = False
    position: int = 0
    active: bool = True


@dataclass(frozen=True)
class AdministrativeEntryReasonRow:
    """Fila del catálogo de motivos de ingreso, tal como vive en la base."""

    code: str
    label: str
    requires_note: bool = True
    position: int = 0
    active: bool = True


@dataclass(frozen=True)
class StockMovement:
    """Un hecho físico de inventario.

    La cantidad que se declara es siempre positiva: el signo lo pone el tipo.
    Es la misma decisión que `tracks_stock`, por el mismo motivo — si el signo
    fuera un dato aparte, nada impediría una venta que suma.

    Un movimiento de stock **no** tiene impacto monetario. Una salida
    administrativa no toca Caja; si además hubo un hecho económico, ese hecho
    se registra por su lado.
    """

    article_id: str
    destination: Destination | str
    kind: StockMovementKind | str
    quantity: int
    actor: str
    idempotency_key: str
    event_id: str | None = None
    occurred_at: datetime | None = None
    recorded_at: datetime | None = None
    reason_code: str | None = None
    note: str = ""
    supplier_id: str | None = None
    document_kind: str | None = None
    document_id: str | None = None
    document_line_id: str | None = None
    document_number: str | None = None
    compensates_id: str | None = None
    negative_override: bool = False
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not _texto(self.article_id):
            raise ValueError("el movimiento necesita artículo")

        try:
            destino = Destination(self.destination)
        except ValueError as exc:
            raise ValueError(f"destino inválido: {self.destination!r}") from exc
        object.__setattr__(self, "destination", destino)

        try:
            tipo = StockMovementKind(self.kind)
        except ValueError as exc:
            raise ValueError(f"tipo de movimiento inválido: {self.kind!r}") from exc
        object.__setattr__(self, "kind", tipo)

        cantidad = self.quantity
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
            raise ValueError(
                "la cantidad se declara positiva; el signo lo decide el tipo")

        actor = _texto(self.actor)
        if not actor:
            raise ValueError("el movimiento necesita saber quién lo hizo")
        object.__setattr__(self, "actor", actor)

        if not _texto(self.idempotency_key):
            raise ValueError("el movimiento necesita clave de idempotencia")
        object.__setattr__(self, "idempotency_key", _texto(self.idempotency_key))

        object.__setattr__(self, "note", _texto(self.note))
        motivo = _texto(self.reason_code).upper() or None
        object.__setattr__(self, "reason_code", motivo)
        object.__setattr__(self, "negative_override", bool(self.negative_override))

        if self.occurred_at is None:
            object.__setattr__(self, "occurred_at", datetime.now(timezone.utc))

    @property
    def signed_quantity(self) -> int:
        """Lo que este movimiento le suma al stock. El ledger suma esto."""
        return self.quantity * self.kind.signo

    @property
    def admite_negative_override(self) -> bool:
        return self.kind in _MOVIMIENTOS_QUE_ADMITEN_NEGATIVO
