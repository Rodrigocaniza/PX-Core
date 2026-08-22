"""Controller testeable entre la ventana de BC Comunicaciones y sus servicios.

Toda la lógica de pantalla vive acá y se puede probar sin Tk: la ventana sólo
dibuja lo que este objeto devuelve.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..application.services import MessageLibraryService, MessagePreparationService, MessagePreview
from ..domain.errors import (
    BackupError,
    CategoryNotFoundError,
    CommunicationsError,
    DuplicateTemplateError,
    InvalidTemplateError,
    MissingVariablesError,
    RestoreError,
    TemplateInactiveError,
    TemplateNotFoundError,
)
from ..domain.models import (
    Category,
    PreparedMessage,
    Template,
    VariableSpec,
    as_value_mapping,
    has_unsaved_changes,
)

OPERATOR_SETTING = "operator"


@dataclass(frozen=True)
class TemplateForm:
    """Todo lo necesario para armar la pantalla de preparación."""

    template: Template
    specs: tuple[VariableSpec, ...]
    values: dict[str, str] = field(default_factory=dict)

    @property
    def category_slug(self) -> str:
        return self.template.category_slug


@dataclass(frozen=True)
class CategoryOption:
    slug: str
    name: str
    count: int


class CommunicationsUIController:
    def __init__(
        self,
        library: MessageLibraryService,
        preparation: MessagePreparationService,
        *,
        backup_service=None,
    ) -> None:
        self.library = library
        self.preparation = preparation
        self.backup_service = backup_service
        self.last_backup_path: Path | None = None
        self.last_warning: str | None = None

    # ------------------------------------------------------------------ arranque

    def start(self) -> int:
        """Deja la biblioteca lista para operar. Devuelve plantillas precargadas."""
        return self.library.ensure_seeded()

    @property
    def repository(self):
        return self.library.repository

    def operator(self) -> str:
        return self.repository.get_setting(OPERATOR_SETTING, "")

    def set_operator(self, name: str) -> None:
        self.repository.set_setting(OPERATOR_SETTING, str(name or "").strip())

    # ------------------------------------------------------------------ navegación

    def category_options(self, *, include_inactive: bool = False) -> list[CategoryOption]:
        counts = self.library.counts_by_category(include_inactive=include_inactive)
        options = [CategoryOption(slug="", name="Todas", count=sum(counts.values()))]
        for category in self.library.list_categories():
            options.append(
                CategoryOption(slug=category.slug, name=category.name, count=counts.get(category.slug, 0))
            )
        return options

    def search(
        self,
        query: str = "",
        *,
        category_slug: str | None = None,
        branch: str | None = None,
        only_favorites: bool = False,
        include_inactive: bool = False,
    ) -> Sequence[Template]:
        return self.library.search(
            query,
            category_slug=category_slug or None,
            branch=branch,
            only_favorites=only_favorites,
            include_inactive=include_inactive,
        )

    def empty_state_message(
        self,
        query: str,
        *,
        category_slug: str | None = None,
        only_favorites: bool = False,
    ) -> str:
        """Estados vacíos que explican qué hacer, no sólo que no hay nada."""
        if only_favorites:
            return (
                "Todavía no marcaste plantillas como favoritas.\n"
                "Abrí una plantilla y tocá la estrella ☆ para tenerla siempre a mano."
            )
        if str(query or "").strip():
            ambito = "esta categoría" if category_slug else "la biblioteca"
            return (
                f"No encontramos plantillas con «{query.strip()}» en {ambito}.\n"
                "Probá con otra palabra, mirá en «Todas» o creá una plantilla nueva con F2."
            )
        if category_slug:
            return (
                "Esta categoría todavía no tiene plantillas activas.\n"
                "Creá la primera con F2."
            )
        return "La biblioteca está vacía. Creá tu primera plantilla con F2."

    # ------------------------------------------------------------------ preparación

    def open_template(self, template_id: str, *, values: Mapping[str, Any] | None = None) -> TemplateForm:
        template = self.library.get(template_id)
        supplied = as_value_mapping(values or {})
        return TemplateForm(
            template=template,
            specs=tuple(template.variable_specs),
            values={name: supplied.get(name, "") for name in template.variables},
        )

    def preview(self, template: Template, values: Mapping[str, Any]) -> MessagePreview:
        return self.preparation.preview(template, values)

    def pending_in_text(self, template: Template, text: str) -> tuple[str, ...]:
        """Qué queda sin resolver en el texto que está a punto de copiarse."""
        return self.preparation.pending_in_text(template, text)

    def copy_message(
        self,
        template_id: str,
        values: Mapping[str, Any],
        *,
        final_text: str | None = None,
        operator: str | None = None,
    ) -> PreparedMessage:
        template = self.library.get(template_id)
        who = operator if operator is not None else self.operator()
        return self.preparation.prepare(template, values, operator=who, final_text=final_text)

    def recent(self, limit: int = 25) -> Sequence[PreparedMessage]:
        return self.preparation.recent(limit)

    def toggle_favorite(self, template_id: str) -> Template:
        return self.library.toggle_favorite(template_id)

    # ------------------------------------------------------------------ administración

    def validate_draft(self, draft: Mapping[str, Any]) -> tuple[str, ...]:
        return self.library.validate_draft(
            title=str(draft.get("title", "")),
            body=str(draft.get("body", "")),
            category_slug=str(draft.get("category_slug", "")),
        )

    def has_unsaved_changes(self, original: Template | None, draft: Mapping[str, Any]) -> bool:
        return has_unsaved_changes(original, draft)

    def save_template(self, draft: Mapping[str, Any], *, template_id: str | None = None) -> Template:
        problems = self.validate_draft(draft)
        if problems:
            raise InvalidTemplateError(" ".join(problems))
        payload = {
            "title": str(draft.get("title", "")),
            "body": str(draft.get("body", "")),
            "category_slug": str(draft.get("category_slug", "")),
            "keywords": str(draft.get("keywords", "")),
            "branch": str(draft.get("branch", "")).strip(),
        }
        if template_id:
            active = draft.get("active")
            if active is not None:
                payload["active"] = bool(active)
            return self.library.update_template(template_id, **payload)
        return self.library.create_template(**payload, active=bool(draft.get("active", True)))

    def set_active(self, template_id: str, active: bool) -> Template:
        return self.library.set_active(template_id, active)

    def draft_from(self, template: Template | None, default_category: str = "") -> dict[str, Any]:
        if template is None:
            return {"title": "", "body": "", "category_slug": default_category, "keywords": "", "branch": "", "active": True}
        return {
            "title": template.title,
            "body": template.body,
            "category_slug": template.category_slug,
            "keywords": template.keywords,
            "branch": template.branch,
            "active": template.active,
        }

    def branch_options(self) -> tuple[str, ...]:
        return self.library.list_branches()

    # ------------------------------------------------------------------ respaldo

    def create_backup(self, label: str = "manual") -> Path:
        if self.backup_service is None:
            raise BackupError("El servicio de respaldo no está configurado.")
        self.last_backup_path = self.backup_service.create_backup(label)
        return self.last_backup_path

    def list_backups(self) -> Sequence[Path]:
        return self.backup_service.list_backups() if self.backup_service is not None else ()

    def restore_backup(self, source: str | Path):
        if self.backup_service is None:
            raise RestoreError("El servicio de respaldo no está configurado.")
        result = self.backup_service.restore(source)
        self.last_backup_path = result.safety_backup
        return result


def friendly_error(error: Exception) -> tuple[str, str]:
    """Traduce cualquier fallo previsto a un título y un texto que el mostrador entienda."""
    if isinstance(error, MissingVariablesError):
        return "Faltan datos", str(error)
    if isinstance(error, DuplicateTemplateError):
        return "Nombre repetido", str(error)
    if isinstance(error, TemplateInactiveError):
        return "Plantilla desactivada", str(error)
    if isinstance(error, TemplateNotFoundError):
        return "Plantilla inexistente", str(error)
    if isinstance(error, CategoryNotFoundError):
        return "Categoría inexistente", str(error)
    if isinstance(error, InvalidTemplateError):
        return "Datos incompletos", str(error)
    if isinstance(error, RestoreError):
        return "No se pudo restaurar", str(error)
    if isinstance(error, BackupError):
        return "No se pudo respaldar", str(error)
    if isinstance(error, CommunicationsError):
        return "No se pudo completar", str(error)
    if isinstance(error, sqlite3.Error):
        return "No se pudo guardar", "La base local no pudo completar la operación. Tu texto sigue en pantalla."
    if isinstance(error, OSError):
        return "Problema con el archivo", "No se pudo leer o escribir el archivo indicado."
    return "No se pudo completar", "Ocurrió un error inesperado. Tu texto sigue en pantalla."
