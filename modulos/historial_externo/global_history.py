"""Cliente global: federación read-only, identidad fuerte y mínimo privilegio.

Autenticación, cifrado y auditoría pertenecen a BC Seguridad/Sync. Historial
recibe un principal ya autenticado y fuentes ya autorizadas; no inventa otra
sesión, credencial ni persistencia.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .history import HistoryEvent, HistoryQuery, HistoryReader, PersonHistory

VIEW_LOCAL = "history.customer.read.local"
VIEW_GLOBAL = "history.customer.read.global"
WRITE_CROSS_BRANCH = "operations.cross_branch.write"
ROLE_OPERATOR = "OPERADOR"
ROLE_ADMIN = "ADMIN"
ROLE_FEDERATED_VIEWER = "VISOR_FEDERADO"
ALLOWED_ROLES = frozenset({ROLE_OPERATOR, ROLE_ADMIN, ROLE_FEDERATED_VIEWER})


class HistoryAccessDenied(PermissionError):
    pass


@dataclass(frozen=True)
class HistoryPrincipal:
    """Claims mínimas entregadas por BC Seguridad; no autentica por sí misma."""
    subject: str
    role: str
    branch: str
    permissions: frozenset[str] = field(default_factory=frozenset)
    authenticated: bool = True


class HistoryAccessPolicy:
    def require_view(self, principal: HistoryPrincipal) -> str:
        """Valida claims y devuelve ``GLOBAL`` o ``LOCAL`` sin elevar roles.

        Los permisos llegan de una sesión ya verificada. Aun si una operadora
        recibiera por error el claim global, su rol conserva alcance local.
        """
        role = principal.role.upper()
        if (not principal.authenticated or not str(principal.subject or "").strip()
                or role not in ALLOWED_ROLES):
            raise HistoryAccessDenied("La sesión no permite consultar BC Historial")
        if role in {ROLE_ADMIN, ROLE_FEDERATED_VIEWER}:
            if VIEW_GLOBAL not in principal.permissions:
                raise HistoryAccessDenied("La sesión no permite consultar el historial federado")
            return "GLOBAL"
        if VIEW_LOCAL not in principal.permissions or not _branch(principal.branch):
            raise HistoryAccessDenied("La operadora requiere una sucursal local verificada")
        return "LOCAL"

    def can_view_branch(self, principal: HistoryPrincipal, target_branch: str) -> bool:
        scope = self.require_view(principal)
        target = _branch(target_branch)
        return bool(target) and (scope == "GLOBAL" or target == _branch(principal.branch))

    def can_modify_branch(self, principal: HistoryPrincipal, target_branch: str) -> bool:
        """Contrato para consumidores operativos; Historial nunca escribe."""
        role = principal.role.upper()
        target = _branch(target_branch)
        if (not principal.authenticated or role not in ALLOWED_ROLES or not target
                or not str(principal.subject or "").strip()):
            return False
        if role == ROLE_FEDERATED_VIEWER:
            return False
        if role == ROLE_ADMIN:
            return True
        local = _branch(principal.branch)
        return bool(local) and local == target


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
        scope = self.policy.require_view(principal)
        query = query.cleaned()
        if not query.has_terms:
            raise ValueError("Ingresá al menos un dato para buscar")
        groups: dict[str, list[HistoryEvent]] = {}
        facts: dict[str, dict[str, list[str]]] = {}
        for source_number, source in enumerate(self.sources):
            local_branch = principal.branch if scope == "LOCAL" else ""
            profile = source.search(query, limit=limit, branch=local_branch)
            for event_number, event in enumerate(profile.events):
                # Un hecho sin procedencia no puede formar parte de una vista
                # multisucursal, tampoco para Admin o Visor Federado.
                if not _branch(event.branch):
                    continue
                if scope == "LOCAL" and not self.policy.can_view_branch(principal, event.branch):
                    continue
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
