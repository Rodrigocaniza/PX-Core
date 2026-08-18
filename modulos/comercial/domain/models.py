"""Modelos puros del núcleo comercial de la óptica.

Los importes son enteros en guaraníes, igual que en Caja. Este módulo fija el
vocabulario del que van a colgar Compras, Stock, Ventas y Trabajos: si algo se
nombra mal acá, después hay que migrar dos veces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


class StockMovementKind(str, Enum):
    """Movimientos válidos del ledger. Se define acá para que el slice del
    ledger no tenga que reabrir esta discusión.

    Una compra histórica **nunca** se modifica ni se borra para sacar stock: lo
    que corresponde es registrar la salida administrativa o el ajuste auditado.
    """

    INGRESO_COMPRA = "INGRESO_COMPRA"
    INGRESO_PRODUCCION = "INGRESO_PRODUCCION"
    VENTA = "VENTA"
    SALIDA_ADMINISTRATIVA = "SALIDA_ADMINISTRATIVA"
    AJUSTE_POSITIVO = "AJUSTE_POSITIVO"
    AJUSTE_NEGATIVO = "AJUSTE_NEGATIVO"
    TRANSFERENCIA = "TRANSFERENCIA"


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
    name: str
    kind: str = "PROVEEDOR"
    document: str = ""
    phone: str = ""
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
        for campo in ("document", "phone"):
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
