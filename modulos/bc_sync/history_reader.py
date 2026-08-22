from __future__ import annotations

from modulos.historial_externo.history import HistoryEvent, HistoryQuery, PersonHistory
from .store import SyncStore


def _norm(value: str) -> str:
    return "".join(c for c in str(value or "").casefold() if c.isalnum())


class SyncedHistoryReader:
    """Proyección read-only del journal recibido; implementa HistoryReader."""
    def __init__(self, store: SyncStore) -> None:
        self.store = store

    def search(self, query: HistoryQuery, *, limit: int = 200) -> PersonHistory:
        query = query.cleaned()
        results, names, documents, phones = [], [], [], []
        needles = [_norm(value) for value in (query.document, query.name, query.phone, query.envelope) if value]
        for event in self.store.events():
            payload = event.payload
            searchable = " ".join(str(payload.get(key, "")) for key in
                                  ("customer_document", "customer_name", "customer_phone", "envelope"))
            if needles and not any(needle in _norm(searchable) for needle in needles):
                continue
            names.append(str(payload.get("customer_name", "")))
            documents.append(str(payload.get("customer_document", "")))
            phones.append(str(payload.get("customer_phone", "")))
            results.append(HistoryEvent(
                event.occurred_at, event.event_type, branch=event.branch_id,
                envelope=str(payload.get("envelope", "")), seller=str(payload.get("seller", "")),
                status=str(payload.get("status", "")), total=payload.get("total"),
                description=str(payload.get("description", "")),
                items=tuple(payload.get("items", ())), prescription=tuple(payload.get("prescription", ())),
                observations=str(payload.get("observations", "")),
                trace=(f"sync:{event.event_id}",),
                identity_document=str(payload.get("customer_document", "")),
                identity_phone=str(payload.get("customer_phone", "")),
                identity_name=str(payload.get("customer_name", "")),
                source_reference=str(payload.get("source_reference", event.event_id))))
        unique = lambda values: tuple(dict.fromkeys(value for value in values if value))
        return PersonHistory((unique(names) or (query.name,))[0], unique(documents), unique(phones),
                             tuple(results[:max(1, min(limit, 1000))]))
