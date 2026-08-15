from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .models import Principal, Role, Unit, utc_now
from .operations import _key
from .service import AccessDenied, CentralManagementService


DELIVERY_STATES = ("PENDIENTE", "ENVIANDO", "ENTREGADO", "CONFIRMADO", "REINTENTO", "FALLIDO", "CANCELADO")
FINAL_STATES = {"CONFIRMADO", "FALLIDO", "CANCELADO"}
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = (5, 15, 60)


@dataclass(frozen=True)
class DeliveryEnvelope:
    contract_version: int
    message_id: str
    idempotency_key: str
    unit: str
    pc: str | None
    author: str
    body: str
    created_at: str
    attempt: int
    sent_at: str

    def to_payload(self):
        return {
            "contract_version": self.contract_version,
            "message_id": self.message_id,
            "idempotency_key": self.idempotency_key,
            "target": {"unit": self.unit, "pc": self.pc},
            "author": self.author,
            "body": self.body,
            "created_at": self.created_at,
            "attempt": self.attempt,
            "sent_at": self.sent_at,
        }


@dataclass(frozen=True)
class Receipt:
    contract_version: int
    receipt_id: str
    message_id: str
    idempotency_key: str
    receiver: str
    received_at: str
    status: str = "ACCEPTED"


@dataclass(frozen=True)
class TransportResult:
    delivered: bool
    receipt: Receipt | None = None
    error_code: str | None = None
    error_message: str | None = None
    permanent: bool = False


class TransportAdapter(Protocol):
    def deliver(self, envelope: DeliveryEnvelope) -> TransportResult: ...


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("fecha sin zona horaria")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class DeterministicLocalTransport:
    """Receptor local durable. No usa red, credenciales ni PCs reales."""

    def __init__(self, repository):
        self.repository = repository

    def deliver(self, envelope: DeliveryEnvelope) -> TransportResult:
        target = (envelope.pc or "").upper()
        if target.startswith("UNKNOWN"):
            return TransportResult(False, error_code="PERMANENT_UNKNOWN_TARGET", error_message="Destino sintético inexistente", permanent=True)
        if target.startswith("OFFLINE"):
            return TransportResult(False, error_code="TRANSIENT_OFFLINE", error_message="Equipo sintético desconectado")
        with self.repository.connection() as con:
            prior = con.execute("SELECT * FROM simulated_receiver_inbox WHERE idempotency_key=?", (envelope.idempotency_key,)).fetchone()
            if prior:
                receipt = Receipt(1, prior["receipt_id"], prior["message_id"], envelope.idempotency_key, prior["receiver"], prior["received_at"])
                return TransportResult(True, receipt=receipt)
            received_at = envelope.sent_at
            receipt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bc-receipt:{envelope.idempotency_key}"))
            receiver = envelope.pc or envelope.unit
            con.execute("INSERT INTO simulated_receiver_inbox VALUES(?,?,?,?,?,?)",
                        (envelope.idempotency_key, receipt_id, envelope.message_id, receiver, received_at, _json(envelope.to_payload())))
            con.commit()
        return TransportResult(True, receipt=Receipt(1, receipt_id, envelope.message_id, envelope.idempotency_key, receiver, received_at))


