"""Bandeja local durable para correcciones pedidas por Gestión Central."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Mapping, Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class CajaCorrectionInbox:
    """Recibe instrucciones; la edición sigue perteneciendo al servicio de Caja."""

    def __init__(self, repository):
        self.repository = repository

    def receive(self, correction: Mapping[str, Any]) -> bool:
        required = {"id", "idempotency_key", "identity", "source_entry_id",
                    "source_version", "reason", "requested_by", "requested_at"}
        missing = sorted(required.difference(correction))
        if missing:
            raise ValueError(f"faltan campos de corrección: {', '.join(missing)}")
        reason = str(correction["reason"]).strip()
        if not reason:
            raise ValueError("la corrección requiere una observación")
        with self.repository._connection() as con:
            con.execute("BEGIN IMMEDIATE")
            prior = con.execute(
                "SELECT id FROM central_review_corrections WHERE idempotency_key=?",
                (correction["idempotency_key"],),
            ).fetchone()
            if prior:
                con.rollback()
                return False
            entry = con.execute("SELECT revision FROM cash_entries WHERE id=?",
                                (correction["source_entry_id"],)).fetchone()
            if not entry:
                raise ValueError("la solicitud no corresponde a una venta de esta Caja")
            con.execute("""INSERT INTO central_review_corrections(
                id,idempotency_key,review_identity,cash_entry_id,requested_version,
                field_name,reason,requested_by,requested_at
              ) VALUES(?,?,?,?,?,?,?,?,?)""", (
                correction["id"], correction["idempotency_key"], correction["identity"],
                correction["source_entry_id"], correction["source_version"],
                correction.get("field_name"), reason, correction["requested_by"],
                correction["requested_at"],
            ))
            self._event(con, correction["id"], "RECIBIDA", "SYSTEM", {})
            con.commit()
        return True

    def pending(self):
        with self.repository._connection() as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM central_review_corrections WHERE status IN ('PENDIENTE','VISTA','REABIERTA') ORDER BY requested_at,id"
            )]

    def mark_seen(self, correction_id: str, actor: str) -> None:
        with self.repository._connection() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE central_review_corrections SET status='VISTA',seen_by=?,seen_at=? WHERE id=? AND status IN ('PENDIENTE','REABIERTA')",
                        (actor, _now(), correction_id))
            self._event(con, correction_id, "VISTA", actor, {})
            con.commit()

    def resolve(self, correction_id: str, *, actor: str, reason: str) -> int:
        """Sella que hubo una edición auditada y devuelve su nueva revisión."""
        reason = reason.strip()
        if not reason:
            raise ValueError("resolver requiere el motivo de edición")
        with self.repository._connection() as con:
            con.execute("BEGIN IMMEDIATE")
            correction = con.execute("SELECT * FROM central_review_corrections WHERE id=?", (correction_id,)).fetchone()
            if not correction:
                raise ValueError("solicitud inexistente")
            entry = con.execute("SELECT revision FROM cash_entries WHERE id=?", (correction["cash_entry_id"],)).fetchone()
            if not entry or int(entry["revision"]) <= int(correction["requested_version"]):
                raise ValueError("primero debe guardar una corrección auditada de la venta")
            audit = con.execute("SELECT action,snapshot_json FROM cash_entry_revisions WHERE entry_id=? AND revision=?",
                                (correction["cash_entry_id"], entry["revision"])).fetchone()
            audit_details = json.loads(audit["snapshot_json"]).get("audit", {}) if audit else {}
            if (not audit or audit["action"] != "UPDATE"
                    or not str(audit_details.get("reason", "")).strip()
                    or not str(audit_details.get("user", "")).strip()):
                raise ValueError("la corrección debe conservar su revisión auditada")
            con.execute("""UPDATE central_review_corrections SET status='RESUELTA',resolved_by=?,
                resolved_at=?,resolved_version=?,resolution_reason=? WHERE id=?""",
                (actor,_now(),entry["revision"],reason,correction_id))
            self._event(con, correction_id, "RESUELTA", actor,
                        {"resolved_version": entry["revision"], "reason": reason})
            con.commit()
            return int(entry["revision"])

    @staticmethod
    def _event(con: sqlite3.Connection, correction_id: str, action: str,
               actor: str, details: Mapping[str, Any]) -> None:
        con.execute("INSERT INTO central_review_correction_events VALUES(?,?,?,?,?,?)", (
            str(uuid.uuid4()), correction_id, action, actor,
            json.dumps(details, ensure_ascii=False, sort_keys=True), _now(),
        ))
