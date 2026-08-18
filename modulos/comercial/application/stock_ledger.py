"""El ledger de inventario: la única forma de que el stock cambie.

El stock no es una cifra editable. Es `SUM(quantity)` sobre movimientos que
ocurrieron, cada uno con su origen, su actor, su fecha y su motivo. Corregir no
es reescribir: se registra un movimiento compensatorio y los dos quedan.

Un movimiento de stock **no** mueve Caja. Una salida administrativa por rotura
descuenta una unidad y no toca un guaraní; si además hubo un hecho económico,
ese hecho se registra por su lado. Mezclarlos haría que el inventario y la caja
se expliquen el uno con el otro, que es justo lo que no se quiere.
"""

from __future__ import annotations

import sqlite3

from ..domain.eventos import DomainEvent, EventEffect
from ..domain.models import (
    Article,
    ArticleNature,
    Destination,
    StockMovement,
    StockMovementKind,
)


class LedgerError(ValueError):
    """Base de los rechazos del ledger. Todos son `ValueError`: rechazar un
    movimiento inválido no es una falla del sistema, es el sistema andando."""


class ArticuloNoStockeable(LedgerError):
    """Un servicio o un trabajo bajo pedido no genera unidades de inventario."""


class MotivoRequerido(LedgerError):
    """Un movimiento extraordinario sin causa declarada es un agujero."""


class StockInsuficiente(LedgerError):
    """La salida dejaría el stock en negativo."""


# Mensajes con los que la base rechaza. Se mapean a las excepciones del dominio
# para que un rechazo del trigger y uno de la aplicación se vean igual desde
# afuera: la regla es una sola aunque esté defendida en dos lugares.
_RECHAZOS_DE_LA_BASE = (
    ("stock insuficiente", StockInsuficiente),
    ("no mueve stock", ArticuloNoStockeable),
    ("exige observacion", MotivoRequerido),
    ("motivo desconocido", MotivoRequerido),
)


