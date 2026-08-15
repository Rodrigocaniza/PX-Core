from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from .models import Principal, Unit, utc_now
from .service import CentralManagementService


ALERT_STATES = ("PENDIENTE", "VISTO", "CORREGIDO", "VERIFICADO", "DESCARTADO")
ALERT_TRANSITIONS = {
    "PENDIENTE": {"VISTO", "DESCARTADO"},
    "VISTO": {"CORREGIDO", "DESCARTADO"},
    "CORREGIDO": {"VERIFICADO", "VISTO"},
    "VERIFICADO": set(),
    "DESCARTADO": set(),
}
DAILY_REVIEW_FIELDS = ("CIERRE", "VENTAS_SOBRES", "SALIDAS", "ARQUEO", "PDF")


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _key(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DateRange:
    start: str
    end: str

    def __post_init__(self):
        start, end = date.fromisoformat(self.start), date.fromisoformat(self.end)
        if start > end:
            raise ValueError("la fecha desde no puede ser posterior a la fecha hasta")
        if (end - start).days > 366:
            raise ValueError("el rango máximo es de 366 días")


class OperationsService:
    """Supervisión central local-first; nunca escribe en las fuentes de BC Caja."""

    def __init__(self, core: CentralManagementService):
        self.core, self.repository = core, core.repository

    def summary(self, actor: Principal, period: DateRange):
        self.core._require(actor, "dashboard.read")
        with self.repository.connection() as con:
            rows = con.execute(
                "SELECT * FROM cash_snapshots WHERE business_date BETWEEN ? AND ? ORDER BY unit,business_date DESC,source_updated_at DESC",
                (period.start, period.end),
            ).fetchall()
        alerts = self.alerts(actor, include_closed=False)
        result = []
        for unit in Unit:
            if actor.unit not in (None, unit):
                continue
            unit_rows, seen = [dict(r) for r in rows if r["unit"] == unit.value], set()
            days = [r for r in unit_rows if not (r["business_date"] in seen or seen.add(r["business_date"]))]
            latest = days[0] if days else None
            sync = "SIN_DATOS" if latest is None else self._sync_state(latest)
            result.append({
                "unit": unit, "label": unit.label, "days": len(days),
                "income": sum(r["income"] for r in days), "expenses": sum(r["expenses"] for r in days),
                "withdrawals": sum(r["withdrawals"] for r in days),
                "differences": sum(1 for r in days if r["counted_cash"] is not None and r["counted_cash"] != r["expected_cash"]),
                "sync": sync, "alerts": sum(1 for a in alerts if a["unit"] == unit),
            })
        return result

    def daily(self, actor: Principal, unit: Unit, period: DateRange):
        self.core._require(actor, "dashboard.read", unit)
        with self.repository.connection() as con:
            rows = con.execute(
                "SELECT * FROM cash_snapshots WHERE unit=? AND business_date BETWEEN ? AND ? ORDER BY business_date DESC,source_updated_at DESC",
                (unit.value, period.start, period.end),
            ).fetchall()
        seen, result = set(), []
        for source in rows:
            row = dict(source)
            if row["business_date"] in seen:
                continue
            seen.add(row["business_date"])
            row["sync_state"] = self._sync_state(row)
            row["completeness"] = "INCOMPLETO" if row["status"] == "OPEN" or row["counted_cash"] is None else "COMPLETO"
            row["conflict"] = row["counted_cash"] is not None and row["counted_cash"] != row["expected_cash"]
            result.append(row)
        return result

    @staticmethod
    def _sync_state(row):
        received = datetime.fromisoformat(row["received_at"])
        source = datetime.fromisoformat(row["source_updated_at"])
        if received.tzinfo is None: received = received.replace(tzinfo=timezone.utc)
        if source.tzinfo is None: source = source.replace(tzinfo=timezone.utc)
        return "ATRASADO" if (received - source).total_seconds() > 900 else "SINCRONIZADO"

    def alerts(self, actor: Principal, include_closed=True):
        self.core._require(actor, "dashboard.read")
        with self.repository.connection() as con:
            rows = con.execute("""SELECT a.*,COALESCE(s.state,'PENDIENTE') workflow_state
                FROM central_alerts a LEFT JOIN operational_alert_state s ON s.alert_id=a.id
                ORDER BY a.created_at DESC""").fetchall()
        closed = {"VERIFICADO", "DESCARTADO"}
        return [dict(r) | {"unit": Unit(r["unit"])} for r in rows
                if actor.unit in (None, Unit(r["unit"])) and (include_closed or r["workflow_state"] not in closed)]

    def transition_alert(self, actor: Principal, alert_id: str, target: str, note=""):
        self.core._require(actor, "alerts.manage")
        if target not in ALERT_STATES:
            raise ValueError("estado de alerta inválido")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("""SELECT a.unit,COALESCE(s.state,'PENDIENTE') state
                FROM central_alerts a LEFT JOIN operational_alert_state s ON s.alert_id=a.id WHERE a.id=?""", (alert_id,)).fetchone()
            if not row:
                raise ValueError("alerta inexistente")
            self.core._require(actor, "alerts.manage", Unit(row["unit"]))
            if target not in ALERT_TRANSITIONS[row["state"]]:
                raise ValueError(f"transición inválida: {row['state']} → {target}")
            con.execute("""INSERT INTO operational_alert_state VALUES(?,?,?,?,?)
                ON CONFLICT(alert_id) DO UPDATE SET state=excluded.state,updated_by=excluded.updated_by,updated_at=excluded.updated_at,note=excluded.note""",
                (alert_id, target, actor.username, utc_now().isoformat(), note.strip()))
            self.repository.audit(con, actor.username, "ALERT_TRANSITION", alert_id, details={"from": row["state"], "to": target})
            con.commit()

    def queue_message(self, actor: Principal, unit: Unit, body: str, target_pc: str | None = None):
        self.core._require(actor, "alerts.manage", unit)
        body, target_pc = body.strip(), (target_pc or "").strip() or None
        if not body:
            raise ValueError("mensaje obligatorio")
        payload = {"unit": unit.value, "target_pc": target_pc, "body": body}
        idem = _key(payload)
        message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bc-central:{idem}"))
        now = utc_now().isoformat()
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT OR IGNORE INTO central_messages VALUES(?,?,?,?,?,?,?,?)",
                        (message_id, unit.value, target_pc, body, "PENDIENTE", idem, actor.username, now))
            con.execute("INSERT OR IGNORE INTO central_outbox VALUES(?,?,?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()), "MESSAGE", message_id, "CENTRAL_MESSAGE_QUEUED", _canonical(payload), idem, "PENDING", 0, now))
            self.repository.audit(con, actor.username, "MESSAGE_QUEUED", message_id, details={"unit": unit.value, "target_pc": target_pc, "delivery": "PENDING"})
            con.commit()
        return message_id, idem

    def reviewed_daily_fields(self, actor: Principal, unit: Unit, business_date: str):
        self.core._require(actor, "dashboard.read", unit)
        date.fromisoformat(business_date)
        with self.repository.connection() as con:
            return {row[0] for row in con.execute(
                "SELECT field_name FROM daily_field_reviews WHERE unit=? AND business_date=?",
                (unit.value, business_date),
            )}

    def mark_daily_fields(self, actor: Principal, unit: Unit, business_date: str, fields):
        self.core._require(actor, "reviews.manage", unit)
        date.fromisoformat(business_date)
        fields = tuple(dict.fromkeys(fields))
        if not fields or any(field not in DAILY_REVIEW_FIELDS for field in fields):
            raise ValueError("campos diarios inválidos")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            if not con.execute("SELECT 1 FROM cash_snapshots WHERE unit=? AND business_date=?", (unit.value, business_date)).fetchone():
                raise ValueError("día inexistente")
            for field in fields:
                con.execute("INSERT OR REPLACE INTO daily_field_reviews VALUES(?,?,?,?,?)",
                            (unit.value, business_date, field, actor.username, utc_now().isoformat()))
            self.repository.audit(con, actor.username, "DAILY_FIELDS_REVIEWED", f"{unit.value}:{business_date}", details={"fields": fields})
            con.commit()
        return self.reviewed_daily_fields(actor, unit, business_date)
