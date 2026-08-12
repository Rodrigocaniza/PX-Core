"""Modelos y reglas puras de BC Comunicaciones.

Una plantilla es texto con variables escritas como ``{{cliente}}``. El dominio
sabe extraerlas, validar que estén completas y renderizar el mensaje final. No
conoce SQLite, Tk ni el portapapeles.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Mapping, Sequence
from uuid import uuid4

from .errors import InvalidTemplateError, MissingVariablesError


LETRA = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
VARIABLE_PATTERN = re.compile(rf"\{{\{{\s*([{LETRA}][{LETRA}0-9_]*)\s*\}}\}}")
# Cualquier par de llaves dobles, válido o no: sirve para detectar los mal escritos.
LLAVES_PATTERN = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)

TITLE_MAX_LENGTH = 120
BODY_MAX_LENGTH = 4000


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def new_id() -> str:
    return str(uuid4())


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_search_text(value: str) -> str:
    """Texto comparable para búsqueda: sin acentos, minúsculas, espacios simples."""
    return " ".join(strip_accents(str(value or "")).lower().split())


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", strip_accents(str(value or "")).lower())
    return cleaned.strip("-")


def variable_key(name: str) -> str:
    """Clave canónica de una variable: sin acentos, minúsculas, con guion bajo."""
    return re.sub(r"\s+", "_", strip_accents(str(name or "")).lower().strip())


def extract_variables(body: str) -> tuple[str, ...]:
    """Variables del cuerpo, en orden de aparición y sin repetir."""
    found: list[str] = []
    for match in VARIABLE_PATTERN.finditer(str(body or "")):
        key = variable_key(match.group(1))
        if key and key not in found:
            found.append(key)
    return tuple(found)


def humanize_variable(name: str) -> str:
    return variable_key(name).replace("_", " ").strip().capitalize()


def find_malformed_variables(body: str) -> tuple[str, ...]:
    """Llaves dobles que NO son una variable válida, tal como las escribió el operador.

    `{{2do par}}`, `{{nombre del cliente}}` o `{{}}` se veían como texto común y
    viajaban tal cual al cliente. Acá se detectan para poder avisar a tiempo.
    """
    malas: list[str] = []
    for match in LLAVES_PATTERN.finditer(str(body or "")):
        if VARIABLE_PATTERN.fullmatch(match.group(0)):
            continue
        crudo = match.group(0)
        if crudo not in malas:
            malas.append(crudo)
    return tuple(malas)


def pending_marker(name: str) -> str:
    """Marcador que la vista previa deja donde falta un dato."""
    return f"[{humanize_variable(name)}]"


def unresolved_in_final_text(text: str, variables: Iterable[str]) -> tuple[str, ...]:
    """Qué queda sin resolver en el texto que realmente se va a copiar.

    Se valida el texto final y no los campos, porque el operador puede haberlo
    reescrito a mano. Detecta tanto los marcadores `[Dato]` de la vista previa
    como cualquier `{{variable}}` que haya quedado sin reemplazar.
    """
    contenido = str(text or "")
    pendientes: list[str] = []
    for name in variables:
        etiqueta = humanize_variable(name)
        if pending_marker(name) in contenido and etiqueta not in pendientes:
            pendientes.append(etiqueta)
    for match in LLAVES_PATTERN.finditer(contenido):
        crudo = match.group(0)
        if crudo not in pendientes:
            pendientes.append(crudo)
    return tuple(pendientes)


def render_body(body: str, values: Mapping[str, object]) -> str:
    """Reemplaza las variables del cuerpo; error si falta alguna obligatoria."""
    normalized = {variable_key(key): str(value or "").strip() for key, value in values.items()}
    missing = [name for name in extract_variables(body) if not normalized.get(name)]
    if missing:
        raise MissingVariablesError([humanize_variable(name) for name in missing])
    return VARIABLE_PATTERN.sub(lambda match: normalized[variable_key(match.group(1))], str(body))


def render_preview(body: str, values: Mapping[str, object]) -> str:
    """Vista previa tolerante: lo que falta se muestra resaltado, nunca rompe."""
    normalized = {variable_key(key): str(value or "").strip() for key, value in values.items()}

    def _replace(match: re.Match[str]) -> str:
        key = variable_key(match.group(1))
        supplied = normalized.get(key, "")
        return supplied if supplied else f"[{humanize_variable(key)}]"

    return VARIABLE_PATTERN.sub(_replace, str(body or ""))


def missing_variables(body: str, values: Mapping[str, object]) -> tuple[str, ...]:
    normalized = {variable_key(key): str(value or "").strip() for key, value in values.items()}
    return tuple(name for name in extract_variables(body) if not normalized.get(name))


class DeliveryStatus(str, Enum):
    """Estados previstos del ciclo de envío.

    El MVP sólo produce `PENDIENTE` (el mensaje se copia y se pega a mano). Los
    demás quedan definidos para el envío directo futuro sin migrar datos.
    """

    PENDIENTE = "PENDIENTE"
    ENVIADO = "ENVIADO"
    ENTREGADO = "ENTREGADO"
    RESPONDIDO = "RESPONDIDO"


@dataclass(frozen=True)
class Category:
    slug: str
    name: str
    position: int = 0
    active: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "slug", slugify(self.slug))
        object.__setattr__(self, "name", str(self.name or "").strip())
        if not self.slug:
            raise InvalidTemplateError("la categoría necesita un identificador")
        if not self.name:
            raise InvalidTemplateError("la categoría necesita un nombre")


@dataclass(frozen=True)
class VariableSpec:
    """Metadatos opcionales de una variable: etiqueta y ejemplo para el operador."""

    name: str
    label: str = ""
    example: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", variable_key(self.name))
        if not self.name:
            raise InvalidTemplateError("la variable necesita un nombre")
        object.__setattr__(self, "label", str(self.label or "").strip() or humanize_variable(self.name))
        object.__setattr__(self, "example", str(self.example or "").strip())


@dataclass(frozen=True)
class Template:
    title: str
    body: str
    category_slug: str
    keywords: str = ""
    active: bool = True
    favorite: bool = False
    branch: str = ""
    origin: str = "manual"
    usage_count: int = 0
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    revision: int = 0
    variable_specs: tuple[VariableSpec, ...] = ()

    def __post_init__(self) -> None:
        title = str(self.title or "").strip()
        if not title:
            raise InvalidTemplateError("el título de la plantilla es obligatorio")
        if len(title) > TITLE_MAX_LENGTH:
            raise InvalidTemplateError(f"el título no puede superar {TITLE_MAX_LENGTH} caracteres")
        object.__setattr__(self, "title", title)

        body = str(self.body or "").strip()
        if not body:
            raise InvalidTemplateError("el mensaje de la plantilla es obligatorio")
        if len(body) > BODY_MAX_LENGTH:
            raise InvalidTemplateError(f"el mensaje no puede superar {BODY_MAX_LENGTH} caracteres")
        object.__setattr__(self, "body", body)

        object.__setattr__(self, "category_slug", slugify(self.category_slug))
        if not self.category_slug:
            raise InvalidTemplateError("la plantilla necesita una categoría")

        object.__setattr__(self, "keywords", str(self.keywords or "").strip())
        object.__setattr__(self, "branch", str(self.branch or "").strip())
        object.__setattr__(self, "origin", str(self.origin or "manual").strip() or "manual")
        object.__setattr__(self, "active", bool(self.active))
        object.__setattr__(self, "favorite", bool(self.favorite))

        if isinstance(self.usage_count, bool) or not isinstance(self.usage_count, int) or self.usage_count < 0:
            raise InvalidTemplateError("el contador de uso es inválido")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 0:
            raise InvalidTemplateError("la revisión de la plantilla es inválida")

        declared = extract_variables(body)
        specs = {spec.name: spec for spec in (
            item if isinstance(item, VariableSpec) else VariableSpec(**dict(item))
            for item in self.variable_specs
        )}
        # Toda variable presente en el cuerpo tiene spec; las huérfanas se descartan.
        object.__setattr__(
            self,
            "variable_specs",
            tuple(specs.get(name, VariableSpec(name)) for name in declared),
        )

    @property
    def variables(self) -> tuple[str, ...]:
        return extract_variables(self.body)

    @property
    def search_blob(self) -> str:
        return normalize_search_text(f"{self.title} {self.keywords} {self.body}")

    def preview(self, values: Mapping[str, object]) -> str:
        return render_preview(self.body, values)

    def missing_for(self, values: Mapping[str, object]) -> tuple[str, ...]:
        return missing_variables(self.body, values)

    def render(self, values: Mapping[str, object]) -> str:
        return render_body(self.body, values)

    def edited(self, **changes) -> "Template":
        protected = {"id", "created_at", "revision", "usage_count"}
        rejected = protected.intersection(changes)
        if rejected:
            raise InvalidTemplateError(f"la edición intentó modificar campos protegidos: {sorted(rejected)}")
        return replace(self, **changes, revision=self.revision + 1, updated_at=utc_now())

    def with_favorite(self, favorite: bool) -> "Template":
        return replace(self, favorite=bool(favorite), updated_at=utc_now())

    def with_active(self, active: bool) -> "Template":
        return replace(self, active=bool(active), updated_at=utc_now())

    def used_once(self) -> "Template":
        return replace(self, usage_count=self.usage_count + 1, updated_at=utc_now())


@dataclass(frozen=True)
class PreparedMessage:
    """Un mensaje ya completado y copiado. Es el historial de envíos del MVP."""

    template_id: str
    template_title: str
    category_slug: str
    final_text: str
    values: Mapping[str, str] = field(default_factory=dict)
    operator: str = ""
    channel: str = "whatsapp"
    status: DeliveryStatus = DeliveryStatus.PENDIENTE
    delivery_reference: str = ""
    # Enganche para clientes/pedidos futuros sin migrar datos.
    subject_kind: str = ""
    subject_reference: str = ""
    manually_edited: bool = False
    id: str = field(default_factory=new_id)
    prepared_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        text = str(self.final_text or "").strip()
        if not text:
            raise InvalidTemplateError("el mensaje final no puede quedar vacío")
        object.__setattr__(self, "final_text", text)
        object.__setattr__(self, "status", DeliveryStatus(self.status))
        object.__setattr__(
            self,
            "values",
            {variable_key(key): str(value or "") for key, value in dict(self.values).items()},
        )
        for name in ("operator", "channel", "delivery_reference", "subject_kind", "subject_reference"):
            object.__setattr__(self, name, str(getattr(self, name) or "").strip())
        object.__setattr__(self, "manually_edited", bool(self.manually_edited))

    @property
    def summary(self) -> str:
        one_line = " ".join(self.final_text.split())
        return one_line if len(one_line) <= 90 else one_line[:87] + "…"


def rank_templates(templates: Iterable[Template], query: str) -> list[Template]:
    """Orden estable por relevancia: favoritos y coincidencia de título primero."""
    needle = normalize_search_text(query)

    def score(template: Template) -> tuple:
        title = normalize_search_text(template.title)
        keywords = normalize_search_text(template.keywords)
        if not needle:
            match_rank = 0
        elif title.startswith(needle):
            match_rank = 0
        elif needle in title:
            match_rank = 1
        elif needle in keywords:
            match_rank = 2
        else:
            match_rank = 3
        return (match_rank, 0 if template.favorite else 1, -template.usage_count, title)

    return sorted(templates, key=score)


def templates_matching(
    templates: Iterable[Template],
    *,
    query: str = "",
    category_slug: str | None = None,
    only_favorites: bool = False,
    include_inactive: bool = False,
) -> list[Template]:
    needle = normalize_search_text(query)
    selected: list[Template] = []
    for template in templates:
        if not include_inactive and not template.active:
            continue
        if only_favorites and not template.favorite:
            continue
        if category_slug and template.category_slug != slugify(category_slug):
            continue
        if needle and needle not in template.search_blob:
            continue
        selected.append(template)
    return rank_templates(selected, query)


def default_values_for(template: Template) -> dict[str, str]:
    return {name: "" for name in template.variables}


def has_unsaved_changes(original: Template | None, draft: Mapping[str, object]) -> bool:
    """Compara el formulario de administración contra la plantilla guardada."""
    fields = ("title", "body", "category_slug", "keywords", "active")
    if original is None:
        return any(str(draft.get(name, "")).strip() for name in ("title", "body"))
    for name in fields:
        if name not in draft:
            continue
        current = getattr(original, name)
        candidate = draft[name]
        if name == "active":
            if bool(candidate) != bool(current):
                return True
        elif name == "category_slug":
            if slugify(str(candidate)) != current:
                return True
        elif str(candidate or "").strip() != current:
            return True
    return False


def as_value_mapping(pairs: Sequence[tuple[str, object]] | Mapping[str, object]) -> dict[str, str]:
    items = pairs.items() if isinstance(pairs, Mapping) else pairs
    return {variable_key(key): str(value or "").strip() for key, value in items}
