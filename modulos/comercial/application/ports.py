"""Puertos del núcleo comercial; no dependen de SQLite ni de la UI."""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from ..domain.eventos import DomainEvent, EventEffect
from ..domain.models import (
    AdministrativeEntryReasonRow,
    AdministrativeExitReasonRow,
    Article,
    Brand,
    Category,
    Destination,
    StockMovement,
    Supplier,
)


@runtime_checkable
class CatalogRepository(Protocol):
    def save_category(self, category: Category) -> Category: ...

    def get_category(self, category_id: str) -> Category | None: ...

    def list_categories(self, *, only_active: bool = True) -> Sequence[Category]: ...

    def save_brand(self, brand: Brand) -> Brand: ...

    def get_brand(self, brand_id: str) -> Brand | None: ...

    def list_brands(self, *, only_active: bool = True) -> Sequence[Brand]: ...

    def save_supplier(self, supplier: Supplier) -> Supplier: ...

    def get_supplier(self, supplier_id: str) -> Supplier | None: ...

    def list_suppliers(self, *, only_active: bool = True) -> Sequence[Supplier]: ...

    def save_article(self, article: Article) -> Article: ...

    def get_article(self, article_id: str) -> Article | None: ...

    def get_article_by_sku(self, sku: str) -> Article | None: ...

    def list_articles(self, *, only_active: bool = True) -> Sequence[Article]: ...

    def list_administrative_exit_reasons(
        self, *, only_active: bool = True
    ) -> Sequence[AdministrativeExitReasonRow]: ...

    def list_administrative_entry_reasons(
        self, *, only_active: bool = True
    ) -> Sequence[AdministrativeEntryReasonRow]: ...


@runtime_checkable
class StockLedgerRepository(Protocol):
    """Escribe y lee el ledger. No decide: las reglas viven en el dominio y,
    las que tienen que valer para cualquier escritor, en la base.

    No hay `eliminar` ni `actualizar`, y no es un olvido: el ledger es
    append-only y una corrección es un movimiento compensatorio.
    """

    def registrar(
        self,
        movimiento: StockMovement,
        *,
        evento: DomainEvent | None = None,
        efecto: str = "STOCK_MOVEMENT",
    ) -> StockMovement: ...

    def obtener(self, movimiento_id: str) -> StockMovement | None: ...

    def por_clave(self, idempotency_key: str) -> StockMovement | None: ...

    def compensacion_de(self, movimiento_id: str) -> StockMovement | None: ...

    def movimientos(
        self,
        *,
        article_id: str | None = None,
        destination: Destination | str | None = None,
    ) -> Sequence[StockMovement]: ...

    def movimientos_de_documento(
        self, document_kind: str, document_id: str
    ) -> Sequence[StockMovement]: ...

    def stock(self, article_id: str, destination: Destination | str) -> int: ...

    def stock_por_destino(self, article_id: str) -> dict[Destination, int]: ...

    def evento(self, event_id: str) -> DomainEvent | None: ...

    def evento_por_clave(self, idempotency_key: str) -> DomainEvent | None: ...

    def eventos_pendientes(self) -> Sequence[DomainEvent]: ...

    def efectos_de(self, event_id: str) -> Sequence[EventEffect]: ...
