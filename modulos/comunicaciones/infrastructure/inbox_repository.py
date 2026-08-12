"""Persistencia transaccional de la bandeja y su auditoría append-only."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from typing import Mapping, Sequence

from ..domain.inbox import Account, Conversation, ConversationFilter, ConversationStatus, Direction, Message, now_utc


class SQLiteInboxRepository:
    def __init__(self, repository) -> None:
        self.repository = repository

    def save_account(self, account: Account) -> None:
        with self.repository._connection() as db:
            db.execute("""INSERT INTO communication_accounts(id,business,branch,label,provider,active)
                VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET business=excluded.business,
                branch=excluded.branch,label=excluded.label,provider=excluded.provider,active=excluded.active""",
                (account.id, account.business, account.branch, account.label, account.provider, int(account.active)))
            db.commit()

    def list_accounts(self) -> Sequence[Account]:
        with self.repository._connection() as db:
            rows = db.execute("SELECT * FROM communication_accounts WHERE active=1 ORDER BY business,branch,label").fetchall()
        return [Account(r["id"], r["business"], r["branch"], r["label"], r["provider"], bool(r["active"])) for r in rows]

    def create_conversation(self, conversation: Conversation, actor: str = "SISTEMA") -> None:
        with self.repository._connection() as db:
            db.execute("""INSERT INTO conversations(id,account_id,contact_name,contact_reference,status,
                assigned_operator,subject,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                (conversation.id, conversation.account_id, conversation.contact_name, conversation.contact_reference,
                 conversation.status.value, conversation.assigned_operator, conversation.subject,
                 conversation.created_at.isoformat(), conversation.updated_at.isoformat()))
            self._audit(db, actor, "CONVERSATION_CREATED", "conversation", conversation.id,
                        {"status": conversation.status.value, "account_id": conversation.account_id})
            db.commit()

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self.repository._connection() as db:
            row = db.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        return self._conversation(row) if row else None

    def list_conversations(self, filters: ConversationFilter = ConversationFilter()) -> Sequence[Conversation]:
        clauses, values = ["1=1"], []
        for column, value in (("a.business", filters.business), ("a.branch", filters.branch),
                              ("c.account_id", filters.account_id), ("c.assigned_operator", filters.assigned_operator)):
            if value:
                clauses.append(f"{column}=?")
                values.append(value)
        if filters.status:
            clauses.append("c.status=?")
            values.append(ConversationStatus(filters.status).value)
        if filters.text:
            clauses.append("(lower(c.contact_name) LIKE ? OR lower(c.contact_reference) LIKE ? OR lower(c.subject) LIKE ? OR EXISTS (SELECT 1 FROM conversation_messages m WHERE m.conversation_id=c.id AND lower(m.body) LIKE ?))")
            token = f"%{filters.text.lower()}%"
            values.extend([token] * 4)
        sql = "SELECT c.* FROM conversations c JOIN communication_accounts a ON a.id=c.account_id WHERE " + " AND ".join(clauses) + " ORDER BY c.updated_at DESC,c.id"
        with self.repository._connection() as db:
            rows = db.execute(sql, values).fetchall()
        return [self._conversation(r) for r in rows]

    def update_status(self, conversation_id: str, status: ConversationStatus, actor: str) -> Conversation:
        from ..domain.inbox import validate_transition
        current = self._required(conversation_id)
        status = ConversationStatus(status)
        validate_transition(current.status, status)
        return self._update(current, actor, "STATUS_CHANGED", status=status,
                            details={"from": current.status.value, "to": status.value})

    def assign(self, conversation_id: str, operator: str, actor: str) -> Conversation:
        current = self._required(conversation_id)
        operator = operator.strip()
        return self._update(current, actor, "ASSIGNMENT_CHANGED", assigned_operator=operator,
                            details={"from": current.assigned_operator, "to": operator})

    def append_message(self, message: Message, actor: str) -> None:
        with self.repository._connection() as db:
            db.execute("""INSERT INTO conversation_messages(id,conversation_id,direction,body,occurred_at,operator,provider_reference)
                VALUES(?,?,?,?,?,?,?)""", (message.id,message.conversation_id,message.direction.value,message.body,
                message.occurred_at.isoformat(),message.operator,message.provider_reference))
            db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (message.occurred_at.isoformat(), message.conversation_id))
            self._audit(db, actor, "MESSAGE_APPENDED", "conversation", message.conversation_id,
                        {"message_id": message.id, "direction": message.direction.value})
            db.commit()

    def list_messages(self, conversation_id: str) -> Sequence[Message]:
        with self.repository._connection() as db:
            rows = db.execute("SELECT * FROM conversation_messages WHERE conversation_id=? ORDER BY occurred_at,id", (conversation_id,)).fetchall()
        return [Message(r["id"],r["conversation_id"],Direction(r["direction"]),r["body"],datetime.fromisoformat(r["occurred_at"]),r["operator"],r["provider_reference"]) for r in rows]

    def audit_log(self, entity_id: str) -> Sequence[Mapping[str, object]]:
        with self.repository._connection() as db:
            rows = db.execute("SELECT * FROM communication_audit WHERE entity_id=? ORDER BY sequence", (entity_id,)).fetchall()
        return [{**dict(r), "details": json.loads(r["details_json"])} for r in rows]

    def counts(self) -> Mapping[ConversationStatus, int]:
        result = {s: 0 for s in ConversationStatus}
        with self.repository._connection() as db:
            rows = db.execute("SELECT status,count(*) amount FROM conversations GROUP BY status").fetchall()
        result.update({ConversationStatus(r["status"]): r["amount"] for r in rows})
        return result

    def _required(self, conversation_id: str) -> Conversation:
        value = self.get_conversation(conversation_id)
        if value is None:
            raise KeyError(conversation_id)
        return value

    def _update(self, current, actor, action, details, **changes):
        updated = replace(current, updated_at=now_utc(), **changes)
        with self.repository._connection() as db:
            db.execute("UPDATE conversations SET status=?,assigned_operator=?,updated_at=? WHERE id=?",
                       (updated.status.value,updated.assigned_operator,updated.updated_at.isoformat(),updated.id))
            self._audit(db, actor, action, "conversation", updated.id, details)
            db.commit()
        return updated

    @staticmethod
    def _audit(db, actor, action, entity_type, entity_id, details):
        db.execute("INSERT INTO communication_audit(occurred_at,actor,action,entity_type,entity_id,details_json) VALUES(?,?,?,?,?,?)",
                   (now_utc().isoformat(), actor.strip() or "SISTEMA", action, entity_type, entity_id,
                    json.dumps(details, ensure_ascii=False, sort_keys=True)))

    @staticmethod
    def _conversation(r):
        return Conversation(r["id"],r["account_id"],r["contact_name"],r["contact_reference"],ConversationStatus(r["status"]),
                            r["assigned_operator"],r["subject"],datetime.fromisoformat(r["created_at"]),datetime.fromisoformat(r["updated_at"]))