class StockLedgerService:
    def __init__(self, repository, catalog) -> None:
        self._repositorio = repository
        self._catalogo = catalog

    # -- escritura ----------------------------------------------------------

    def registrar(
        self, movimiento: StockMovement, *, evento: DomainEvent | None = None
    ) -> StockMovement:
        """Registra un hecho físico de inventario.

        Si la clave de idempotencia ya se usó, devuelve el movimiento que ya
        existía. El mismo hecho no descuenta dos veces.
        """
        ya_registrado = self._repositorio.por_clave(movimiento.idempotency_key)
        if ya_registrado is not None:
            return ya_registrado

        articulo = self._articulo(movimiento.article_id)
        self._verificar_naturaleza(articulo, movimiento)
        self._verificar_motivo(movimiento)
        self._verificar_excepcion_de_negativo(movimiento)
        self._verificar_stock_suficiente(movimiento)

        try:
            return self._repositorio.registrar(movimiento, evento=evento)
        except sqlite3.IntegrityError as error:
            raise self._traducir(error) from error

    def compensar(
        self, movimiento_id: str, *, reason_code: str, note: str, actor: str
    ) -> StockMovement:
        """Corrige un movimiento sin borrarlo.

        El error y su corrección quedan los dos. Es la única forma de deshacer
        algo en el ledger, y por eso un mismo movimiento se compensa una vez:
        dos compensaciones del mismo error descontarían dos veces.
        """
        original = self._repositorio.obtener(movimiento_id)
        if original is None:
            raise LedgerError(f"no existe el movimiento {movimiento_id}")
        if self._repositorio.compensacion_de(movimiento_id) is not None:
            raise LedgerError(
                f"el movimiento {movimiento_id} ya fue compensado; una segunda "
                "compensación descontaría dos veces")

        inverso = (StockMovementKind.AJUSTE_NEGATIVO if original.kind.es_entrada
                   else StockMovementKind.AJUSTE_POSITIVO)
        return self.registrar(StockMovement(
            article_id=original.article_id,
            destination=original.destination,
            kind=inverso,
            quantity=original.quantity,
            actor=actor,
            idempotency_key=f"compensa:{movimiento_id}",
            reason_code=reason_code,
            note=note,
            supplier_id=original.supplier_id,
            document_kind=original.document_kind,
            document_id=original.document_id,
            document_line_id=original.document_line_id,
            document_number=original.document_number,
            compensates_id=original.id,
        ))

    # -- lectura ------------------------------------------------------------

    def stock(self, article_id: str, destination: Destination | str) -> int:
        return self._repositorio.stock(article_id, destination)

    def stock_por_destino(self, article_id: str) -> dict[Destination, int]:
        return self._repositorio.stock_por_destino(article_id)

    def movimientos(
        self,
        *,
        article_id: str | None = None,
        destination: Destination | str | None = None,
    ) -> list[StockMovement]:
        return self._repositorio.movimientos(
            article_id=article_id, destination=destination)

    def movimientos_de_documento(
        self, document_kind: str, document_id: str
    ) -> list[StockMovement]:
        return self._repositorio.movimientos_de_documento(document_kind, document_id)

    def obtener(self, movimiento_id: str) -> StockMovement | None:
        return self._repositorio.obtener(movimiento_id)

    def evento(self, event_id: str) -> DomainEvent | None:
        return self._repositorio.evento(event_id)

    def efectos_de(self, event_id: str) -> list[EventEffect]:
        return self._repositorio.efectos_de(event_id)

    # -- reglas -------------------------------------------------------------

    def _articulo(self, article_id: str) -> Article:
        articulo = self._catalogo.get_article(article_id)
        if articulo is None:
            raise LedgerError(f"no existe el artículo {article_id}")
        return articulo

    @staticmethod
    def _verificar_naturaleza(articulo: Article, movimiento: StockMovement) -> None:
        if not articulo.tracks_stock:
            raise ArticuloNoStockeable(
                f"«{articulo.name}» es {articulo.nature.label.lower()} y no genera "
                "unidades de inventario")
        if (movimiento.kind is StockMovementKind.INGRESO_PRODUCCION
                and articulo.nature is not ArticleNature.PRODUCCION_INTERNA):
            raise LedgerError(
                f"«{articulo.name}» no es de producción interna: entraría por compra")

    def _verificar_motivo(self, movimiento: StockMovement) -> None:
        if movimiento.kind.exige_motivo and not movimiento.reason_code:
            raise MotivoRequerido(
                f"{movimiento.kind.value} necesita motivo declarado")
        if not movimiento.reason_code:
            return
        motivo = self._motivo(movimiento)
        if motivo is None:
            raise MotivoRequerido(
                f"motivo desconocido para {movimiento.kind.value}: "
                f"{movimiento.reason_code}")
        if motivo.requires_note and not movimiento.note:
            raise MotivoRequerido(
                f"el motivo «{motivo.label}» exige observación")

    def _motivo(self, movimiento: StockMovement):
        """El catálogo de motivos se DERIVA del tipo de movimiento.

        Una columna que dijera cuál es podría contradecir al tipo, que es el
        mismo error que `tracks_stock` existe para impedir.
        """
        if movimiento.kind is StockMovementKind.INGRESO_ADMINISTRATIVO:
            candidatos = self._catalogo.list_administrative_entry_reasons()
        else:
            candidatos = self._catalogo.list_administrative_exit_reasons()
        for motivo in candidatos:
            if motivo.code == movimiento.reason_code:
                return motivo
        return None

    @staticmethod
    def _verificar_excepcion_de_negativo(movimiento: StockMovement) -> None:
        if not movimiento.negative_override:
            return
        if not movimiento.admite_negative_override:
            raise LedgerError(
                f"{movimiento.kind.value} no puede dejar stock negativo: la "
                "excepción es administrativa y auditada, no una forma de seguir "
                "vendiendo")
        if not movimiento.reason_code or not movimiento.note:
            raise MotivoRequerido(
                "dejar el stock en negativo exige motivo y observación")

    def _verificar_stock_suficiente(self, movimiento: StockMovement) -> None:
        if movimiento.signed_quantity >= 0 or movimiento.negative_override:
            return
        disponible = self._repositorio.stock(
            movimiento.article_id, movimiento.destination)
        if disponible + movimiento.signed_quantity < 0:
            raise StockInsuficiente(
                f"hay {disponible} en {movimiento.destination.value} y el "
                f"movimiento pide {movimiento.quantity}")

    @staticmethod
    def _traducir(error: sqlite3.IntegrityError) -> LedgerError:
        mensaje = str(error).lower()
        for fragmento, excepcion in _RECHAZOS_DE_LA_BASE:
            if fragmento in mensaje:
                return excepcion(str(error))
        return LedgerError(str(error))
