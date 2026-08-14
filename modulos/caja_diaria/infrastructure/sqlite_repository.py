"""Repositorio SQLite transaccional de BC Caja."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Sequence

from ..domain.errors import InvalidCashDayError

from ..domain.models import (
    CashCount,
    CashCountStatus,
    CashDay,
    CashDayStatus,
    CashEntry,
    CashEntryStatus,
    CashTotals,
    Order,
    OrderStatus,
    SaleItem,
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

    def save(
        self, cash_day: CashDay, *, audit_reason: str = "", edited_by: str = ""
    ) -> None:
        stage = "cash_day_upsert"
        totals = cash_day.closing_totals
        values = (
            cash_day.id, cash_day.business_date.isoformat(), cash_day.unit, cash_day.opening_cash,
            cash_day.status.value, _iso(cash_day.opened_at), _iso(cash_day.closed_at),
            totals.total if totals else None, totals.cash if totals else None,
            totals.card_check if totals else None, totals.expenses if totals else None,
            totals.expected_cash if totals else None, totals.entry_count if totals else None,
            cash_day.session_duration_seconds,
            None if cash_day.overtime_triggered is None else int(cash_day.overtime_triggered),
            cash_day.overtime_minutes,
            cash_day.version,
            cash_day.initial_cash_expected, cash_day.initial_cash_difference,
            cash_day.initial_cash_source_day_id, cash_day.opened_by,
            totals.withdrawals if totals else None,
            cash_day.initial_cash_source_kind, cash_day.initial_cash_source_count_id,
        )
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """INSERT INTO cash_days(
                        id,business_date,unit,opening_cash,status,opened_at,closed_at,
                        closing_total,closing_cash,closing_card_check,closing_expenses,
                        closing_expected_cash,closing_entry_count,session_duration_seconds,
                        overtime_triggered,overtime_minutes,version,
                        initial_cash_expected,initial_cash_difference,
                        initial_cash_source_day_id,opened_by,closing_withdrawals,
                        initial_cash_source_kind,initial_cash_source_count_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        business_date=excluded.business_date, unit=excluded.unit,
                        opening_cash=excluded.opening_cash, status=excluded.status,
                        opened_at=excluded.opened_at, closed_at=excluded.closed_at,
                        closing_total=excluded.closing_total, closing_cash=excluded.closing_cash,
                        closing_card_check=excluded.closing_card_check,
                        closing_expenses=excluded.closing_expenses,
                        closing_expected_cash=excluded.closing_expected_cash,
                        closing_entry_count=excluded.closing_entry_count,
                        session_duration_seconds=excluded.session_duration_seconds,
                        overtime_triggered=excluded.overtime_triggered,
                        overtime_minutes=excluded.overtime_minutes, version=excluded.version,
                        initial_cash_expected=excluded.initial_cash_expected,
                        initial_cash_difference=excluded.initial_cash_difference,
                        initial_cash_source_day_id=excluded.initial_cash_source_day_id,
                        opened_by=excluded.opened_by,
                        closing_withdrawals=excluded.closing_withdrawals,
                        initial_cash_source_kind=excluded.initial_cash_source_kind,
                        initial_cash_source_count_id=excluded.initial_cash_source_count_id""",
                    values,
                )
                existing_entries = {
                    row["id"]: row
                    for row in connection.execute(
                        "SELECT * FROM cash_entries WHERE cash_day_id = ?", (cash_day.id,)
                    ).fetchall()
                }
                stage = "entry_audit"
                self._record_entry_revisions(
                    connection, cash_day.entries, existing_entries,
                    audit_reason=audit_reason, edited_by=edited_by,
                )
                stage = "cash_entry_upsert"
                connection.executemany(
                    """INSERT INTO cash_entries(
                        id,cash_day_id,description,envelope,frame_origin,code,frame,lens,laboratory,
                        prescription_doctor,total,cash,card_check,orders_text,installments_text,
                        balance_text,expenses,origin,source_reference,customer_document,
                        saleswoman,delivery_date,observations,customer_phone,created_at,updated_at,
                        status,voided_at,void_reason,revision,withdrawal,
                        withdrawal_destination,performed_by,agreement_amount,outflow_type
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        cash_day_id=excluded.cash_day_id, description=excluded.description,
                        envelope=excluded.envelope, frame_origin=excluded.frame_origin,
                        code=excluded.code, frame=excluded.frame, lens=excluded.lens,
                        laboratory=excluded.laboratory,
                        prescription_doctor=excluded.prescription_doctor,
                        total=excluded.total, cash=excluded.cash,
                        card_check=excluded.card_check, orders_text=excluded.orders_text,
                        installments_text=excluded.installments_text,
                        balance_text=excluded.balance_text, expenses=excluded.expenses,
                        origin=excluded.origin, source_reference=excluded.source_reference,
                        customer_document=excluded.customer_document,
                        saleswoman=excluded.saleswoman, delivery_date=excluded.delivery_date,
                        observations=excluded.observations,
                        customer_phone=excluded.customer_phone,
                        updated_at=excluded.updated_at, status=excluded.status,
                        voided_at=excluded.voided_at, void_reason=excluded.void_reason,
                        revision=excluded.revision, withdrawal=excluded.withdrawal,
                        withdrawal_destination=excluded.withdrawal_destination,
                        performed_by=excluded.performed_by,
                        agreement_amount=excluded.agreement_amount,
                        outflow_type=excluded.outflow_type""",
                    [self._entry_values(entry) for entry in cash_day.entries],
                )
                stage = "sale_items_refresh"
                connection.executemany(
                    "DELETE FROM sale_items WHERE cash_entry_id = ?",
                    [(entry.id,) for entry in cash_day.entries],
                )
                connection.executemany(
                    """INSERT INTO sale_items(
                        id,cash_entry_id,position,description,code,item_type,frame_price,
                        lens_price,laboratory,prescription_doctor,frame_discount_percent,
                        lens_discount_percent,frame_final_price,lens_final_price,no_cost
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [
                        (
                            item.id, entry.id, position, item.description, item.code,
                            item.item_type, item.frame_price, item.lens_price,
                            item.laboratory, item.prescription_doctor,
                            item.frame_discount_percent, item.lens_discount_percent,
                            item.frame_final_price, item.lens_final_price, int(item.no_cost),
                        )
                        for entry in cash_day.entries
                        for position, item in enumerate(entry.items)
                    ],
                )
                connection.commit()
            except Exception as error:
                connection.rollback()
                if isinstance(error, sqlite3.Error):
                    self._log_sqlite_failure(error, stage=stage, cash_day_id=cash_day.id)
                raise

    def _log_sqlite_failure(self, error: sqlite3.Error, *, stage: str, cash_day_id: str) -> None:
        """Registra diagnóstico técnico local sin exponer SQL a la operadora."""
        try:
            log_dir = self.database_path.parent / "Logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            logger = logging.getLogger(f"bc-caja-sqlite-{self.database_path}")
            logger.setLevel(logging.ERROR)
            handler = logging.FileHandler(log_dir / "sqlite-errors.log", encoding="utf-8")
            try:
                logger.addHandler(handler)
                logger.error(
                    "sqlite save failed stage=%s cash_day_id=%s class=%s code=%s name=%s detail=%s",
                    stage, cash_day_id, type(error).__name__,
                    getattr(error, "sqlite_errorcode", None),
                    getattr(error, "sqlite_errorname", None), str(error),
                )
            finally:
                logger.removeHandler(handler)
                handler.close()
        except OSError:
            pass

    @staticmethod
    def _entry_values(entry: CashEntry) -> tuple:
        return (
            entry.id, entry.cash_day_id, entry.description, entry.envelope, entry.frame_origin,
            entry.code, entry.frame, entry.lens, entry.laboratory, entry.prescription_doctor, entry.total,
            entry.cash, entry.card_check, entry.orders, entry.installments, entry.balance,
            entry.expenses, entry.origin, entry.source_reference, entry.customer_document,
            entry.saleswoman, _iso(entry.delivery_date), entry.observations, entry.customer_phone, _iso(entry.created_at),
            _iso(entry.updated_at), entry.status.value, _iso(entry.voided_at),
            entry.void_reason, entry.revision,
            entry.withdrawal, entry.withdrawal_destination, entry.performed_by,
            entry.agreement_amount or 0, entry.outflow_type,
        )

    @classmethod
    def _record_entry_revisions(
        cls,
        connection: sqlite3.Connection,
        entries: Sequence[CashEntry],
        existing_entries: dict[str, sqlite3.Row],
        *, audit_reason: str = "", edited_by: str = "",
    ) -> None:
        for entry in entries:
            existing = existing_entries.get(entry.id)
            if existing is not None and entry.revision <= existing["revision"]:
                continue
            action = "CREATE" if existing is None else (
                "VOID" if entry.status is CashEntryStatus.VOIDED else "UPDATE"
            )
            snapshot = cls._entry_snapshot(entry)
            snapshot["audit"] = {
                "reason": str(audit_reason or "").strip(),
                "user": str(edited_by or "").strip(),
            }
            previous = connection.execute(
                """SELECT snapshot_json FROM cash_entry_revisions
                   WHERE entry_id = ? ORDER BY revision DESC LIMIT 1""",
                (entry.id,),
            ).fetchone()
            if previous is not None and action == "UPDATE":
                before = json.loads(previous["snapshot_json"])
                snapshot["item_changes"] = cls._item_changes(
                    before.get("items", []), snapshot.get("items", [])
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
                    json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                    _iso(entry.updated_at),
                ),
            )

    @staticmethod
    def _item_changes(before: Sequence[dict], after: Sequence[dict]) -> dict:
        previous = {item["id"]: item for item in before}
        current = {item["id"]: item for item in after}
        return {
            "added": [current[item_id] for item_id in current.keys() - previous.keys()],
            "removed": [previous[item_id] for item_id in previous.keys() - current.keys()],
            "modified": [
                {"before": previous[item_id], "after": current[item_id]}
                for item_id in previous.keys() & current.keys()
                if previous[item_id] != current[item_id]
            ],
        }
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
            "agreement_amount": entry.agreement_amount,
            "installments": entry.installments,
            "balance": entry.balance,
            "expenses": entry.expenses,
            "withdrawal": entry.withdrawal,
            "withdrawal_destination": entry.withdrawal_destination,
            "performed_by": entry.performed_by,
            "outflow_type": entry.outflow_type,
            "origin": entry.origin,
            "source_reference": entry.source_reference,
            "customer_document": entry.customer_document,
            "customer_phone": entry.customer_phone,
            "saleswoman": entry.saleswoman,
            "delivery_date": _iso(entry.delivery_date),
            "observations": entry.observations,
            "items": [
                {
                    "id": item.id, "description": item.description, "code": item.code,
                    "item_type": item.item_type, "frame_price": item.frame_price,
                    "lens_price": item.lens_price, "laboratory": item.laboratory,
                    "prescription_doctor": item.prescription_doctor,
                    "frame_original_price": item.frame_price,
                    "lens_original_price": item.lens_price,
                    "frame_discount_percent": item.frame_discount_percent,
                    "lens_discount_percent": item.lens_discount_percent,
                    "frame_final_price": item.frame_final_price,
                    "lens_final_price": item.lens_final_price,
                    "no_cost": item.no_cost,
                }
                for item in entry.items
            ],
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
        item_rows = connection.execute(
            "SELECT * FROM sale_items WHERE cash_entry_id IN (SELECT id FROM cash_entries WHERE cash_day_id = ?) ORDER BY cash_entry_id, position",
            (row["id"],),
        ).fetchall()
        items_by_entry: dict[str, list[SaleItem]] = {}
        for item in item_rows:
            items_by_entry.setdefault(item["cash_entry_id"], []).append(SaleItem(
                id=item["id"], description=item["description"], code=item["code"],
                item_type=item["item_type"], frame_price=item["frame_price"],
                lens_price=item["lens_price"], laboratory=item["laboratory"],
                prescription_doctor=item["prescription_doctor"],
                frame_discount_percent=item["frame_discount_percent"],
                lens_discount_percent=item["lens_discount_percent"],
                no_cost=bool(item["no_cost"]),
            ))
        entries = [CashEntry(
            id=item["id"], cash_day_id=item["cash_day_id"], description=item["description"],
            envelope=item["envelope"], frame_origin=item["frame_origin"], code=item["code"],
            frame=item["frame"], lens=item["lens"], laboratory=item["laboratory"],
            prescription_doctor=item["prescription_doctor"],
            total=item["total"], cash=item["cash"], card_check=item["card_check"],
            orders=item["orders_text"], agreement_amount=item["agreement_amount"],
            installments=item["installments_text"],
            balance=item["balance_text"], expenses=item["expenses"], origin=item["origin"],
            withdrawal=item["withdrawal"], withdrawal_destination=item["withdrawal_destination"],
            performed_by=item["performed_by"],
            outflow_type=item["outflow_type"],
            source_reference=item["source_reference"], created_at=_datetime(item["created_at"]),
            customer_document=item["customer_document"], saleswoman=item["saleswoman"],
            customer_phone=item["customer_phone"],
            delivery_date=item["delivery_date"], observations=item["observations"],
            items=tuple(items_by_entry.get(item["id"], ())),
            updated_at=_datetime(item["updated_at"]), status=item["status"],
            voided_at=_datetime(item["voided_at"]), void_reason=item["void_reason"],
            revision=item["revision"],
        ) for item in entry_rows]
        closing_totals = None
        if row["status"] == CashDayStatus.CLOSED.value:
            closing_totals = CashTotals(
                total=row["closing_total"], cash=row["closing_cash"],
                card_check=row["closing_card_check"], expenses=row["closing_expenses"],
                expected_cash=row["closing_expected_cash"], entry_count=row["closing_entry_count"],
                withdrawals=row["closing_withdrawals"] or 0,
            )
        return CashDay(
            id=row["id"], business_date=row["business_date"], unit=row["unit"],
            opening_cash=row["opening_cash"], status=row["status"], entries=entries,
            initial_cash_expected=row["initial_cash_expected"],
            initial_cash_difference=row["initial_cash_difference"],
            initial_cash_source_day_id=row["initial_cash_source_day_id"],
            opened_by=row["opened_by"],
            initial_cash_source_kind=row["initial_cash_source_kind"],
            initial_cash_source_count_id=row["initial_cash_source_count_id"],
            opened_at=_datetime(row["opened_at"]), closed_at=_datetime(row["closed_at"]),
            closing_totals=closing_totals,
            session_duration_seconds=row["session_duration_seconds"],
            overtime_triggered=(
                None if row["overtime_triggered"] is None else bool(row["overtime_triggered"])
            ),
            overtime_minutes=row["overtime_minutes"], version=row["version"],
        )

    def correct_opening_cash(
        self, cash_day_id: str, new_value: int, reason: str, user: str
    ) -> CashDay:
        normalized_reason = str(reason or "").strip()
        normalized_user = str(user or "").strip()
        if not normalized_reason or not normalized_user:
            raise InvalidCashDayError("motivo y usuario son obligatorios para corregir la caja")
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT opening_cash, unit FROM cash_days WHERE id = ?", (cash_day_id,)
                ).fetchone()
                if row is None:
                    raise InvalidCashDayError("caja inexistente")
                old_value = int(row["opening_cash"])
                if old_value == new_value:
                    raise InvalidCashDayError("el nuevo valor debe ser diferente")
                now = datetime.now().astimezone().isoformat()
                connection.execute(
                    """INSERT INTO cash_day_corrections(
                        cash_day_id,unit,field_name,old_value,new_value,reason,corrected_by,corrected_at
                    ) VALUES (?,?,?,?,?,?,?,?)""",
                    (cash_day_id, row["unit"], "opening_cash", str(old_value), str(new_value),
                     normalized_reason, normalized_user, now),
                )
                connection.execute(
                    """UPDATE cash_days SET opening_cash = ?,
                       initial_cash_difference = CASE WHEN initial_cash_expected IS NULL THEN NULL
                           ELSE ? - initial_cash_expected END,
                       closing_expected_cash = CASE WHEN closing_expected_cash IS NULL THEN NULL
                           ELSE closing_expected_cash + (? - opening_cash) END,
                       version = version + 1 WHERE id = ?""",
                    (new_value, new_value, new_value, cash_day_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        result = self.get(cash_day_id)
        assert result is not None
        return result

    def list_day_corrections(self, cash_day_id: str):
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM cash_day_corrections WHERE cash_day_id = ? ORDER BY id",
                (cash_day_id,),
            ).fetchall()]

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

    @staticmethod
    def _hydrate_order(row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"], origin=row["origin"], source_reference=row["source_reference"],
            delivery_date=row["delivery_date"], branch=row["branch"],
            customer_name=row["customer_name"], customer_document=row["customer_document"],
            customer_phone=row["customer_phone"],
            envelope=row["envelope"], saleswoman=row["saleswoman"], status=row["status"],
            observations=row["observations"], cash_entry_id=row["cash_entry_id"],
            created_at=_datetime(row["created_at"]), updated_at=_datetime(row["updated_at"]),
        )

    def save_order(self, order: Order) -> Order:
        """Persiste un pedido; cash_entry_id hace idempotente el origen CAJA."""
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO orders(
                    id,origin,source_reference,delivery_date,branch,customer_name,
                    customer_document,customer_phone,envelope,saleswoman,status,observations,
                    cash_entry_id,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(cash_entry_id) WHERE cash_entry_id IS NOT NULL DO UPDATE SET
                    delivery_date=excluded.delivery_date, branch=excluded.branch,
                    customer_name=excluded.customer_name,
                    customer_document=excluded.customer_document,
                    customer_phone=excluded.customer_phone, envelope=excluded.envelope,
                    saleswoman=excluded.saleswoman, observations=excluded.observations,
                    updated_at=excluded.updated_at""",
                (
                    order.id, order.origin.value, order.source_reference,
                    _iso(order.delivery_date), order.branch, order.customer_name,
                    order.customer_document, order.customer_phone,
                    order.envelope, order.saleswoman,
                    order.status.value, order.observations, order.cash_entry_id,
                    _iso(order.created_at), _iso(order.updated_at),
                ),
            )
            connection.commit()
        return self.get_order_for_entry(order.cash_entry_id) if order.cash_entry_id else order

    def get_order_for_entry(self, entry_id: str | None) -> Order | None:
        if not entry_id:
            return None
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM orders WHERE cash_entry_id = ?", (entry_id,)
            ).fetchone()
        return self._hydrate_order(row) if row else None

    def list_orders(self) -> Sequence[Order]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT * FROM orders
                ORDER BY delivery_date,
                CASE status WHEN 'PENDIENTE' THEN 0 WHEN 'LISTO' THEN 1 ELSE 2 END,
                created_at"""
            ).fetchall()
        return [self._hydrate_order(row) for row in rows]

    def update_order_status(
        self, order_id: str, status: OrderStatus | str, *,
        reason: str = "", responsible: str = "Sistema",
    ) -> Order:
        target = OrderStatus(status)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if row is None:
                raise InvalidCashDayError(f"pedido inexistente: {order_id}")
            current = self._hydrate_order(row)
            if current.status is target:
                return current
            reason = str(reason or "").strip()
            responsible = str(responsible or "").strip()
            if current.status is OrderStatus.DELIVERED and target is OrderStatus.PENDING:
                if not reason:
                    raise InvalidCashDayError("el motivo de corrección es obligatorio")
                if not responsible:
                    raise InvalidCashDayError("el responsable de la corrección es obligatorio")
            updated = current.transition_to(target)
            connection.execute(
                "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                (updated.status.value, _iso(updated.updated_at), updated.id),
            )
            connection.execute(
                """INSERT INTO order_status_revisions(
                    order_id,previous_status,new_status,responsible,reason,recorded_at
                ) VALUES (?,?,?,?,?,?)""",
                (updated.id, current.status.value, updated.status.value,
                 responsible or "Sistema", reason, _iso(updated.updated_at)),
            )
            connection.commit()
        return updated

    def list_order_status_revisions(self, order_id: str) -> Sequence[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT previous_status,new_status,responsible,reason,recorded_at
                FROM order_status_revisions WHERE order_id = ? ORDER BY id""",
                (order_id,),
            ).fetchall()
        return [dict(row) for row in rows]