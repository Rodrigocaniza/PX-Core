from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .models import Alert, CashSnapshot, Unit


class CentralRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.database_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        try:
            yield con
        finally:
            con.close()

    def migrate(self):
        with self.connection() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS central_users(
              username TEXT PRIMARY KEY COLLATE NOCASE, password_hash TEXT NOT NULL,
              salt TEXT NOT NULL, role TEXT NOT NULL, unit TEXT, active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cash_snapshots(
              event_id TEXT PRIMARY KEY, unit TEXT NOT NULL, business_date TEXT NOT NULL,
              status TEXT NOT NULL, opening_cash INTEGER NOT NULL, income INTEGER NOT NULL,
              cash INTEGER NOT NULL, card_check INTEGER NOT NULL, expenses INTEGER NOT NULL,
              withdrawals INTEGER NOT NULL, expected_cash INTEGER NOT NULL,
              counted_cash INTEGER, entry_count INTEGER NOT NULL,
              source_updated_at TEXT NOT NULL, received_at TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_unit_time ON cash_snapshots(unit, source_updated_at DESC);
            CREATE TABLE IF NOT EXISTS central_alerts(
              id TEXT PRIMARY KEY, unit TEXT NOT NULL, kind TEXT NOT NULL,
              severity TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL,
              created_at TEXT NOT NULL, acknowledged_at TEXT, acknowledged_by TEXT,
              UNIQUE(unit, kind, status)
            );
            CREATE TABLE IF NOT EXISTS central_audit(
              id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL,
              target TEXT NOT NULL, result TEXT NOT NULL, details_json TEXT NOT NULL,
              recorded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS operational_alert_state(
              alert_id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_by TEXT NOT NULL,
              updated_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
              FOREIGN KEY(alert_id) REFERENCES central_alerts(id)
            );
            CREATE TABLE IF NOT EXISTS central_messages(
              id TEXT PRIMARY KEY, target_unit TEXT NOT NULL, target_pc TEXT,
              body TEXT NOT NULL, status TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
              created_by TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS central_outbox(
              id TEXT PRIMARY KEY, aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL,
              event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS daily_field_reviews(
              unit TEXT NOT NULL, business_date TEXT NOT NULL, field_name TEXT NOT NULL,
              reviewed_by TEXT NOT NULL, reviewed_at TEXT NOT NULL,
              PRIMARY KEY(unit,business_date,field_name)
            );
            CREATE TABLE IF NOT EXISTS message_delivery(
              message_id TEXT PRIMARY KEY, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
              last_attempt_at TEXT, next_attempt_at TEXT, delivered_at TEXT, confirmed_at TEXT,
              cancelled_at TEXT, cancelled_by TEXT, cancel_reason TEXT,
              error_code TEXT, error_message TEXT, updated_at TEXT NOT NULL,
              FOREIGN KEY(message_id) REFERENCES central_messages(id)
            );
            CREATE TABLE IF NOT EXISTS message_delivery_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT NOT NULL,
              from_state TEXT, to_state TEXT NOT NULL, actor TEXT NOT NULL,
              details_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
              FOREIGN KEY(message_id) REFERENCES central_messages(id)
            );
            CREATE TABLE IF NOT EXISTS message_receipts(
              receipt_id TEXT PRIMARY KEY, message_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE, receiver TEXT NOT NULL,
              received_at TEXT NOT NULL, payload_json TEXT NOT NULL,
              FOREIGN KEY(message_id) REFERENCES central_messages(id)
            );
            CREATE TABLE IF NOT EXISTS simulated_receiver_inbox(
              idempotency_key TEXT PRIMARY KEY, receipt_id TEXT NOT NULL UNIQUE,
              message_id TEXT NOT NULL, receiver TEXT NOT NULL, received_at TEXT NOT NULL,
              envelope_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_delivery_state_next ON message_delivery(state,next_attempt_at);
            CREATE TABLE IF NOT EXISTS factufacil_sales(
              id TEXT PRIMARY KEY, identity_key TEXT NOT NULL UNIQUE, branch TEXT NOT NULL,
              source_sale_id TEXT NOT NULL, envelope TEXT NOT NULL, status TEXT NOT NULL,
              content_hash TEXT NOT NULL, payload_json TEXT NOT NULL, version INTEGER NOT NULL,
              loaded_by TEXT, loaded_at TEXT, receipt_number TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(branch,envelope)
            );
            CREATE TABLE IF NOT EXISTS factufacil_versions(
              sale_id TEXT NOT NULL, version INTEGER NOT NULL, content_hash TEXT NOT NULL,
              payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
              PRIMARY KEY(sale_id,version), FOREIGN KEY(sale_id) REFERENCES factufacil_sales(id)
            );
            CREATE TABLE IF NOT EXISTS factufacil_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id TEXT NOT NULL,
              from_state TEXT, to_state TEXT NOT NULL, actor TEXT NOT NULL,
              action TEXT NOT NULL, details_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
              FOREIGN KEY(sale_id) REFERENCES factufacil_sales(id)
            );
            CREATE INDEX IF NOT EXISTS idx_factufacil_status_date ON factufacil_sales(status,updated_at);
            CREATE TABLE IF NOT EXISTS commission_sales(
              id TEXT PRIMARY KEY, identity_key TEXT NOT NULL UNIQUE, branch TEXT NOT NULL,
              source_sale_id TEXT NOT NULL, saleswoman TEXT NOT NULL, sale_kind TEXT NOT NULL,
              sale_date TEXT NOT NULL, total_amount INTEGER NOT NULL, paid_amount INTEGER NOT NULL,
              balance_amount INTEGER NOT NULL, cancelled_date TEXT,
              voided INTEGER NOT NULL DEFAULT 0, void_reason TEXT, envelope TEXT NOT NULL DEFAULT '',
              content_hash TEXT NOT NULL, payload_json TEXT NOT NULL, version INTEGER NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(branch,source_sale_id)
            );
            CREATE TABLE IF NOT EXISTS commission_payments(
              id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES commission_sales(id),
              amount INTEGER NOT NULL, payment_date TEXT NOT NULL, kind TEXT NOT NULL,
              reference TEXT NOT NULL DEFAULT '', reverses_id TEXT,
              idempotency_key TEXT NOT NULL UNIQUE, client_key TEXT,
              actor TEXT NOT NULL, recorded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS commission_entries(
              id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES commission_sales(id),
              sequence INTEGER NOT NULL, period TEXT, branch TEXT NOT NULL, saleswoman TEXT NOT NULL,
              sale_kind TEXT NOT NULL, status TEXT NOT NULL,
              gross_amount INTEGER NOT NULL, agreement_discount INTEGER NOT NULL DEFAULT 0,
              commissionable_base INTEGER NOT NULL DEFAULT 0,
              rate_bp INTEGER, commission_amount INTEGER, policy_status TEXT NOT NULL,
              eligible_date TEXT, reviewed_by TEXT, reviewed_at TEXT, approved_by TEXT, approved_at TEXT,
              paid_at TEXT, payment_reference TEXT, observation TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(sale_id,sequence)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_commission_entry_active
              ON commission_entries(sale_id) WHERE status<>'REVERTIDA';
            CREATE UNIQUE INDEX IF NOT EXISTS idx_commission_entry_period
              ON commission_entries(sale_id,period) WHERE period IS NOT NULL AND status<>'REVERTIDA';
            CREATE INDEX IF NOT EXISTS idx_commission_entries_period
              ON commission_entries(period,branch,saleswoman);
            CREATE TABLE IF NOT EXISTS commission_entry_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id TEXT NOT NULL,
              sale_id TEXT NOT NULL, from_state TEXT, to_state TEXT NOT NULL, actor TEXT NOT NULL,
              action TEXT NOT NULL, details_json TEXT NOT NULL, recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_commission_history_entry ON commission_entry_history(entry_id,id);
            CREATE TABLE IF NOT EXISTS commission_policies(
              id TEXT PRIMARY KEY, scope TEXT NOT NULL, scope_value TEXT NOT NULL DEFAULT '',
              rate_bp INTEGER NOT NULL, approval_status TEXT NOT NULL,
              created_by TEXT NOT NULL, created_at TEXT NOT NULL,
              UNIQUE(scope,scope_value)
            );
            """)
            self._add_missing_columns(con)
            con.commit()

    @staticmethod
    def _add_missing_columns(con):
        """Migración aditiva idempotente para bases de pilotos ya creadas."""
        additions = (("commission_payments", "client_key", "TEXT"),)
        for table, column, kind in additions:
            existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_commission_payments_client_key"
                    " ON commission_payments(client_key)")

    def audit(self, con, actor, action, target, result="SUCCESS", details=None):
        con.execute(
            "INSERT INTO central_audit(actor,action,target,result,details_json,recorded_at) VALUES(?,?,?,?,?,?)",
            (actor, action, target, result, json.dumps(details or {}, ensure_ascii=False, sort_keys=True), datetime.now().astimezone().isoformat()),
        )

    def latest_snapshots(self) -> dict[Unit, sqlite3.Row]:
        with self.connection() as con:
            rows = con.execute("""
              SELECT s.* FROM cash_snapshots s JOIN (
                SELECT unit, MAX(source_updated_at) newest FROM cash_snapshots GROUP BY unit
              ) x ON x.unit=s.unit AND x.newest=s.source_updated_at
            """).fetchall()
        return {Unit(row["unit"]): row for row in rows}

    def alerts(self, active_only=True) -> list[Alert]:
        query = "SELECT * FROM central_alerts" + (" WHERE status='ACTIVE'" if active_only else "") + " ORDER BY created_at DESC"
        with self.connection() as con:
            rows = con.execute(query).fetchall()
        return [Alert(row["id"], Unit(row["unit"]), row["kind"], row["severity"], row["message"], row["status"], datetime.fromisoformat(row["created_at"]), row["acknowledged_by"]) for row in rows]

    def audit_log(self, limit=200):
        with self.connection() as con:
            return [dict(row) for row in con.execute("SELECT * FROM central_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
