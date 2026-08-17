"""Sincronización offline de solo lectura y revisión de ventas de Gestión Central."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import Principal
from .service import AccessDenied


REVIEW_FIELDS = (
    "date", "customer_name", "envelope", "customer_document", "customer_phone",
    "saleswoman", "items", "codes", "laboratory", "prescription",
    "total", "cash", "card_transfer", "agreement", "balance",
    "delivery_date", "factufacil_status", "recorded_by",
)
REVIEW_STATUSES = {
    "UNREVIEWED", "IN_REVIEW", "REVIEWED", "WITH_OBSERVATION",
    "REQUIRES_CORRECTION", "CORRECTED_PENDING_REVALIDATION",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ImportResult:
    snapshot_id: str
    period: str
    unit: str
    processed: int
    inserted: int
    unchanged: int
    changed: int


class ReviewService:
    def __init__(self, repository):
        self.repository = repository
        self.migrate()

    @staticmethod
    def _require(actor: Principal, permission: str):
        if not actor.allows(permission):
            raise AccessDenied(f"{actor.role.value} no tiene permiso {permission}")

    def migrate(self):
        with self.repository.connection() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS real_sync_snapshots(
              id TEXT PRIMARY KEY, organization TEXT NOT NULL, branch TEXT NOT NULL,
              cashbox TEXT NOT NULL, business_date TEXT NOT NULL, source_sha256 TEXT NOT NULL,
              source_integrity TEXT NOT NULL, source_kind TEXT NOT NULL,
              imported_at TEXT NOT NULL, UNIQUE(organization,branch,cashbox,business_date,source_sha256)
            );
            CREATE TABLE IF NOT EXISTS review_sales(
              identity TEXT PRIMARY KEY, organization TEXT NOT NULL, branch TEXT NOT NULL,
              cashbox TEXT NOT NULL, business_date TEXT NOT NULL, source_entry_id TEXT NOT NULL,
              current_version INTEGER NOT NULL, current_content_hash TEXT NOT NULL,
              payload_json TEXT NOT NULL, review_status TEXT NOT NULL DEFAULT 'UNREVIEWED',
              selected INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_sale_versions(
              identity TEXT NOT NULL REFERENCES review_sales(identity), version INTEGER NOT NULL,
              content_hash TEXT NOT NULL, payload_json TEXT NOT NULL, snapshot_id TEXT NOT NULL,
              imported_at TEXT NOT NULL, PRIMARY KEY(identity,version,content_hash)
            );
            CREATE TABLE IF NOT EXISTS review_fields(
              identity TEXT NOT NULL REFERENCES review_sales(identity), field_name TEXT NOT NULL,
              reviewed_hash TEXT NOT NULL, valid INTEGER NOT NULL DEFAULT 1,
              reviewed_by TEXT NOT NULL, reviewed_at TEXT NOT NULL,
              PRIMARY KEY(identity,field_name)
            );
            CREATE TABLE IF NOT EXISTS review_events(
              id TEXT PRIMARY KEY, identity TEXT NOT NULL, actor TEXT NOT NULL,
              action TEXT NOT NULL, from_status TEXT NOT NULL, to_status TEXT NOT NULL,
              details_json TEXT NOT NULL, recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_review_events_identity ON review_events(identity,recorded_at);
            CREATE TABLE IF NOT EXISTS review_notes(
              id TEXT PRIMARY KEY, identity TEXT NOT NULL, field_name TEXT,
              note TEXT NOT NULL, author TEXT NOT NULL, recorded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_alert_outbox(
              id TEXT PRIMARY KEY, identity TEXT NOT NULL, branch TEXT NOT NULL,
              message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
              created_by TEXT NOT NULL, created_at TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS review_inbox(
              id TEXT PRIMARY KEY, branch TEXT NOT NULL, payload_json TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'PENDING', received_at TEXT NOT NULL
            );
            """)
            con.commit()

    @staticmethod
    def _source(path: Path):
        con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        return con

    @staticmethod
    def snapshot_hash(path: Path) -> str:
        value = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                value.update(chunk)
        return value.hexdigest()

    def import_snapshot(self, actor: Principal, snapshot_path: Path, *, organization="BC", branch="Pilar", period=None) -> ImportResult:
        self._require(actor, "sync.write")
        source_hash = self.snapshot_hash(snapshot_path)
        source = self._source(snapshot_path)
        try:
            integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok": raise ValueError("snapshot inválido")
            if period:
                day = source.execute("SELECT * FROM cash_days WHERE status='CLOSED' AND business_date=? ORDER BY closed_at DESC LIMIT 1", (period,)).fetchone()
            else:
                day = source.execute("SELECT * FROM cash_days WHERE status='CLOSED' ORDER BY business_date DESC,closed_at DESC LIMIT 1").fetchone()
            if not day: raise ValueError("no existe cierre válido en el snapshot")
            cashbox = day["unit"]
            entries = source.execute("SELECT * FROM cash_entries WHERE cash_day_id=? AND status='ACTIVE' ORDER BY created_at,id", (day["id"],)).fetchall()
            items = source.execute("SELECT * FROM sale_items WHERE cash_entry_id IN (SELECT id FROM cash_entries WHERE cash_day_id=?) ORDER BY cash_entry_id,position", (day["id"],)).fetchall()
            orders = source.execute("SELECT * FROM orders WHERE cash_entry_id IN (SELECT id FROM cash_entries WHERE cash_day_id=?)", (day["id"],)).fetchall()
        finally:
            source.close()
        source_hash_after_read = self.snapshot_hash(snapshot_path)
        if source_hash_after_read != source_hash:
            raise RuntimeError("el snapshot cambió durante la lectura; importación cancelada")
        item_map, order_map = {}, {row["cash_entry_id"]: row for row in orders}
        for item in items: item_map.setdefault(item["cash_entry_id"], []).append(item)
        snapshot_id = digest({"organization": organization, "branch": branch, "cashbox": cashbox, "date": day["business_date"], "sha": source_hash})
        inserted = unchanged = changed = 0
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT OR IGNORE INTO real_sync_snapshots VALUES(?,?,?,?,?,?,?,?,?)", (snapshot_id,organization,branch,cashbox,day["business_date"],source_hash,integrity,"SQLITE_READONLY_SNAPSHOT",now_iso()))
            for entry in entries:
                sale_items = item_map.get(entry["id"], [])
                order = order_map.get(entry["id"])
                payload = {
                    "date": day["business_date"], "envelope": entry["envelope"] or "", "customer_name": entry["description"] or "",
                    "customer_document": entry["customer_document"] or "", "customer_phone": entry["customer_phone"] or "",
                    "saleswoman": entry["saleswoman"] or "", "items": " · ".join((row["description"] or "") for row in sale_items).strip(" ·") or entry["frame_origin"] or "",
                    "codes": " · ".join((row["code"] or "") for row in sale_items).strip(" ·") or entry["code"] or "",
                    "laboratory": " · ".join(dict.fromkeys(row["laboratory"] for row in sale_items if row["laboratory"])) or entry["laboratory"],
                    "prescription": " · ".join(filter(None, [entry["prescription_doctor"], entry["observations"]])),
                    "total": entry["total"] or 0, "cash": entry["cash"] or 0, "card_transfer": entry["card_check"] or 0,
                    "agreement": entry["agreement_amount"] or 0, "balance": entry["balance_text"] or "",
                    "delivery_date": (order["delivery_date"] if order else entry["delivery_date"]) or "",
                    "factufacil_status": "NO DISPONIBLE PILOTO", "recorded_by": entry["performed_by"] or entry["saleswoman"],
                }
                identity = digest({"organization":organization,"branch":branch,"cashbox":cashbox,"date":day["business_date"],"entry":entry["id"]})
                content_hash = digest(payload); version = int(entry["revision"] or 0)
                prior = con.execute("SELECT * FROM review_sales WHERE identity=?", (identity,)).fetchone()
                if not prior:
                    con.execute("INSERT INTO review_sales VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (identity,organization,branch,cashbox,day["business_date"],entry["id"],version,content_hash,canonical(payload),"UNREVIEWED",0,now_iso()))
                    inserted += 1
                elif prior["current_content_hash"] == content_hash:
                    unchanged += 1
                else:
                    old = json.loads(prior["payload_json"]); changed_fields=[name for name in REVIEW_FIELDS if old.get(name) != payload.get(name)]
                    invalidated=[]
                    for name in changed_fields:
                        reviewed=con.execute("SELECT 1 FROM review_fields WHERE identity=? AND field_name=? AND valid=1",(identity,name)).fetchone()
                        if reviewed:
                            con.execute("UPDATE review_fields SET valid=0 WHERE identity=? AND field_name=?",(identity,name)); invalidated.append(name)
                    target = "CORRECTED_PENDING_REVALIDATION" if invalidated else prior["review_status"]
                    con.execute("UPDATE review_sales SET current_version=?,current_content_hash=?,payload_json=?,review_status=?,updated_at=? WHERE identity=?",(version,content_hash,canonical(payload),target,now_iso(),identity))
                    self._event(con,identity,actor.username,"SOURCE_CHANGED",prior["review_status"],target,{"changed_fields":changed_fields,"invalidated_fields":invalidated,"before_hash":prior["current_content_hash"],"after_hash":content_hash})
                    changed += 1
                con.execute("INSERT OR IGNORE INTO review_sale_versions VALUES(?,?,?,?,?,?)",(identity,version,content_hash,canonical(payload),snapshot_id,now_iso()))
            self.repository.audit(con,actor.username,"REAL_SNAPSHOT_IMPORT",snapshot_id,details={"period":day["business_date"],"unit":cashbox,"processed":len(entries)})
            con.commit()
        return ImportResult(snapshot_id,day["business_date"],cashbox,len(entries),inserted,unchanged,changed)

    def _event(self, con, identity, actor, action, before, after, details=None):
        con.execute("INSERT INTO review_events VALUES(?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),identity,actor,action,before,after,canonical(details or {}),now_iso()))

    def list_sales(self, actor: Principal, *, status=None, cashbox=None, date=None, saleswoman=None, envelope=None):
        self._require(actor,"reviews.read")
        with self.repository.connection() as con: rows=con.execute("SELECT * FROM review_sales ORDER BY business_date,source_entry_id").fetchall()
        result=[]
        for row in rows:
            item=dict(row); item["payload"]=json.loads(item.pop("payload_json"))
            if status and status != "ALL" and item["review_status"] != status: continue
            if cashbox and item["cashbox"] != cashbox: continue
            if date and item["business_date"] != date: continue
            if saleswoman and saleswoman.lower() not in item["payload"]["saleswoman"].lower(): continue
            if envelope and envelope.lower() not in item["payload"]["envelope"].lower(): continue
            result.append(item)
        return result

    def progress(self, actor):
        rows=self.list_sales(actor); total=len(rows); reviewed=sum(r["review_status"]=="REVIEWED" for r in rows); observed=sum(r["review_status"] in {"WITH_OBSERVATION","REQUIRES_CORRECTION","CORRECTED_PENDING_REVALIDATION"} for r in rows)
        return {"total":total,"reviewed":reviewed,"pending":total-reviewed,"observations":observed,"percent":0 if not total else round(reviewed*100/total)}

    def reviewed_fields(self, actor, identity):
        self._require(actor,"reviews.read")
        with self.repository.connection() as con: return {r[0] for r in con.execute("SELECT field_name FROM review_fields WHERE identity=? AND valid=1",(identity,))}

    def mark_fields(self, actor, identity, fields):
        self._require(actor,"reviews.manage"); fields=tuple(dict.fromkeys(fields))
        if not fields or any(name not in REVIEW_FIELDS for name in fields): raise ValueError("campos de revisión inválidos")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE"); row=con.execute("SELECT * FROM review_sales WHERE identity=?",(identity,)).fetchone(); payload=json.loads(row["payload_json"]); before=row["review_status"]
            for name in fields: con.execute("INSERT INTO review_fields VALUES(?,?,?,?,?,?) ON CONFLICT(identity,field_name) DO UPDATE SET reviewed_hash=excluded.reviewed_hash,valid=1,reviewed_by=excluded.reviewed_by,reviewed_at=excluded.reviewed_at",(identity,name,digest(payload.get(name)),1,actor.username,now_iso()))
            count=con.execute("SELECT count(*) FROM review_fields WHERE identity=? AND valid=1",(identity,)).fetchone()[0]; after="REVIEWED" if count==len(REVIEW_FIELDS) else "IN_REVIEW"
            con.execute("UPDATE review_sales SET review_status=?,updated_at=? WHERE identity=?",(after,now_iso(),identity)); self._event(con,identity,actor.username,"FIELDS_REVIEWED",before,after,{"fields":fields}); con.commit()
        return after

    def mark_complete(self, actor, identity): return self.mark_fields(actor,identity,REVIEW_FIELDS)

    def mark_many(self, actor, identities):
        self._require(actor,"reviews.manage"); unique=tuple(dict.fromkeys(identities))
        for identity in unique: self.mark_complete(actor,identity)
        return len(unique)

    def add_note(self, actor, identity, note, field_name=None):
        self._require(actor,"reviews.manage"); note=note.strip()
        if not note: raise ValueError("observación vacía")
        if field_name and field_name not in REVIEW_FIELDS: raise ValueError("campo inválido")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE"); row=con.execute("SELECT review_status FROM review_sales WHERE identity=?",(identity,)).fetchone(); before=row[0]
            con.execute("INSERT INTO review_notes VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),identity,field_name,note,actor.username,now_iso())); con.execute("UPDATE review_sales SET review_status='WITH_OBSERVATION',updated_at=? WHERE identity=?",(now_iso(),identity)); self._event(con,identity,actor.username,"NOTE_ADDED",before,"WITH_OBSERVATION",{"field":field_name}); con.commit()

    def require_correction(self, actor, identity, reason):
        self._require(actor,"reviews.manage"); reason=reason.strip()
        if not reason: raise ValueError("motivo obligatorio")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE"); before=con.execute("SELECT review_status FROM review_sales WHERE identity=?",(identity,)).fetchone()[0]; con.execute("UPDATE review_sales SET review_status='REQUIRES_CORRECTION',updated_at=? WHERE identity=?",(now_iso(),identity)); self._event(con,identity,actor.username,"REOPEN_CORRECTION",before,"REQUIRES_CORRECTION",{"reason":reason}); con.commit()

    def create_branch_alert(self, actor, identity, message):
        self._require(actor,"reviews.manage"); message=message.strip()
        if not message: raise ValueError("mensaje obligatorio")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row=con.execute("SELECT branch,review_status FROM review_sales WHERE identity=?",(identity,)).fetchone(); key=digest({"identity":identity,"message":message})
            con.execute("INSERT OR IGNORE INTO review_alert_outbox VALUES(?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),identity,row[0],message,"PENDING",actor.username,now_iso(),key))
            self._event(con,identity,actor.username,"BRANCH_ALERT_QUEUED",row[1],row[1],{"idempotency_key":key})
            self.repository.audit(con,actor.username,"REVIEW_BRANCH_ALERT_QUEUED",identity,details={"idempotency_key":key,"delivery":"PENDING"})
            con.commit()
        return key

    def notes(self, actor, identity):
        self._require(actor,"reviews.read")
        with self.repository.connection() as con: return [dict(r) for r in con.execute("SELECT * FROM review_notes WHERE identity=? ORDER BY recorded_at,id",(identity,))]

    def events(self, actor, identity):
        self._require(actor,"reviews.read")
        with self.repository.connection() as con: return [dict(r) for r in con.execute("SELECT * FROM review_events WHERE identity=? ORDER BY recorded_at,id",(identity,))]