class DeliveryService:
    def __init__(self, core: CentralManagementService, adapter: TransportAdapter | None = None):
        self.core, self.repository = core, core.repository
        self.adapter = adapter or DeterministicLocalTransport(self.repository)
        self._reconcile_orphans()

    def _reconcile_orphans(self):
        """Migra filas creadas por versiones previas; evita mensajes durables invisibles."""
        now = _iso(utc_now())
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute("""SELECT m.id,m.status FROM central_messages m
                LEFT JOIN message_delivery d ON d.message_id=m.id WHERE d.message_id IS NULL""").fetchall()
            for row in rows:
                legacy = row["status"]
                state = legacy if legacy in DELIVERY_STATES else "PENDIENTE"
                con.execute("INSERT INTO message_delivery(message_id,state,updated_at) VALUES(?,?,?)", (row["id"], state, now))
                self._history(con, row["id"], None, state, "SYSTEM_RECOVERY", {"reason": "LEGACY_ORPHAN_RECONCILIATION"})
            con.commit()

    def queue(self, actor: Principal, unit: Unit, body: str, pc: str | None = None):
        self.core._require(actor, "alerts.manage", unit)
        body, pc = body.strip(), (pc or "").strip() or None
        if not body:
            raise ValueError("mensaje obligatorio")
        payload = {"unit": unit.value, "target_pc": pc, "body": body}
        key = _key(payload)
        message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bc-central:{key}"))
        now = _iso(utc_now())
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT OR IGNORE INTO central_messages VALUES(?,?,?,?,?,?,?,?)",
                        (message_id, unit.value, pc, body, "PENDIENTE", key, actor.username, now))
            con.execute("INSERT OR IGNORE INTO central_outbox VALUES(?,?,?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()), "MESSAGE", message_id, "CENTRAL_MESSAGE_QUEUED", _json(payload), key, "PENDING", 0, now))
            exists = con.execute("SELECT 1 FROM message_delivery WHERE message_id=?", (message_id,)).fetchone()
            if not exists:
                con.execute("INSERT INTO message_delivery(message_id,state,updated_at) VALUES(?,'PENDIENTE',?)", (message_id, now))
                self._history(con, message_id, None, "PENDIENTE", actor.username, {"idempotency_key": key})
                self.repository.audit(con, actor.username, "MESSAGE_QUEUED", message_id, details={"unit": unit.value, "target_pc": pc, "delivery": "PENDING"})
            con.commit()
        return message_id, key

    def _history(self, con, message_id, before, after, actor, details=None, now=None):
        con.execute("INSERT INTO message_delivery_history(message_id,from_state,to_state,actor,details_json,recorded_at) VALUES(?,?,?,?,?,?)",
                    (message_id, before, after, actor, _json(details or {}), _iso(now or utc_now())))

    def recover_abandoned(self, actor: Principal, now: datetime | None = None, stale_after=timedelta(minutes=2)):
        self.core._require(actor, "alerts.manage")
        now = now or utc_now(); cutoff = _iso(now - stale_after); recovered = 0
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute("SELECT message_id FROM message_delivery WHERE state='ENVIANDO' AND last_attempt_at<=?", (cutoff,)).fetchall()
            for row in rows:
                con.execute("UPDATE message_delivery SET state='REINTENTO',next_attempt_at=?,error_code='TRANSIENT_INTERRUPTED',error_message='Intento interrumpido; recuperación local',updated_at=? WHERE message_id=?",
                            (_iso(now), _iso(now), row["message_id"]))
                self._history(con, row["message_id"], "ENVIANDO", "REINTENTO", actor.username, {"reason": "ABANDONED_SEND_RECOVERY"}, now)
                recovered += 1
            con.commit()
        return recovered

    def process_due(self, actor: Principal, now: datetime | None = None, limit=50, auto_ack=True):
        self.core._require(actor, "alerts.manage")
        now = now or utc_now(); processed = []
        with self.repository.connection() as con:
            ids = [r[0] for r in con.execute("""SELECT d.message_id FROM message_delivery d
                WHERE d.state='PENDIENTE' OR (d.state='REINTENTO' AND d.next_attempt_at<=?)
                ORDER BY d.updated_at,d.message_id LIMIT ?""", (_iso(now), limit)).fetchall()]
        for message_id in ids:
            result = self._attempt(actor, message_id, now)
            processed.append((message_id, result))
            if auto_ack and result.receipt:
                self.accept_ack(actor, result.receipt)
        return processed

    def _attempt(self, actor: Principal, message_id: str, now: datetime):
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("""SELECT m.*,d.state,d.attempts FROM central_messages m
                JOIN message_delivery d ON d.message_id=m.id WHERE m.id=?""", (message_id,)).fetchone()
            if not row or row["state"] not in {"PENDIENTE", "REINTENTO"}:
                raise ValueError("mensaje no disponible para envío")
            attempt = row["attempts"] + 1
            con.execute("UPDATE message_delivery SET state='ENVIANDO',attempts=?,last_attempt_at=?,next_attempt_at=NULL,error_code=NULL,error_message=NULL,updated_at=? WHERE message_id=?",
                        (attempt, _iso(now), _iso(now), message_id))
            self._history(con, message_id, row["state"], "ENVIANDO", actor.username, {"attempt": attempt}, now)
            con.commit()
        envelope = DeliveryEnvelope(1, row["id"], row["idempotency_key"], row["target_unit"], row["target_pc"], row["created_by"], row["body"], row["created_at"], attempt, _iso(now))
        try:
            result = self.adapter.deliver(envelope)
        except Exception:
            result = TransportResult(False, error_code="TRANSIENT_ADAPTER_ERROR", error_message="Error transitorio sanitizado")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            if result.delivered:
                con.execute("UPDATE message_delivery SET state='ENTREGADO',delivered_at=COALESCE(delivered_at,?),updated_at=? WHERE message_id=?", (_iso(now), _iso(now), message_id))
                con.execute("UPDATE central_messages SET status='ENTREGADO' WHERE id=?", (message_id,))
                con.execute("UPDATE central_outbox SET status='DELIVERED',attempts=? WHERE aggregate_id=?", (attempt, message_id))
                self._history(con, message_id, "ENVIANDO", "ENTREGADO", actor.username, {"attempt": attempt}, now)
            else:
                exhausted = result.permanent or attempt >= MAX_ATTEMPTS
                state = "FALLIDO" if exhausted else "REINTENTO"
                next_at = None if exhausted else _iso(now + timedelta(seconds=BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]))
                con.execute("UPDATE message_delivery SET state=?,next_attempt_at=?,error_code=?,error_message=?,updated_at=? WHERE message_id=?",
                            (state, next_at, result.error_code, (result.error_message or "Error de transporte")[:240], _iso(now), message_id))
                con.execute("UPDATE central_messages SET status=? WHERE id=?", (state, message_id))
                con.execute("UPDATE central_outbox SET status=?,attempts=? WHERE aggregate_id=?", (state, attempt, message_id))
                self._history(con, message_id, "ENVIANDO", state, actor.username, {"attempt": attempt, "error_code": result.error_code}, now)
            con.commit()
        return result

    def accept_ack(self, actor: Principal, receipt: Receipt):
        self.core._require(actor, "alerts.manage")
        if receipt.contract_version != 1 or receipt.status != "ACCEPTED":
            raise ValueError("receipt inválido")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("""SELECT m.idempotency_key,d.state FROM central_messages m
                JOIN message_delivery d ON d.message_id=m.id WHERE m.id=?""", (receipt.message_id,)).fetchone()
            if not row or row["idempotency_key"] != receipt.idempotency_key:
                raise ValueError("ACK no corresponde al mensaje")
            prior = con.execute("SELECT 1 FROM message_receipts WHERE receipt_id=? OR idempotency_key=?", (receipt.receipt_id, receipt.idempotency_key)).fetchone()
            if prior:
                con.rollback(); return False
            if row["state"] not in {"ENTREGADO", "CONFIRMADO"}:
                raise ValueError("ACK recibido antes de entrega")
            con.execute("INSERT INTO message_receipts VALUES(?,?,?,?,?,?)", (receipt.receipt_id, receipt.message_id, receipt.idempotency_key, receipt.receiver, receipt.received_at, _json(asdict(receipt))))
            if row["state"] != "CONFIRMADO":
                con.execute("UPDATE message_delivery SET state='CONFIRMADO',confirmed_at=?,updated_at=? WHERE message_id=?", (receipt.received_at, receipt.received_at, receipt.message_id))
                con.execute("UPDATE central_messages SET status='CONFIRMADO' WHERE id=?", (receipt.message_id,))
                con.execute("UPDATE central_outbox SET status='CONFIRMED' WHERE aggregate_id=?", (receipt.message_id,))
                self._history(con, receipt.message_id, row["state"], "CONFIRMADO", actor.username, {"receipt_id": receipt.receipt_id})
            con.commit(); return True

    def retry(self, actor: Principal, message_id: str, now: datetime | None = None):
        self.core._require(actor, "alerts.manage")
        now = now or utc_now()
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE"); row = con.execute("SELECT state FROM message_delivery WHERE message_id=?", (message_id,)).fetchone()
            if not row or row["state"] not in {"REINTENTO", "FALLIDO"}: raise ValueError("mensaje no reintentable")
            con.execute("UPDATE message_delivery SET state='REINTENTO',next_attempt_at=?,error_code=NULL,error_message=NULL,updated_at=? WHERE message_id=?", (_iso(now), _iso(now), message_id))
            self._history(con, message_id, row["state"], "REINTENTO", actor.username, {"manual": True}, now); con.commit()

    def cancel(self, actor: Principal, message_id: str, reason: str, now: datetime | None = None):
        self.core._require(actor, "alerts.manage"); reason = reason.strip(); now = now or utc_now()
        if not reason: raise ValueError("motivo de cancelación obligatorio")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE"); row = con.execute("SELECT state FROM message_delivery WHERE message_id=?", (message_id,)).fetchone()
            if not row or row["state"] not in {"PENDIENTE", "REINTENTO", "FALLIDO"}: raise ValueError("mensaje no cancelable")
            con.execute("UPDATE message_delivery SET state='CANCELADO',cancelled_at=?,cancelled_by=?,cancel_reason=?,next_attempt_at=NULL,updated_at=? WHERE message_id=?", (_iso(now), actor.username, reason, _iso(now), message_id))
            con.execute("UPDATE central_messages SET status='CANCELADO' WHERE id=?", (message_id,)); con.execute("UPDATE central_outbox SET status='CANCELLED' WHERE aggregate_id=?", (message_id,))
            self._history(con, message_id, row["state"], "CANCELADO", actor.username, {"reason": reason}, now); con.commit()

    def list_messages(self, actor: Principal, *, start=None, end=None, unit=None, pc=None, state=None):
        if actor.role == Role.OPERADOR_LOCAL: raise AccessDenied("operador local sin acceso a mensajes centrales")
        self.core._require(actor, "dashboard.read")
        query = """SELECT m.*,d.state,d.attempts,d.last_attempt_at,d.next_attempt_at,d.delivered_at,d.confirmed_at,d.error_code,d.error_message,d.cancel_reason,d.updated_at
            FROM central_messages m JOIN message_delivery d ON d.message_id=m.id WHERE 1=1"""; params=[]
        for clause, value in (("date(m.created_at)>=?", start), ("date(m.created_at)<=?", end), ("m.target_unit=?", unit.value if isinstance(unit, Unit) else unit), ("m.target_pc LIKE ?", f"%{pc}%" if pc else None), ("d.state=?", state)):
            if value: query += " AND " + clause; params.append(value)
        if actor.unit: query += " AND m.target_unit=?"; params.append(actor.unit.value)
        query += " ORDER BY m.created_at DESC,m.id"
        with self.repository.connection() as con: return [dict(r) for r in con.execute(query, params).fetchall()]

    def history(self, actor: Principal, message_id: str):
        if actor.role == Role.OPERADOR_LOCAL: raise AccessDenied("operador local sin acceso")
        self.core._require(actor, "dashboard.read")
        with self.repository.connection() as con: return [dict(r) for r in con.execute("SELECT * FROM message_delivery_history WHERE message_id=? ORDER BY id", (message_id,)).fetchall()]
