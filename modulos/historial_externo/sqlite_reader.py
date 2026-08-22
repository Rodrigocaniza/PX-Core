"""Lectura del estado canónico de BC Caja mediante SQLite ``mode=ro``."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from .history import HistoryEvent, HistoryQuery, PersonHistory

def _text(value) -> str:
    return str(value or "").strip()

def _unique(values) -> tuple[str, ...]:
    result, seen = [], set()
    for value in values:
        clean = _text(value)
        if clean and clean.casefold() not in seen:
            seen.add(clean.casefold())
            result.append(clean)
    return tuple(result)

class SQLiteHistoryReader:
    """Consulta sin migrar, crear ni modificar la base productiva."""
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        if not self.database_path.is_file():
            raise FileNotFoundError(f"No existe la base de BC Caja: {self.database_path}")
        connection = sqlite3.connect(self.database_path.resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    @staticmethod
    def _has_table(connection, name: str) -> bool:
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

    def search(self, query: HistoryQuery, *, limit: int = 200,
               branch: str = "") -> PersonHistory:
        query = query.cleaned()
        if not query.has_terms:
            return PersonHistory()
        limit = max(1, min(int(limit), 1000))
        with self._connect() as connection:
            sales = self._sales(connection, query, limit, branch)
            sale_ids = [row["id"] for row in sales]
            names = _unique(row["description"] for row in sales)
            documents = _unique(row["customer_document"] for row in sales)
            phones = _unique(row["customer_phone"] for row in sales)
            events = [self._sale_event(connection, row) for row in sales]
            documents_by_entry = {row["id"]: _text(row["customer_document"]) for row in sales}
            jobs = self._jobs(connection, query, sale_ids, limit, branch)
            events.extend(self._job_event(
                connection, row, documents_by_entry.get(_text(row["cash_entry_id"]), ""))
                for row in jobs)
            names = _unique((*names, *(row["customer_name"] for row in jobs)))
            phones = _unique((*phones, *(row["customer_phone"] for row in jobs)))
        events.sort(key=lambda event: event.occurred_at or "", reverse=True)
        return PersonHistory(names[0] if names else query.name,
                             documents or ((query.document,) if query.document else ()),
                             phones or ((query.phone,) if query.phone else ()), tuple(events[:limit]))

    @staticmethod
    def _sales(connection, query, limit, branch=""):
        clauses, params = [], []
        normalized_document = "".join(character for character in query.document.upper()
                                      if character.isalnum())
        if len(normalized_document) >= 5:
            clauses.append("upper(replace(replace(replace(COALESCE(ce.customer_document,''),"
                           "'.',''),'-',''),' ','')) = ?")
            params.append(normalized_document)
        else:
            for column, value in (("ce.description", query.name),
                                  ("ce.customer_phone", query.phone),
                                  ("ce.envelope", query.envelope)):
                if value:
                    clauses.append(f"lower(COALESCE({column}, '')) LIKE lower(?)")
                    params.append(f"%{value}%")
        if not clauses:
            return []
        branch_clause = ""
        if _text(branch):
            branch_clause = " AND upper(trim(COALESCE(cd.unit,''))) = upper(trim(?))"
            params.append(_text(branch))
        return connection.execute(f"""SELECT ce.*, cd.business_date, cd.unit
            FROM cash_entries ce JOIN cash_days cd ON cd.id=ce.cash_day_id
            WHERE ({' OR '.join(clauses)}){branch_clause}
            ORDER BY COALESCE(ce.updated_at, ce.created_at, cd.business_date) DESC LIMIT ?""",
                                  (*params, limit)).fetchall()

    def _sale_event(self, connection, row):
        items, prescriptions = (), ()
        if self._has_table(connection, "sale_items"):
            rows = connection.execute(
                "SELECT * FROM sale_items WHERE cash_entry_id=? ORDER BY position", (row["id"],)).fetchall()
            items = tuple(" · ".join(filter(None, (_text(item["description"]), _text(item["code"]),
                                                    _text(item["laboratory"])))) for item in rows)
            prescriptions = _unique(item["prescription_doctor"] for item in rows)
        trace = []
        if self._has_table(connection, "cash_entry_revisions"):
            for revision in connection.execute(
                    "SELECT * FROM cash_entry_revisions WHERE entry_id=? ORDER BY revision DESC",
                    (row["id"],)):
                detail = ""
                try:
                    snapshot = json.loads(revision["snapshot_json"] or "{}")
                    detail = _text(snapshot.get("void_reason") or snapshot.get("observations"))
                except (TypeError, ValueError):
                    pass
                trace.append(" · ".join(filter(None, (revision["recorded_at"], revision["action"],
                                                        f"rev. {revision['revision']}", detail))))
        return HistoryEvent(
            _text(row["updated_at"] or row["created_at"] or row["business_date"]), "VENTA",
            _text(row["unit"]), _text(row["envelope"]),
            _text(row["saleswoman"] or row["performed_by"]), _text(row["status"]), row["total"],
            row["cash"], row["card_check"], row["agreement_amount"], _text(row["balance_text"]),
            _text(row["description"]), items,
            prescriptions or ((_text(row["prescription_doctor"]),) if _text(row["prescription_doctor"]) else ()),
            _text(row["observations"]), tuple(trace),
            _text(row["customer_document"]), _text(row["customer_phone"]),
            _text(row["description"]), _text(row["id"]))

    def _jobs(self, connection, query, sale_ids, limit, branch=""):
        if not self._has_table(connection, "service_jobs"):
            return []
        clauses, params = [], []
        for column, value in (("customer_name", query.name), ("customer_phone", query.phone),
                              ("reference", query.envelope)):
            if value:
                clauses.append(f"lower(COALESCE({column}, '')) LIKE lower(?)")
                params.append(f"%{value}%")
        if sale_ids:
            clauses.append("cash_entry_id IN (%s)" % ",".join("?" * len(sale_ids)))
            params.extend(sale_ids)
        if not clauses:
            return []
        branch_clause = ""
        if _text(branch):
            branch_clause = " AND upper(trim(COALESCE(branch,''))) = upper(trim(?))"
            params.append(_text(branch))
        return connection.execute(f"SELECT * FROM service_jobs WHERE ({' OR '.join(clauses)})"
                                  f"{branch_clause} ORDER BY updated_at DESC LIMIT ?",
                                  (*params, limit)).fetchall()

    def _job_event(self, connection, row, identity_document=""):
        trace = []
        if self._has_table(connection, "service_job_events"):
            trace = [" · ".join(filter(None, (event["occurred_at"], event["event_type"],
                                               event["actor"], event["reason"])))
                     for event in connection.execute(
                         "SELECT * FROM service_job_events WHERE job_id=? ORDER BY sequence DESC", (row["id"],))]
        return HistoryEvent(_text(row["updated_at"] or row["received_at"]), "TRABAJO",
                            _text(row["branch"]), _text(row["reference"]), _text(row["received_by"]),
                            _text(row["status"]), row["charged_amount"], description=" · ".join(filter(None, (
                                _text(row["job_type"]), _text(row["description"]), _text(row["responsible"])))),
                            observations=_text(row["observations"]), trace=tuple(trace),
                            identity_document=_text(identity_document),
                            identity_phone=_text(row["customer_phone"]),
                            identity_name=_text(row["customer_name"]),
                            source_reference=_text(row["id"]))
