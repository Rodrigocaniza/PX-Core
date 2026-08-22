from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .model import SyncEvent


class ReplayDetected(ValueError):
    pass


class SyncStore:
    """Estado técnico de Sync; nunca contiene ni copia tablas operativas completas."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sync_events(
              event_id TEXT PRIMARY KEY, installation_id TEXT NOT NULL, branch_id TEXT NOT NULL,
              event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, schema_version INTEGER NOT NULL,
              payload_json TEXT NOT NULL, idempotency_key TEXT NOT NULL, direction TEXT NOT NULL,
              UNIQUE(installation_id, idempotency_key));
            CREATE TABLE IF NOT EXISTS sync_outbox(
              event_id TEXT PRIMARY KEY REFERENCES sync_events(event_id), state TEXT NOT NULL DEFAULT 'PENDING',
              attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT, last_error TEXT, acked_at TEXT);
            CREATE TABLE IF NOT EXISTS sync_inbox(
              event_id TEXT PRIMARY KEY REFERENCES sync_events(event_id), received_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sync_nonces(
              installation_id TEXT NOT NULL, nonce TEXT NOT NULL, seen_at TEXT NOT NULL,
              PRIMARY KEY(installation_id, nonce));
            CREATE TABLE IF NOT EXISTS sync_audit(
              sequence INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, action TEXT NOT NULL,
              event_id TEXT, installation_id TEXT, branch_id TEXT, detail TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS sync_conflicts(
              conflict_id INTEGER PRIMARY KEY AUTOINCREMENT, entity_key TEXT NOT NULL,
              local_event_id TEXT NOT NULL, remote_event_id TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'OPEN',
              detected_at TEXT NOT NULL, resolution TEXT);
            """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _values(event: SyncEvent):
        return (event.event_id, event.installation_id, event.branch_id, event.event_type,
                event.occurred_at, event.schema_version,
                json.dumps(event.payload, sort_keys=True, ensure_ascii=False), event.idempotency_key)

    def enqueue(self, event: SyncEvent) -> str:
        event.validate()
        with self.connect() as db:
            existing = db.execute("SELECT event_id FROM sync_events WHERE installation_id=? AND idempotency_key=?",
                                  (event.installation_id, event.idempotency_key)).fetchone()
            if existing:
                return existing["event_id"]
            db.execute("INSERT INTO sync_events VALUES(?,?,?,?,?,?,?,?, 'OUT')", self._values(event))
            db.execute("INSERT INTO sync_outbox(event_id) VALUES(?)", (event.event_id,))
            self._audit(db, "OUTBOX_ENQUEUED", event)
        return event.event_id

    def pending(self, limit: int = 100) -> tuple[SyncEvent, ...]:
        with self.connect() as db:
            rows = db.execute("SELECT e.* FROM sync_events e JOIN sync_outbox o USING(event_id) "
                              "WHERE o.state!='ACKED' ORDER BY e.occurred_at, e.event_id LIMIT ?", (limit,)).fetchall()
        return tuple(self._event(row, "PENDING") for row in rows)

    def mark_attempt(self, event: SyncEvent, error: str = "") -> None:
        with self.connect() as db:
            db.execute("UPDATE sync_outbox SET attempts=attempts+1,last_error=?,state='PENDING' WHERE event_id=?",
                       (error, event.event_id))
            self._audit(db, "SEND_FAILED" if error else "SEND_ATTEMPT", event, error)

    def acknowledge(self, event: SyncEvent) -> None:
        with self.connect() as db:
            db.execute("UPDATE sync_outbox SET state='ACKED',acked_at=?,last_error=NULL WHERE event_id=?",
                       (self._now(), event.event_id))
            self._audit(db, "SEND_ACKNOWLEDGED", event)

    def receive(self, event: SyncEvent, *, nonce: str | None = None) -> bool:
        event.validate()
        with self.connect() as db:
            if nonce is not None:  # Sólo adapter legado; BC Seguridad lleva su NonceLedger.
                try:
                    db.execute("INSERT INTO sync_nonces VALUES(?,?,?)",
                               (event.installation_id, nonce, self._now()))
                except sqlite3.IntegrityError as exc:
                    raise ReplayDetected("nonce ya recibido") from exc
            existing = db.execute("SELECT event_id FROM sync_events WHERE event_id=? OR "
                                  "(installation_id=? AND idempotency_key=?)",
                                  (event.event_id, event.installation_id, event.idempotency_key)).fetchone()
            if existing:
                self._audit(db, "RECEIVE_DUPLICATE", event)
                return False
            db.execute("INSERT INTO sync_events VALUES(?,?,?,?,?,?,?,?, 'IN')", self._values(event))
            db.execute("INSERT INTO sync_inbox VALUES(?,?)", (event.event_id, self._now()))
            self._audit(db, "RECEIVED", event)
        return True

    def record_conflict(self, entity_key: str, local_event_id: str, remote_event_id: str) -> None:
        with self.connect() as db:
            cursor = db.execute("INSERT INTO sync_conflicts(entity_key,local_event_id,remote_event_id,detected_at) VALUES(?,?,?,?)",
                                (entity_key, local_event_id, remote_event_id, self._now()))
            db.execute("INSERT INTO sync_audit(occurred_at,action,event_id,detail) VALUES(?,?,?,?)",
                       (self._now(), "CONFLICT_OPENED", remote_event_id,
                        json.dumps({"conflict_id": cursor.lastrowid, "entity_key": entity_key,
                                    "local_event_id": local_event_id})))

    def resolve_conflict(self, conflict_id: int, resolution: str) -> None:
        if not resolution.strip():
            raise ValueError("la resolución explícita es obligatoria")
        with self.connect() as db:
            row = db.execute("SELECT * FROM sync_conflicts WHERE conflict_id=? AND state='OPEN'",
                             (conflict_id,)).fetchone()
            if not row:
                raise KeyError(conflict_id)
            db.execute("UPDATE sync_conflicts SET state='RESOLVED',resolution=? WHERE conflict_id=?",
                       (resolution.strip(), conflict_id))
            db.execute("INSERT INTO sync_audit(occurred_at,action,event_id,detail) VALUES(?,?,?,?)",
                       (self._now(), "CONFLICT_RESOLVED", row["remote_event_id"],
                        json.dumps({"conflict_id": conflict_id, "resolution": resolution.strip()})))

    def events(self) -> tuple[SyncEvent, ...]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM sync_events ORDER BY occurred_at DESC,event_id").fetchall()
        return tuple(self._event(row, "STORED") for row in rows)

    def audit(self):
        with self.connect() as db:
            return tuple(dict(row) for row in db.execute("SELECT * FROM sync_audit ORDER BY sequence"))

    @staticmethod
    def _audit(db, action: str, event: SyncEvent, detail: str = "") -> None:
        db.execute("INSERT INTO sync_audit(occurred_at,action,event_id,installation_id,branch_id,detail) VALUES(?,?,?,?,?,?)",
                   (SyncStore._now(), action, event.event_id, event.installation_id,
                    event.branch_id, detail[:1000]))

    @staticmethod
    def _event(row, state: str) -> SyncEvent:
        return SyncEvent(row["event_id"], row["installation_id"], row["branch_id"],
                         row["event_type"], row["occurred_at"], row["schema_version"],
                         json.loads(row["payload_json"]), row["idempotency_key"], state)
