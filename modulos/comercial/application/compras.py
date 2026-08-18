"""Compras: registrar la factura una vez y derivar sus consecuencias.

Confirmar una compra es un solo hecho con varias consecuencias, no varias
operaciones que casualmente ocurren juntas. Por eso todo pasa en una sola
transacción: la factura queda confirmada, se emite un `PURCHASE_CONFIRMED`, y
nacen exactamente los `INGRESO_COMPRA` que las líneas stockeables y su reparto
determinan. O no pasa nada de eso.

Dinero y stock siguen siendo dimensiones separadas. Registrar una factura no
mueve Caja: una compra a crédito es una obligación, no una salida de dinero de
hoy, y Cuentas por Pagar excede este slice y no se improvisa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from ..domain.compras import (
    DOCUMENTO_COMPRA,
    EVENTO_COMPRA_CONFIRMADA,
    ORIGEN_COMPRAS,
    Purchase,
    PurchaseLine,
    PurchaseStatus,
)
from ..domain.eventos import DomainEvent, EventProcessingState
from ..domain.models import (
    Article,
    Destination,
    StockMovement,
    StockMovementKind,
    Supplier,
)


class ComprasError(ValueError):
    """Base de los rechazos de Compras. Todos son `ValueError`: rechazar una
    factura mal cargada no es una falla del sistema, es el sistema andando."""


class DistribucionInvalida(ComprasError):
    """El reparto físico no puede ser el que se pidió."""


class TotalNoCuadra(ComprasError):
    """Lo que dice el papel y lo que suman las líneas no coinciden."""


class CompraNoEditable(ComprasError):
    """Una factura confirmada es historia; no se reescribe."""


@dataclass(frozen=True)
class ResultadoDeConfirmacion:
    """Lo que dejó una confirmación: el hecho y sus efectos."""

    purchase: Purchase
    evento: DomainEvent
    movimientos: tuple[StockMovement, ...]
    ya_estaba_confirmada: bool = False


@dataclass(frozen=True)
class OrigenDeStock:
    """De dónde salió una unidad que está en el depósito.

    Es la respuesta mecánica a «qué factura, qué proveedor, qué línea, qué
    destino, qué evento, cuándo y quién confirmó».
    """

    movement_id: str
    article_id: str
    destination: Destination
    quantity: int
    purchase_id: str
    document_number: str
    document_date: str
    stamped_number: str
    condition: str
    due_date: str | None
    confirmed_by: str
    confirmed_at: str
    purchase_line_id: str
    line_number: int
    unit_cost: int
    supplier_id: str
    supplier_name: str
    supplier_document: str
    event_id: str
    event_type: str
    event_at: str


class ComprasService:
    def __init__(self, repository, catalog, ledger) -> None:
        self._repositorio = repository
        self._catalogo = catalog
        self._ledger = ledger

    # -- proveedores --------------------------------------------------------

    def guardar_proveedor(self, proveedor: Supplier) -> Supplier:
        """Alta o edición. No hay baja: un proveedor se desactiva.

        Borrarlo dejaría facturas apuntando a nadie, y esas facturas explican
        stock que existe.
        """
        return self._catalogo.save_supplier(proveedor)

    def obtener_proveedor(self, supplier_id: str) -> Supplier | None:
        return self._catalogo.get_supplier(supplier_id)

    def listar_proveedores(self, *, only_active: bool = True) -> Sequence[Supplier]:
        return self._catalogo.list_suppliers(only_active=only_active)

    # -- compras ------------------------------------------------------------

    def guardar_borrador(self, compra: Purchase) -> Purchase:
        """Carga la factura como borrador, todavía sin consecuencias.

        Lo que no se puede es volver a cargar una que ya se confirmó: eso
        cambiaría el pasado y dejaría stock existente con un origen distinto
        del que tuvo.
        """
        ya_cargada = self._repositorio.por_documento(
            compra.supplier_id, compra.document_number)
        if ya_cargada is not None and ya_cargada.confirmada:
            raise CompraNoEditable(
                f"la factura {compra.document_number} de este proveedor ya está "
                "confirmada: corregirla es un hecho nuevo, no una edición")

        for linea in compra.lines:
            self._verificar_linea(linea)
        return self._repositorio.guardar_borrador(compra)

    def obtener(self, purchase_id: str) -> Purchase | None:
        return self._repositorio.obtener(purchase_id)

    def listar(self, *, supplier_id: str | None = None) -> Sequence[Purchase]:
        return self._repositorio.listar(supplier_id=supplier_id)

    def confirmar(self, purchase_id: str, *, actor: str) -> ResultadoDeConfirmacion:
        """Confirma la factura y deriva su stock, todo o nada.

        Reintentar no duplica: si ya estaba confirmada devuelve el mismo hecho y
        los mismos movimientos, sin escribir de nuevo.
        """
        compra = self._repositorio.obtener(purchase_id)
        if compra is None:
            raise ComprasError(f"no existe la compra {purchase_id}")

        if compra.confirmada:
            return self._resultado_ya_confirmado(compra)

        self._verificar_confirmable(compra)
        momento = datetime.now(timezone.utc).replace(microsecond=0)
        evento = DomainEvent(
            event_type=EVENTO_COMPRA_CONFIRMADA,
            source=ORIGEN_COMPRAS,
            entity_type="PURCHASE",
            entity_id=compra.id,
            actor=actor,
            occurred_at=momento,
            idempotency_key=f"{DOCUMENTO_COMPRA}:{compra.id}",
            payload={
                "document_number": compra.document_number,
                "supplier_id": compra.supplier_id,
                "document_total": compra.document_total,
                "condition": compra.condition.value,
            },
            processing_state=EventProcessingState.PENDIENTE,
        )

        movimientos: list[StockMovement] = []
        with self._repositorio.escritura() as connection:
            # El hecho primero. Una factura de puros servicios se confirma
            # igual y su PURCHASE_CONFIRMED tiene que quedar registrado aunque
            # no arrastre un solo movimiento de stock.
            self._ledger.asegurar_evento_en(connection, evento)
            for linea in compra.lines:
                for distribucion in linea.distributions:
                    movimientos.append(self._ledger.registrar_en(
                        connection,
                        self._movimiento(compra, linea, distribucion.destination,
                                         distribucion.quantity, actor, momento),
                        evento=evento))
            self._ledger.marcar_evento_procesado_en(
                connection, evento.event_id, momento)
            self._repositorio.marcar_confirmada_en(
                connection, compra.id, actor=actor, event_id=evento.event_id,
                momento=momento)

        return ResultadoDeConfirmacion(
            purchase=self._repositorio.obtener(compra.id),
            evento=self._ledger.evento(evento.event_id),
            movimientos=tuple(movimientos),
        )

    # -- trazabilidad -------------------------------------------------------

    def trazabilidad(self, movement_id: str) -> OrigenDeStock | None:
        fila = self._repositorio.origen_de_movimiento(movement_id)
        if fila is None:
            return None
        return OrigenDeStock(
            movement_id=fila["movement_id"],
            article_id=fila["article_id"],
            destination=Destination(fila["destination"]),
            quantity=abs(int(fila["quantity"])),
            purchase_id=fila["purchase_id"],
            document_number=fila["document_number"],
            document_date=fila["document_date"],
            stamped_number=fila["stamped_number"],
            condition=fila["condition"],
            due_date=fila["due_date"],
            confirmed_by=fila["confirmed_by"],
            confirmed_at=fila["confirmed_at"],
            purchase_line_id=fila["purchase_line_id"],
            line_number=fila["line_number"],
            unit_cost=fila["unit_cost"],
            supplier_id=fila["supplier_id"],
            supplier_name=fila["supplier_name"],
            supplier_document=fila["supplier_document"],
            event_id=fila["event_id"],
            event_type=fila["event_type"],
            event_at=fila["event_at"],
        )

    # -- reglas -------------------------------------------------------------

    def _articulo(self, article_id: str) -> Article:
        articulo = self._catalogo.get_article(article_id)
        if articulo is None:
            raise ComprasError(f"no existe el artículo {article_id}")
        return articulo

    def _verificar_linea(self, linea: PurchaseLine) -> None:
        """Lo que se puede saber al cargar, se rechaza al cargar."""
        articulo = self._articulo(linea.article_id)
        if not articulo.tracks_stock:
            if linea.distributions:
                raise DistribucionInvalida(
                    f"«{articulo.name}» es {articulo.nature.label.lower()} y no "
                    "genera unidades de inventario: no se reparte entre sucursales")
            return
        if linea.distributed_quantity > linea.quantity:
            raise DistribucionInvalida(
                f"la línea {linea.line_number} reparte "
                f"{linea.distributed_quantity} de {linea.quantity} compradas")

    def _verificar_confirmable(self, compra: Purchase) -> None:
        """Lo que sólo se puede saber al confirmar, se rechaza al confirmar.

        Un borrador puede estar incompleto: para eso es un borrador. Lo que no
        puede es generar stock estando incompleto.
        """
        if compra.document_total != compra.lines_total:
            raise TotalNoCuadra(
                f"la factura dice {compra.document_total:,} y las líneas suman "
                f"{compra.lines_total:,}. No se ajusta sola: hay que mirar el papel")

        for linea in compra.lines:
            articulo = self._articulo(linea.article_id)
            if not articulo.tracks_stock:
                continue
            if linea.distributed_quantity != linea.quantity:
                raise DistribucionInvalida(
                    f"la línea {linea.line_number} compró {linea.quantity} y "
                    f"reparte {linea.distributed_quantity}: la mercadería tiene "
                    "que estar en algún lado, y no se inventa cuál")

    @staticmethod
    def _movimiento(
        compra: Purchase,
        linea: PurchaseLine,
        destino: Destination,
        cantidad: int,
        actor: str,
        momento: datetime,
    ) -> StockMovement:
        """El ingreso que esta línea provoca en esta sucursal.

        La clave de idempotencia es el camino completo hasta acá, así que
        reconfirmar la misma factura vuelve a apuntar al mismo movimiento en vez
        de crear otro.
        """
        return StockMovement(
            article_id=linea.article_id,
            destination=destino,
            kind=StockMovementKind.INGRESO_COMPRA,
            quantity=cantidad,
            actor=actor,
            occurred_at=momento,
            idempotency_key=(f"{DOCUMENTO_COMPRA}:{compra.id}:"
                             f"{linea.id}:{destino.value}"),
            supplier_id=compra.supplier_id,
            document_kind=DOCUMENTO_COMPRA,
            document_id=compra.id,
            document_line_id=linea.id,
            document_number=compra.document_number,
            note=linea.description,
        )

    def _resultado_ya_confirmado(self, compra: Purchase) -> ResultadoDeConfirmacion:
        """Reintento: se devuelve lo que ya pasó, sin volver a escribir nada."""
        movimientos = self._ledger.movimientos_de_documento(
            DOCUMENTO_COMPRA, compra.id)
        return ResultadoDeConfirmacion(
            purchase=compra,
            evento=self._ledger.evento(compra.event_id),
            movimientos=tuple(movimientos),
            ya_estaba_confirmada=True,
        )
