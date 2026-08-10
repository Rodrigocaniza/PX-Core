"""Repositorio SQLite transaccional de BC Caja."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Sequence

from ..domain.models import (
    CashCount,
    CashCountStatus,
    CashDay,
    CashDayStatus,
    CashEntry,
    CashEntryStatus,
    CashTotals,
)


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteCashDayRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        if self.database_path != Path(":memory:"):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._memory_connection: sqlite3.Connection | None = None
        if str(database_path) == ":memory:":
            self._memory_connection = self._new_connection()
        self.migrate()

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA synchronous = FULL")
        if self.database_path != Path(":memory:"):
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._memory_connection or self._new_connection()
        try:
            yield connection
        finally:
            if self._memory_connection is None:
                connection.close()

    def close(self) -> None:
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None

    def integrity_check(self) -> None:
        with self._connection() as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()[0]
        if result != "ok":
            raise sqlite3.DatabaseError(f"SQLite quick_check falló: {result}")

    def backup_to(self, destination: str | Path) -> Path:
        target_path = Path(destination)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as source:
            target = sqlite3.connect(str(target_path))
            try:
                source.backup(target)
                target.commit()
            finally:
                target.close()
        return target_path

    def migrate(self) -> None:
        with self._connection() as connection:
            for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = migration.stem.split("_", 1)[0]
                applied = connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
                ).fetchone() if self._table_exists(connection, "schema_migrations") else None
                if applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, datetime.now().astimezone().isoformat()),
                )
                connection.commit()

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone() is not None

    def save(self, cash_day: CashDay) -> None:
        totals = cash_day.closing_totals
        values = (
            cash_day.id, cash_day.business_date.isoformat(), cash_day.unit, cash_day.opening_cash,
            cash_day.status.value, _iso(cash_day.opened_at), _iso(cash_day.closed_at),
            totals.total if totals else None, totals.cash if totals else None,
            totals.card_check if totals else None, totals.expenses if totals else None,
            totals.expected_cash if totals else None, totals.entry_count if totals else None,
            cash_day.version,
        )
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """INSERT INTO cash_days(
                        id,business_date,unit,opening_cash,status,opened_at,closed_at,
                        closing_total,closing_cash,closing_card_check,closing_expenses,
                        closing_expected_cash,closing_entry_count,version
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        business_date=excluded.business_date, unit=excluded.unit,
                        opening_cash=excluded.opening_cash, status=excluded.status,
                        opened_at=excluded.opened_at, closed_at=excluded.closed_at,
                        closing_total=excluded.closing_total, closing_cash=excluded.closing_cash,
                        closing_card_check=excluded.closing_card_check,
                        closing_expenses=excluded.closing_expenses,
                        closing_expected_cash=excluded.closing_expected_cash,
                        closing_entry_count=excluded.closing_entry_count, version=excluded.version""",
                    values,
                )
                existing_entries = {
                    row["id"]: row
                    for row in connection.execute(
                        "SELECT * FROM cash_entries WHERE cash_day_id = ?", (cash_day.id,)
                    ).fetchall()
                }
                self._record_entry_revisions(connection, cash_day.entries, existing_entries)
                connection.execute("DELETE FROM cash_entries WHERE cash_day_id = ?", (cash_day.id,))
                connection.executemany(
                    """INSERT INTO cash_entries(
                        id,cash_day_id,description,envelope,frame_origin,code,frame,lens,laboratory,
                        prescription_doctor,total,cash,card_check,orders_text,installments_text,
                        balance_text,expenses,origin,source_reference,created_at,updated_at,
                        status,voided_at,void_reason,revision
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [self._entry_values(entry) for entry in cash_day.entries],
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _entry_values(entry: CashEntry) -> tuple:
        return (
            entry.id, entry.cash_day_id, entry.description, entry.envelope, entry.frame_origin,
            entry.code, entry.frame, entry.lens, entry.laboratory, entry.prescription_doctor, entry.total,
            entry.cash, entry.card_check, entry.orders, entry.installments, entry.balance,
            entry.expenses, entry.origin, entry.source_reference, _iso(entry.created_at),
            _iso(entry.updated_at), entry.status.value, _iso(entry.voided_at),
            entry.void_reason, entry.revision,
        )

    @classmethod
    def _record_entry_revisions(
        cls,
        connection: sqlite3.Connection,
        entries: Sequence[CashEntry],
        existing_entries: dict[str, sqlite3.Row],
    ) -> None:
        for entry in entries:
            existing = existing_entries.get(entry.id)
            if existing is not None and entry.revision <= existing["revision"]:
                continue
            action = "CREATE" if existing is None else (
                "VOID" if entry.status is CashEntryStatus.VOIDED else "UPDATE"
            )
            connection.execute(
                """INSERT INTO cash_entry_revisions(
                    entry_id,cash_day_id,revision,action,snapshot_json,recorded_at
                ) VALUES (?,?,?,?,?,?)""",
                (
                    entry.id,
                    entry.cash_day_id,
                    entry.revision,
                    action,
                    json.dumps(cls._entry_snapshot(entry), ensure_ascii=False, sort_keys=True),
                    _iso(entry.updated_at),
                ),
            )

    @staticmethod
    def _entry_snapshot(entry: CashEntry) -> dict:
        return {
            "id": entry.id,
            "cash_day_id": entry.cash_day_id,
            "description": entry.description,
            "envelope": entry.envelope,
            "frame_origin": entry.frame_origin,
            "code": entry.code,
            "frame": entry.frame,
            "lens": entry.lens,
            "laboratory": entry.laboratory,
            "prescription_doctor": entry.prescription_doctor,
            "total": entry.total,
            "cash": entry.cash,
            "card_check": entry.card_check,
            "orders": entry.orders,
            "installments": entry.installments,
            "balance": entry.balance,
            "expenses": entry.expenses,
            "origin": entry.origin,
            "source_reference": entry.source_reference,
            "status": entry.status.value,
            "voided_at": _iso(entry.voided_at),
            "void_reason": entry.void_reason,
            "revision": entry.revision,
        }

    def get(self, cash_day_id: str) -> CashDay | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM cash_days WHERE id = ?", (cash_day_id,)).fetchone()
            return self._hydrate(connection, row) if row else None

    def get_by_date_and_unit(self, business_date: date, unit: str) -> CashDay | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM cash_days WHERE business_date = ? AND unit = ?",
                (business_date.isoformat(), unit.strip().upper()),
            ).fetchone()
            return self._hydrate(connection, row) if row else None

    def list_between(self, start_date: date, end_date: date, unit: str | None = None) -> Sequence[CashDay]:
        query = "SELECT * FROM cash_days WHERE business_date BETWEEN ? AND ?"
        params: list[str] = [start_date.isoformat(), end_date.isoformat()]
        if unit:
            query += " AND unit = ?"
            params.append(unit.strip().upper())
        query += " ORDER BY business_date, unit"
        with self._connection() as connection:
            return [self._hydrate(connection, row) for row in connection.execute(query, params).fetchall()]

    def get_latest_closed_before(self, business_date: date, unit: str) -> CashDay | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT * FROM cash_days
                   WHERE business_date < ? AND unit = ? AND status = 'CLOSED'
                   ORDER BY business_date DESC LIMIT 1""",
                (business_date.isoformat(), unit.strip().upper()),
            ).fetchone()
            return self._hydrate(connection, row) if row else None

    def _hydrate(self, connection: sqlite3.Connection, row: sqlite3.Row) -> CashDay:
        entry_rows = connection.execute(
            "SELECT * FROM cash_entries WHERE cash_day_id = ? ORDER BY rowid", (row["id"],)
        ).fetchall()
        entries = [CashEntry(
            id=item["id"], cash_day_id=item["cash_day_id"], description=item["description"],
            envelope=item["envelope"], frame_origin=item["frame_origin"], code=item["code"],
            frame=item["frame"], lens=item["lens"], laboratory=item["laboratory"],
            prescription_doctor=item["prescription_doctor"],
            total=item["total"], cash=item["cash"], card_check=item["card_check"],
            orders=item["orders_text"], installments=item["installments_text"],
            balance=item["balance_text"], expenses=item["expenses"], origin=item["origin"],
            source_reference=item["source_reference"], created_at=_datetime(item["created_at"]),
            updated_at=_datetime(item["updated_at"]), status=item["status"],
            voided_at=_datetime(item["voided_at"]), void_reason=item["void_reason"],
            revision=item["revision"],
        ) for item in entry_rows]
        closing_totals = None
        if row["status"] == CashDayStatus.CLOSED.value:
            closing_totals = CashTotals(
                row["closing_total"], row["closing_cash"], row["closing_card_check"],
                row["closing_expenses"], row["closing_expected_cash"], row["closing_entry_count"],
            )
        return CashDay(
            id=row["id"], business_date=row["business_date"], unit=row["unit"],
            opening_cash=row["opening_cash"], status=row["status"], entries=entries,
            opened_at=_datetime(row["opened_at"]), closed_at=_datetime(row["closed_at"]),
            closing_totals=closing_totals, version=row["version"],
        )

    def save_cash_count(self, cash_count: CashCount) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO cash_counts(
                    id,cash_day_id,quantities_json,counted_total,expected_total,difference,status,recorded_at
                ) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    cash_count.id, cash_count.cash_day_id,
                    json.dumps(dict(cash_count.quantities), sort_keys=True), cash_count.counted_total,
                    cash_count.expected_total, cash_count.difference, cash_count.status.value,
                    _iso(cash_count.recorded_at),
                ),
            )
            connection.commit()

    def get_latest_cash_count(self, cash_day_id: str) -> CashCount | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM cash_counts WHERE cash_day_id = ? ORDER BY recorded_at DESC, rowid DESC LIMIT 1",
                (cash_day_id,),
            ).fetchone()
        if row is None:
            return None
        return CashCount(
            id=row["id"], cash_day_id=row["cash_day_id"],
            quantities={int(k): int(v) for k, v in json.loads(row["quantities_json"]).items()},
            counted_total=row["counted_total"], expected_total=row["expected_total"],
            difference=row["difference"], status=CashCountStatus(row["status"]),
            recorded_at=_datetime(row["recorded_at"]),
        )

    def list_entry_revisions(self, entry_id: str) -> Sequence[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT revision,action,snapshot_json,recorded_at
                FROM cash_entry_revisions WHERE entry_id = ? ORDER BY revision""",
                (entry_id,),
            ).fetchall()
        return [
            {
                "revision": row["revision"],
                "action": row["action"],
                "snapshot": json.loads(row["snapshot_json"]),
                "recorded_at": row["recorded_at"],
            }
            for row in rows
        ]
