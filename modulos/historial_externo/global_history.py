"""Cliente global: federación read-only, identidad fuerte y mínimo privilegio.

Autenticación, cifrado y auditoría pertenecen a BC Seguridad/Sync. Historial
recibe un principal ya autenticado y fuentes ya autorizadas; no inventa otra
sesión, credencial ni persistencia.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .history import HistoryEvent, HistoryQuery, HistoryReader, PersonHistory

VIEW_GLOBAL = "history.customer.read.global"
WRITE_CROSS_BRANCH = "operations.cross_branch.write"
ALLOWED_ROLES = frozenset({"OPERADOR", "ADMIN"})


class HistoryAccessDenied(PermissionError):
    pass


@dataclass(frozen=True)
class HistoryPrincipal:
    """Claims mínimas entregadas por BC Seguridad; no autentica por sí misma."""
    subject: str
    role: str
    branch: str
    permissions: frozenset[str] = field(default_factory=lambda: frozenset({VIEW_GLOBAL}))
    authenticated: bool = True


class HistoryAccessPolicy:
    def require_global_view(self, principal: HistoryPrincipal) -> None:
        if (not principal.authenticated or principal.role.upper() not in ALLOWED_ROLES
                or VIEW_GLOBAL not in principal.permissions):
            raise HistoryAccessDenied("La sesión no permite consultar el historial global")

    def can_modify_branch(self, principal: HistoryPrincipal, target_branch: str) -> bool:
        """Contrato para consumidores operativos; Historial nunca escribe."""
        if not principal.authenticated:
            return False
        if principal.role.upper() == "ADMIN" or WRITE_CROSS_BRANCH in principal.permissions:
            return True
        return _branch(principal.branch) == _branch(target_branch)


@dataclass(frozen=True)
class GlobalHistoryResult:
    candidates: tuple[PersonHistory, ...] = ()
    identity_resolution: str = "NONE"

    @property
    def selected(self) -> PersonHistory | None:
        return self.candidates[0] if len(self.candidates) == 1 else None


def _document(value: str) -> str:
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def _branch(value: str) -> str:
    return str(value or "").strip().upper()


class GlobalHistoryService:
    """Une hechos autorizados de una o varias fuentes canónicas sincronizadas."""
    def __init__(self, sources: Iterable[HistoryReader], *, policy=None) -> None:
        self.sources = tuple(sources)
        self.policy = policy or HistoryAccessPolicy()

    def search(self, principal: HistoryPrincipal, query: HistoryQuery,
               *, limit: int = 200) -> GlobalHistoryResult:
        self.policy.require_global_view(principal)
        query = query.cleaned()
        groups: dict[str, list[HistoryEvent]] = {}
        facts: dict[str, dict[str, list[str]]] = {}
        for source_number, source in enumerate(self.sources):
            profile = source.search(query, limit=limit)
            for event_number, event in enumerate(profile.events):
                document = _document(event.identity_document)
                if document:
                    key = "document:" + document
                else:
                    # Nombre/teléfono ayudan a buscar, pero jamás fusionan solos.
                    key = f"weak:{source_number}:{event.source_reference or event_number}"
                groups.setdefault(key, []).append(event)
                bucket = facts.setdefault(key, {"names": [], "documents": [], "phones": []})
                bucket["names"].append(event.identity_name or profile.display_name)
                bucket["documents"].append(event.identity_document)
                bucket["phones"].append(event.identity_phone)
        candidates = []
        for key, events in groups.items():
            events.sort(key=lambda event: event.occurred_at or "", reverse=True)
            fact = facts[key]
            names = _unique(fact["names"])
            candidates.append(PersonHistory(
                names[0] if names else query.name, _unique(fact["documents"]),
                _unique(fact["phones"]), tuple(events[:limit])))
        candidates.sort(key=lambda item: item.events[0].occurred_at if item.events else "", reverse=True)
        exact = bool(query.document and len(candidates) == 1
                     and _document(query.document) in {_document(value) for value in candidates[0].documents})
        resolution = "STRONG_DOCUMENT" if exact else ("AMBIGUOUS" if len(candidates) > 1 else "SINGLE_RECORD")
        return GlobalHistoryResult(tuple(candidates), resolution)


def _unique(values) -> tuple[str, ...]:
    result, seen = [], set()
    for value in values:
        clean = str(value or "").strip()
        if clean and clean.casefold() not in seen:
            seen.add(clean.casefold()); result.append(clean)
    return tuple(result)
