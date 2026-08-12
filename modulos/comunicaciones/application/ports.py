"""Puertos de aplicación: no dependen de SQLite, de Tk ni del sistema operativo.

Los puertos marcados como *futuros* no tienen implementación en el MVP a
propósito. Existen para que las integraciones previstas (BC Caja / BC Gestión,
BC Consultorio, BC Inventario, catálogo web, envío directo por WhatsApp) se
enchufen sin rediseñar el módulo.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from ..domain.models import Category, PreparedMessage, Template


class TemplateRepository(Protocol):
    def save_template(self, template: Template) -> None: ...

    def get_template(self, template_id: str) -> Template | None: ...

    def list_templates(self, *, include_inactive: bool = True) -> Sequence[Template]: ...

    def search_templates(
        self,
        *,
        query: str = "",
        category_slug: str | None = None,
        only_favorites: bool = False,
        include_inactive: bool = False,
    ) -> Sequence[Template]: ...

    def save_category(self, category: Category) -> None: ...

    def list_categories(self, *, include_inactive: bool = False) -> Sequence[Category]: ...

    def get_category(self, slug: str) -> Category | None: ...


class PreparedMessageRepository(Protocol):
    def save_prepared_message(self, message: PreparedMessage) -> None: ...

    def list_prepared_messages(self, *, limit: int = 25) -> Sequence[PreparedMessage]: ...


class OutboxRepository(Protocol):
    """Cola local de eventos. Base de la telemetría y del envío directo futuro."""

    def append_outbox_event(self, event_type: str, payload: Mapping[str, Any]) -> str: ...

    def list_pending_outbox_events(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]: ...


class Clipboard(Protocol):
    def copy(self, text: str) -> None: ...


class MessageProvider(Protocol):
    """FUTURO — proveedor de envío intercambiable (WhatsApp Business, SMS, …).

    Ningún componente del MVP lo implementa ni lo invoca: el operador copia y
    pega. Cuando exista, `MessagePreparationService.prepare()` ya deja el
    `PreparedMessage` en estado `PENDIENTE` y un evento en el outbox listos para
    que un despachador los consuma.
    """

    def send(self, message: PreparedMessage, destination: str) -> str: ...


class ContactDirectory(Protocol):
    """FUTURO — origen de clientes/pedidos (BC Gestión, BC Consultorio, BC Inventario).

    Alimentará el autocompletado de variables y poblará
    `PreparedMessage.subject_kind` / `subject_reference`, columnas que ya existen
    en el esquema.
    """

    def suggest_values(self, reference: str) -> Mapping[str, str]: ...
