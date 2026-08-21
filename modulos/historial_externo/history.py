"""Modelo y contrato de consulta de BC Historial (solo lectura)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol

@dataclass(frozen=True)
class HistoryQuery:
    document: str = ""
    name: str = ""
    phone: str = ""
    envelope: str = ""

    def cleaned(self) -> "HistoryQuery":
        return HistoryQuery(*(str(value or "").strip() for value in
                              (self.document, self.name, self.phone, self.envelope)))

    @property
    def has_terms(self) -> bool:
        query = self.cleaned()
        return any((query.document, query.name, query.phone, query.envelope))

@dataclass(frozen=True)
class HistoryEvent:
    occurred_at: str
    kind: str
    branch: str = ""
    envelope: str = ""
    seller: str = ""
    status: str = ""
    total: int | None = None
    cash: int | None = None
    card_check: int | None = None
    agreement: int | None = None
    balance: str = ""
    description: str = ""
    items: tuple[str, ...] = ()
    prescription: tuple[str, ...] = ()
    observations: str = ""
    trace: tuple[str, ...] = ()

@dataclass(frozen=True)
class PersonHistory:
    display_name: str = ""
    documents: tuple[str, ...] = ()
    phones: tuple[str, ...] = ()
    events: tuple[HistoryEvent, ...] = field(default_factory=tuple)

class HistoryReader(Protocol):
    def search(self, query: HistoryQuery, *, limit: int = 200) -> PersonHistory: ...
