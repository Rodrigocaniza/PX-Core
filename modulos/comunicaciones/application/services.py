"""Casos de uso de BC Comunicaciones: biblioteca y preparación de mensajes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from ..domain.errors import (
    CategoryNotFoundError,
    InvalidTemplateError,
    MissingVariablesError,
    TemplateInactiveError,
    TemplateNotFoundError,
)
from ..domain.models import (
    Category,
    DeliveryStatus,
    PreparedMessage,
    Template,
    VariableSpec,
    as_value_mapping,
    find_malformed_variables,
    humanize_variable,
    rank_templates,
    slugify,
    unresolved_in_final_text,
)
from .seed import initial_categories, initial_templates


@dataclass(frozen=True)
class MessagePreview:
    """Lo que la UI necesita mostrar mientras el operador completa las variables."""

    text: str
    missing: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing

    @property
    def missing_labels(self) -> tuple[str, ...]:
        return tuple(humanize_variable(name) for name in self.missing)


class MessageLibraryService:
    """Buscar, filtrar y administrar plantillas."""

    def __init__(self, repository) -> None:
        self.repository = repository

    # ------------------------------------------------------------------ carga inicial

    def ensure_seeded(self) -> int:
        """Carga el catálogo inicial sólo si la biblioteca está vacía.

        Devuelve cuántas plantillas se crearon. Es idempotente: en cualquier
        arranque posterior devuelve 0 y no toca lo que el operador editó.
        """
        for category in initial_categories():
            if self.repository.get_category(category.slug) is None:
                self.repository.save_category(category)
        if self.repository.list_templates(include_inactive=True):
            return 0
        created = 0
        for template in initial_templates():
            self.repository.save_template(template)
            created += 1
        return created

    # ------------------------------------------------------------------ consulta

    def list_categories(self, *, include_inactive: bool = False) -> Sequence[Category]:
        return self.repository.list_categories(include_inactive=include_inactive)

    def category_name(self, slug: str) -> str:
        category = self.repository.get_category(slugify(slug))
        return category.name if category else slug

    def search(
        self,
        query: str = "",
        *,
        category_slug: str | None = None,
        branch: str | None = None,
        only_favorites: bool = False,
        include_inactive: bool = False,
    ) -> Sequence[Template]:
        found = self.repository.search_templates(
            query=query,
            category_slug=slugify(category_slug) if category_slug else None,
            branch=str(branch).strip() if branch is not None else None,
            only_favorites=only_favorites,
            include_inactive=include_inactive,
        )
        return rank_templates(found, query)

    def list_branches(self) -> tuple[str, ...]:
        """Sucursales declaradas, sin convertirlas en una entidad nueva."""
        values = {
            template.branch
            for template in self.repository.list_templates(include_inactive=True)
            if template.branch
        }
        return tuple(sorted(values, key=str.casefold))

    def get(self, template_id: str) -> Template:
        template = self.repository.get_template(template_id)
        if template is None:
            raise TemplateNotFoundError("Esa plantilla ya no existe.")
        return template

    def variable_specs(self, template: Template) -> Sequence[VariableSpec]:
        return template.variable_specs

    def counts_by_category(self, *, include_inactive: bool = False) -> dict[str, int]:
        counts: dict[str, int] = {}
        for template in self.repository.list_templates(include_inactive=True):
            if not include_inactive and not template.active:
                continue
            counts[template.category_slug] = counts.get(template.category_slug, 0) + 1
        return counts

    # ------------------------------------------------------------------ administración

    def _require_category(self, slug: str) -> Category:
        category = self.repository.get_category(slugify(slug))
        if category is None:
            raise CategoryNotFoundError(f"La categoría «{slug}» no existe.")
        return category

    def create_template(
        self,
        *,
        title: str,
        body: str,
        category_slug: str,
        keywords: str = "",
        active: bool = True,
        favorite: bool = False,
        branch: str = "",
        variable_specs: Sequence[VariableSpec] = (),
    ) -> Template:
        self._require_category(category_slug)
        template = Template(
            title=title,
            body=body,
            category_slug=category_slug,
            keywords=keywords,
            active=active,
            favorite=favorite,
            branch=branch,
            origin="manual",
            variable_specs=tuple(variable_specs),
        )
        self.repository.save_template(template)
        return template

    def update_template(self, template_id: str, **changes) -> Template:
        template = self.get(template_id)
        if "category_slug" in changes:
            self._require_category(changes["category_slug"])
        updated = template.edited(**changes)
        self.repository.save_template(updated)
        return updated

    def set_active(self, template_id: str, active: bool) -> Template:
        updated = self.get(template_id).with_active(active)
        self.repository.save_template(updated)
        return updated

    def set_favorite(self, template_id: str, favorite: bool) -> Template:
        updated = self.get(template_id).with_favorite(favorite)
        self.repository.save_template(updated)
        return updated

    def toggle_favorite(self, template_id: str) -> Template:
        template = self.get(template_id)
        return self.set_favorite(template_id, not template.favorite)

    def create_category(self, name: str, *, position: int | None = None) -> Category:
        slug = slugify(name)
        if not slug:
            raise InvalidTemplateError("La categoría necesita un nombre.")
        existing = self.repository.get_category(slug)
        if existing is not None:
            return existing
        if position is None:
            current = self.repository.list_categories(include_inactive=True)
            position = (max((item.position for item in current), default=0)) + 10
        category = Category(slug=slug, name=name, position=position)
        self.repository.save_category(category)
        return category

    # ------------------------------------------------------------------ validación

    @staticmethod
    def validate_draft(*, title: str, body: str, category_slug: str) -> tuple[str, ...]:
        """Errores comprensibles de un formulario, sin lanzar excepciones."""
        problems: list[str] = []
        if not str(title or "").strip():
            problems.append("Falta el título de la plantilla.")
        if not str(body or "").strip():
            problems.append("Falta el texto del mensaje.")
        if not slugify(str(category_slug or "")):
            problems.append("Elegí una categoría.")
        malformadas = find_malformed_variables(str(body or ""))
        if malformadas:
            problems.append(
                "Estos datos están mal escritos y se enviarían tal cual al cliente: "
                + ", ".join(malformadas)
                + ". Usá una sola palabra sin espacios ni números al principio, "
                "por ejemplo {{cliente}} o {{segundo_par}}."
            )
        return tuple(problems)


class MessagePreparationService:
    """Completar variables, previsualizar, copiar y registrar el historial."""

    def __init__(self, repository, *, clipboard=None) -> None:
        self.repository = repository
        self.clipboard = clipboard

    def preview(self, template: Template, values: Mapping[str, object]) -> MessagePreview:
        normalized = as_value_mapping(values)
        return MessagePreview(text=template.preview(normalized), missing=template.missing_for(normalized))

    def prepare(
        self,
        template: Template,
        values: Mapping[str, object],
        *,
        operator: str = "",
        final_text: str | None = None,
        channel: str = "whatsapp",
        subject_kind: str = "",
        subject_reference: str = "",
        copy_to_clipboard: bool = True,
    ) -> PreparedMessage:
        """Deja el mensaje listo, lo copia y lo registra en el historial.

        `final_text` permite que el operador ajuste el texto antes de copiar: se
        guarda exactamente lo que se copió, marcado como editado a mano.
        """
        if not template.active:
            raise TemplateInactiveError(
                "Esa plantilla está desactivada. Activala antes de usarla."
            )
        normalized = as_value_mapping(values)
        if final_text is None:
            # Sin texto propio: se arma desde los campos, que deben estar completos.
            rendered = template.render(normalized)
            text = rendered
        else:
            # El operador escribió el mensaje: lo que se valida es ese texto, no los
            # campos. Aun así no puede salir con datos sin resolver.
            text = str(final_text).strip()
            if not text:
                raise MissingVariablesError(("el mensaje final está vacío",))
            pendientes = unresolved_in_final_text(text, template.variables)
            if pendientes:
                raise MissingVariablesError(pendientes)
            rendered = template.preview(normalized)

        message = PreparedMessage(
            template_id=template.id,
            template_title=template.title,
            category_slug=template.category_slug,
            final_text=text,
            values=normalized,
            operator=operator,
            channel=channel,
            status=DeliveryStatus.PENDIENTE,
            subject_kind=subject_kind,
            subject_reference=subject_reference,
            manually_edited=text != rendered,
        )
        if copy_to_clipboard and self.clipboard is not None:
            self.clipboard.copy(text)

        self.repository.save_prepared_message(message)
        self.repository.save_template(template.used_once())
        # Telemetría local: base del envío directo futuro. Nadie la consume aún.
        self.repository.append_outbox_event(
            "message_prepared",
            {
                "message_id": message.id,
                "template_id": template.id,
                "template_title": template.title,
                "category_slug": template.category_slug,
                "operator": operator,
                "channel": channel,
                "manually_edited": message.manually_edited,
                "prepared_at": message.prepared_at.isoformat(),
            },
        )
        return message

    @staticmethod
    def pending_in_text(template: Template, text: str) -> tuple[str, ...]:
        """Qué falta resolver en el texto tal como está por copiarse."""
        return unresolved_in_final_text(text, template.variables)

    def recent(self, limit: int = 25) -> Sequence[PreparedMessage]:
        return self.repository.list_prepared_messages(limit=limit)
