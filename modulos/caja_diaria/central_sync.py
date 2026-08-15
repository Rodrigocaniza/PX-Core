"""Outbox local y contrato versionado para sincronizar cierres de BC Caja."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class SyncConflict(ValueError):
    """La misma clave idempotente fue reutilizada con contenido diferente."""


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PendingEvent:
    event_id: str
    payload: dict[str, Any]
    payload_hash: str
    attempts: int


class CentralSyncOutbox:
    """Persistencia separada: nunca abre ni modifica la base autoritativa de Caja."""

    def __init__(self, database: str | Path):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS central_sync_outbox(
                    event_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    delivered_at TEXT
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, factory=_ClosingConnection)
        connection.row_factory = sqlite3.Row
        return connection

    def enqueue_close(self, payload: Mapping[str, Any]) -> bool:
        required = {
            "schema_version", "event_id", "organization_id", "branch_id",
            "cashbox_id", "device_id", "cash_day_id", "operator_id",
            "closed_at", "expected_cash_pyg", "counted_cash_pyg", "difference_pyg",
        }
        missing = sorted(required.difference(payload))
        if missing:
            raise ValueError(f"faltan campos de contrato: {', '.join(missing)}")
        if payload["schema_version"] != "bc.cash.close.v1":
            raise ValueError("schema_version no soportada")
        serialized = canonical_json(payload)
        digest = payload_hash(payload)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_hash FROM central_sync_outbox WHERE event_id=?",
                (payload["event_id"],),
            ).fetchone()
            if row:
                if row["payload_hash"] != digest:
                    raise SyncConflict("event_id existente con payload diferente")
                return False
            connection.execute(
                "INSERT INTO central_sync_outbox(event_id,payload_json,payload_hash) VALUES(?,?,?)",
                (payload["event_id"], serialized, digest),
            )
        return True

    def pending(self, limit: int = 10) -> list[PendingEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM central_sync_outbox WHERE status='PENDING' ORDER BY rowid LIMIT ?",
                (limit,),
            ).fetchall()
        return [PendingEvent(row["event_id"], json.loads(row["payload_json"]), row["payload_hash"], row["attempts"]) for row in rows]

    def record_attempt(self, event_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE central_sync_outbox SET attempts=attempts+1 WHERE event_id=? AND status='PENDING'",
                (event_id,),
            )

    def mark_delivered(self, event_id: str, delivered_at: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE central_sync_outbox SET status='DELIVERED',delivered_at=? WHERE event_id=?",
                (delivered_at, event_id),
            )
