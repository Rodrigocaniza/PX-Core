from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class SyncEvent:
    event_id: str
    installation_id: str
    branch_id: str
    event_type: str
    occurred_at: str
    schema_version: int
    payload: Mapping[str, Any]
    idempotency_key: str
    sync_state: str = "PENDING"

    @classmethod
    def create(cls, *, installation_id: str, branch_id: str, event_type: str,
               payload: Mapping[str, Any], idempotency_key: str,
               occurred_at: str | None = None, schema_version: int = 1) -> "SyncEvent":
        return cls(str(uuid4()), installation_id, branch_id.upper(), event_type.upper(),
                   occurred_at or datetime.now(timezone.utc).isoformat(), schema_version,
                   dict(payload), idempotency_key, "PENDING")

    def validate(self) -> None:
        if not all((self.event_id, self.installation_id, self.branch_id,
                    self.event_type, self.occurred_at, self.idempotency_key)):
            raise ValueError("evento de sincronización incompleto")
        if self.schema_version < 1:
            raise ValueError("schema_version inválida")
        json.dumps(self.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def wire_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "event_id": self.event_id, "installation_id": self.installation_id,
            "branch_id": self.branch_id, "type": self.event_type,
            "timestamp": self.occurred_at, "schema_version": self.schema_version,
            "payload": dict(self.payload), "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def from_wire(cls, value: Mapping[str, Any]) -> "SyncEvent":
        event = cls(str(value["event_id"]), str(value["installation_id"]),
                    str(value["branch_id"]).upper(), str(value["type"]).upper(),
                    str(value["timestamp"]), int(value["schema_version"]),
                    dict(value["payload"]), str(value["idempotency_key"]), "RECEIVED")
        event.validate()
        return event
