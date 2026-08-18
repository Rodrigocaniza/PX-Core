"""Repositorio SQLite transaccional de BC Caja."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

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
from ..domain.tracking import (
    ContactRecord,
    Laboratory,
    ReceptionIssue,
    PilarShipment,
    TrackedWork,
    TrackingTransition,
)


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _limites_utc_del_dia(start_date: date, end_date: date) -> tuple[str, str]:
    """Instantes UTC que abren y cierran un rango de dias del negocio.

    El limite superior es exclusivo: cubre el ultimo dia entero sin depender de
    la hora. Devuelve texto sin offset porque se compara contra `datetime()` de
    SQLite, que normaliza a UTC.
    """
    from ..domain.models import BUSINESS_TIMEZONE

    desde = datetime.combine(start_date, time.min, tzinfo=BUSINESS_TIMEZONE)
    hasta = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=BUSINESS_TIMEZONE)
    return (desde.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            hasta.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))


class SQLiteCashDayRepository:
    def __init__(
        self, database_path: str | Path, *, sale_integrator=None
    ) -> None:
        """`sale_integrator` engancha la venta con el inventario.

        Es opcional y por defecto no hay ninguno: sin el, este repositorio
        guarda exactamente como guardaba antes de que existiera el nucleo
        comercial. Esa es la condicion para que instalar esto no cambie el
        comportamiento de una caja que todavia no vincula articulos.

        Cuando esta, corre DENTRO de la misma transaccion del guardado. No abre
        una propia: una segunda transaccion independiente podria dejar la venta
        guardada y el stock no, o al reves.
        """
        self._sale_integrator = sale_integrator
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
    def _ventas_ya_integradas(
        connection: sqlite3.Connection, cash_day: CashDay
    ) -> set[str]:
        """Entradas de este dia que ya movieron inventario.

        Vive en la base y no en memoria: reabrir la ventana o recuperarse de un
        corte tiene que encontrar lo mismo que habia antes.
        """
        if not cash_day.entries:
            return set()
        marcas = ",".join("?" * len(cash_day.entries))
        return {
            fila[0] for fila in connection.execute(
                f"SELECT cash_entry_id FROM sale_stock_integrations"
                f" WHERE cash_entry_id IN ({marcas})",
                [entry.id for entry in cash_day.entries])
        }

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
                stage = "sale_stock_guard"
                integradas = self._ventas_ya_integradas(connection, cash_day)
                if integradas and self._sale_integrator is not None:
                    self._sale_integrator.verificar_editable(
                        connection, cash_day, integradas)
                    stage = "sale_void_compensation"
                    # Antes de escribir el VOIDED, no despues: la devolucion de
                    # la mercaderia es lo que habilita la anulacion, y si algo
                    # de esto falla no queda ni la anulacion ni la devolucion.
                    self._sale_integrator.compensar_anulaciones_en(
                        connection, cash_day, integradas, actor=edited_by)
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
                # Las lineas de una venta que ya movio stock no se reescriben.
                # El guardado normal borra y reinserta, que esta bien para una
                # venta que todavia no saco nada del deposito y es inaceptable
                # para una que si: el movimiento que la saco apunta a esta fila.
                refrescables = [
                    entry for entry in cash_day.entries if entry.id not in integradas
                ]
                connection.executemany(
                    "DELETE FROM sale_items WHERE cash_entry_id = ?",
                    [(entry.id,) for entry in refrescables],
                )
                connection.executemany(
                    """INSERT INTO sale_items(
                        id,cash_entry_id,position,description,code,item_type,frame_price,
                        lens_price,laboratory,prescription_doctor,frame_discount_percent,
                        lens_discount_percent,frame_final_price,lens_final_price,no_cost,
                        article_id,lens_article_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [
                        (
                            item.id, entry.id, position, item.description, item.code,
                            item.item_type, item.frame_price, item.lens_price,
                            item.laboratory, item.prescription_doctor,
                            item.frame_discount_percent, item.lens_discount_percent,
                            item.frame_final_price, item.lens_final_price, int(item.no_cost),
                            item.article_id, item.lens_article_id,
                        )
                        for entry in refrescables
                        for position, item in enumerate(entry.items)
                    ],
                )
                stage = "sale_ledger_integration"
                if self._sale_integrator is not None:
                    self._sale_integrator.integrar_en(
                        connection, cash_day, integradas)
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
                    "article_id": item.article_id,
                    "lens_article_id": item.lens_article_id,
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
                article_id=item["article_id"],
                lens_article_id=item["lens_article_id"],
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

    def order_work_details(self, order_ids: Sequence[str]) -> dict[str, dict]:
        """Qué pidió el cliente y a qué laboratorio fue, en una sola consulta.

        Sale del movimiento que originó el pedido: los artículos cargados si los
        hay y, si no, los campos sueltos de la venta. Sin esto la grilla sólo
        puede mostrar identificadores y hay que abrir otra ventana para saber de
        qué trabajo se trata.
        """
        if not order_ids:
            return {}
        marcadores = ",".join("?" for _ in order_ids)
        with self._connection() as connection:
            filas = connection.execute(
                f"""SELECT o.id AS order_id, e.frame_origin, e.code,
                           e.laboratory AS entry_laboratory,
                           i.item_type, i.description AS item_description,
                           i.laboratory AS item_laboratory
                    FROM orders AS o
                    JOIN cash_entries AS e ON e.id = o.cash_entry_id
                    LEFT JOIN sale_items AS i ON i.cash_entry_id = e.id
                    WHERE o.id IN ({marcadores})
                    ORDER BY o.id, i.position""",
                tuple(order_ids),
            ).fetchall()
        detalles: dict[str, dict] = {}
        for fila in filas:
            detalle = detalles.setdefault(
                fila["order_id"],
                {"trabajo": [], "laboratorio": "", "codigo": str(fila["code"] or "").strip()},
            )
            for candidato in (fila["item_type"], fila["item_description"]):
                texto = str(candidato or "").strip()
                if texto and texto not in detalle["trabajo"]:
                    detalle["trabajo"].append(texto)
            for candidato in (fila["item_laboratory"], fila["entry_laboratory"]):
                if not detalle["laboratorio"] and str(candidato or "").strip():
                    detalle["laboratorio"] = str(candidato).strip()
            if not detalle["trabajo"] and str(fila["frame_origin"] or "").strip():
                detalle["trabajo"].append(str(fila["frame_origin"]).strip())
        return {
            order_id: {
                "trabajo": " + ".join(detalle["trabajo"]),
                "laboratorio": detalle["laboratorio"],
                "codigo": detalle["codigo"],
            }
            for order_id, detalle in detalles.items()
        }

    def latest_order_revisions(self) -> dict[str, dict]:
        """Última novedad por pedido, en una sola consulta (evita N+1 en la grilla)."""
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT r.order_id,r.previous_status,r.new_status,r.responsible,
                          r.reason,r.recorded_at
                FROM order_status_revisions AS r
                JOIN (
                    SELECT order_id, MAX(id) AS id
                    FROM order_status_revisions GROUP BY order_id
                ) AS ultima ON ultima.id = r.id"""
            ).fetchall()
        return {row["order_id"]: dict(row) for row in rows}

    def list_order_status_revisions(self, order_id: str) -> Sequence[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT previous_status,new_status,responsible,reason,recorded_at
                FROM order_status_revisions WHERE order_id = ? ORDER BY id""",
                (order_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- RC19: seguimiento Pilar / laboratorios ---------------------------

    def save_laboratory(self, laboratory: Laboratory) -> Laboratory:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO laboratories(
                    id,name,phone_line,whatsapp,active,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, phone_line=excluded.phone_line,
                    whatsapp=excluded.whatsapp, active=excluded.active,
                    updated_at=excluded.updated_at""",
                (
                    laboratory.id, laboratory.name, laboratory.phone_line,
                    laboratory.whatsapp, int(laboratory.active),
                    _iso(laboratory.created_at), _iso(laboratory.updated_at),
                ),
            )
            connection.commit()
        return laboratory

    def list_laboratories(self, *, only_active: bool = False) -> Sequence[Laboratory]:
        consulta = "SELECT * FROM laboratories"
        if only_active:
            consulta += " WHERE active = 1"
        consulta += " ORDER BY name COLLATE NOCASE"
        with self._connection() as connection:
            rows = connection.execute(consulta).fetchall()
        return [self._hydrate_laboratory(row) for row in rows]

    def get_laboratory(self, laboratory_id: str) -> Laboratory | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM laboratories WHERE id = ?", (laboratory_id,)
            ).fetchone()
        return self._hydrate_laboratory(row) if row else None

    @staticmethod
    def _hydrate_laboratory(row: sqlite3.Row) -> Laboratory:
        return Laboratory(
            id=row["id"], name=row["name"], phone_line=row["phone_line"],
            whatsapp=row["whatsapp"], active=bool(row["active"]),
            created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]),
        )

    def save_pilar_shipment(self, shipment: PilarShipment) -> PilarShipment:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO pilar_shipments(
                    id,shipped_on,consultation_date,origin_branch,destination_branch,
                    operator,note,created_at
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    shipped_on=excluded.shipped_on,
                    consultation_date=excluded.consultation_date,
                    operator=excluded.operator, note=excluded.note""",
                (
                    shipment.id, _iso(shipment.shipped_on), _iso(shipment.consultation_date),
                    shipment.origin_branch, shipment.destination_branch,
                    shipment.operator, shipment.note, _iso(shipment.created_at),
                ),
            )
            connection.commit()
        return shipment

    def get_pilar_shipment(self, shipment_id: str) -> PilarShipment | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM pilar_shipments WHERE id = ?", (shipment_id,)
            ).fetchone()
        return self._hydrate_shipment(row) if row else None

    def list_pilar_shipments(self, *, limit: int = 50) -> Sequence[PilarShipment]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM pilar_shipments ORDER BY shipped_on DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._hydrate_shipment(row) for row in rows]

    @staticmethod
    def _hydrate_shipment(row: sqlite3.Row) -> PilarShipment:
        return PilarShipment(
            id=row["id"], shipped_on=row["shipped_on"],
            consultation_date=row["consultation_date"],
            origin_branch=row["origin_branch"], destination_branch=row["destination_branch"],
            operator=row["operator"], note=row["note"],
            created_at=_datetime(row["created_at"]),
        )

    def list_shipment_candidates(
        self, *, branch: str, start_date: date, end_date: date,
    ) -> Sequence[Order]:
        """Pedidos de la sucursal aun no incluidos en ningun envio.

        La elegibilidad se resuelve en SQL contra `tracked_works`: un pedido ya
        seguido no vuelve a ofrecerse, de modo que no se puede armar dos veces
        el mismo trabajo aunque se repita la consulta.

        El rango se compara como instante, no como `date()` del texto guardado.
        `created_at` se guarda en UTC y las fechas que elige la operadora son
        del dia del negocio: a partir de las 21:00 locales el UTC ya es del dia
        siguiente, asi que comparar fechas sueltas hacia desaparecer de los
        candidatos los pedidos cargados de noche. Se convierten los limites del
        dia local a UTC y se compara contra ellos.
        """
        desde, hasta = _limites_utc_del_dia(start_date, end_date)
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT o.* FROM orders o
                LEFT JOIN tracked_works t ON t.order_id = o.id
                WHERE t.id IS NULL
                  AND o.branch = ? COLLATE NOCASE
                  AND datetime(o.created_at) >= datetime(?)
                  AND datetime(o.created_at) <  datetime(?)
                ORDER BY o.envelope, o.created_at""",
                (branch, desde, hasta),
            ).fetchall()
        return [self._hydrate_order(row) for row in rows]

    def search_untracked_orders(
        self, term: str, *, branch: str | None = None, limit: int = 25,
    ) -> Sequence[Order]:
        """Pedidos por sobre o cliente que aun no entraron al circuito.

        Sostiene NO ESTABA EN LISTA: el fisico que aparecio suele tener su
        pedido ya cargado, y encontrarlo evita volver a escribir cliente y
        receta. La exclusion de los ya seguidos se resuelve en SQL, de modo que
        no se pueda agregar dos veces el mismo trabajo.
        """
        if not str(term or "").strip():
            return []
        patron = f"%{str(term).strip()}%"
        condicion_sucursal = "AND o.branch = ? COLLATE NOCASE" if branch else ""
        parametros = [patron, patron] + ([branch] if branch else []) + [int(limit)]
        with self._connection() as connection:
            rows = connection.execute(
                f"""SELECT o.* FROM orders o
                LEFT JOIN tracked_works t ON t.order_id = o.id
                WHERE t.id IS NULL
                  AND (o.envelope LIKE ? COLLATE NOCASE
                       OR o.customer_name LIKE ? COLLATE NOCASE)
                  {condicion_sucursal}
                ORDER BY o.created_at DESC, o.envelope
                LIMIT ?""",
                tuple(parametros),
            ).fetchall()
        return [self._hydrate_order(row) for row in rows]

    def customer_phones(
        self, order_ids: Sequence[str] = (), cash_entry_ids: Sequence[str] = (),
    ) -> dict[str, str]:
        """Telefono del cliente, indexado por id de pedido o de venta.

        El seguimiento no guarda telefono propio: el dato ya existe en el
        pedido o en la venta que originaron el trabajo, y duplicarlo abriria la
        puerta a que las dos copias digan cosas distintas. Se resuelve en una
        consulta por lote, no una por fila.
        """
        encontrados: dict[str, str] = {}
        for tabla, ids in (("orders", order_ids), ("cash_entries", cash_entry_ids)):
            limpios = [str(i) for i in ids if i]
            if not limpios:
                continue
            marcadores = ",".join("?" for _ in limpios)
            with self._connection() as connection:
                filas = connection.execute(
                    f"SELECT id, customer_phone FROM {tabla} WHERE id IN ({marcadores})",
                    tuple(limpios),
                ).fetchall()
            for fila in filas:
                telefono = str(fila["customer_phone"] or "").strip()
                if telefono:
                    encontrados[fila["id"]] = telefono
        return encontrados

    def list_orders_by_ids(self, order_ids: Sequence[str]) -> Sequence[Order]:
        """Pedidos por id exacto, sin filtrar por fecha ni sucursal."""
        if not order_ids:
            return []
        marcadores = ",".join("?" for _ in order_ids)
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM orders WHERE id IN ({marcadores})", tuple(order_ids),
            ).fetchall()
        return [self._hydrate_order(row) for row in rows]

    def list_tracked_works_for_orders(self, order_ids: Sequence[str]) -> Sequence[TrackedWork]:
        if not order_ids:
            return []
        marcadores = ",".join("?" for _ in order_ids)
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM tracked_works WHERE order_id IN ({marcadores})",
                tuple(order_ids),
            ).fetchall()
            return [self._hydrate_tracked_work(connection, row) for row in rows]

    def branch_of_register(self, cash_register: str) -> str | None:
        """Sucursal ligada a la caja, o None si nadie la asigno todavia."""
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT branch FROM cash_register_branches WHERE cash_register = ?",
                (str(cash_register or "").strip(),),
            ).fetchone()
        return fila["branch"] if fila else None

    def list_register_branches(self) -> Sequence[Mapping[str, Any]]:
        with self._connection() as connection:
            return [dict(r) for r in connection.execute(
                "SELECT * FROM cash_register_branches ORDER BY cash_register")]

    def bind_register_to_branch(
        self, cash_register: str, branch: str, *, assigned_by: str, reason: str = "",
    ) -> None:
        """Asigna o reasigna la sucursal de una caja, dejando traza.

        Reasignar es administrativo y queda auditado: una caja no puede
        cambiar de sucursal durante la operacion normal.
        """
        caja = str(cash_register or "").strip()
        sucursal = str(branch or "").strip().upper()
        responsable = str(assigned_by or "").strip()
        if not caja or not sucursal:
            raise InvalidCashDayError("caja y sucursal son obligatorias")
        if not responsable:
            raise InvalidCashDayError("la asignacion requiere responsable")
        ahora = datetime.now().astimezone().isoformat()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previa = connection.execute(
                "SELECT branch FROM cash_register_branches WHERE cash_register = ?", (caja,),
            ).fetchone()
            connection.execute(
                """INSERT INTO cash_register_branches(
                    cash_register, branch, assigned_by, reason, created_at, updated_at
                ) VALUES (?,?,?,?,?,?)
                ON CONFLICT(cash_register) DO UPDATE SET
                    branch=excluded.branch, assigned_by=excluded.assigned_by,
                    reason=excluded.reason, updated_at=excluded.updated_at""",
                (caja, sucursal, responsable, str(reason or "").strip(), ahora, ahora),
            )
            connection.execute(
                """INSERT INTO admin_audit_log(
                    id, actor, action, target_type, target_id, result, details_json, recorded_at
                ) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    __import__("uuid").uuid4().hex, responsable,
                    "CASH_REGISTER_BRANCH_BIND", "cash_register", caja, "SUCCESS",
                    json.dumps({"anterior": previa["branch"] if previa else None,
                                "nueva": sucursal, "motivo": reason}, ensure_ascii=False),
                    ahora,
                ),
            )
            connection.commit()

    def laboratory_has_history(self, laboratory_id: str) -> bool:
        with self._connection() as connection:
            fila = connection.execute(
                "SELECT 1 FROM tracked_works WHERE laboratory_id = ? LIMIT 1",
                (laboratory_id,),
            ).fetchone()
        return fila is not None

    def save_tracked_work(self, work: TrackedWork) -> TrackedWork:
        """Guarda el trabajo y reescribe su traza en una sola transaccion.

        Las transiciones y contactos son append-only en el dominio, asi que
        reescribirlos por posicion conserva la historia sin duplicarla.
        """
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO tracked_works(
                        id,envelope,customer_name,status,origin_branch,processing_branch,reception_issue,
                        awaiting_confirmation,confirmation_note,laboratory_id,
                        expected_date,expected_time,confirmed_for_next_day,order_id,
                        cash_entry_id,shipment_id,consultation_date,observations,created_by,
                        created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        envelope=excluded.envelope, customer_name=excluded.customer_name,
                        status=excluded.status, origin_branch=excluded.origin_branch,
                        processing_branch=excluded.processing_branch,
                        reception_issue=excluded.reception_issue,
                        awaiting_confirmation=excluded.awaiting_confirmation,
                        confirmation_note=excluded.confirmation_note,
                        laboratory_id=excluded.laboratory_id,
                        expected_date=excluded.expected_date,
                        expected_time=excluded.expected_time,
                        confirmed_for_next_day=excluded.confirmed_for_next_day,
                        order_id=excluded.order_id, cash_entry_id=excluded.cash_entry_id,
                        shipment_id=excluded.shipment_id,
                        consultation_date=excluded.consultation_date,
                        observations=excluded.observations,
                        updated_at=excluded.updated_at""",
                    (
                        work.id, work.envelope, work.customer_name, work.status.value,
                        work.origin_branch, work.processing_branch,
                        work.reception_issue.value if work.reception_issue else None,
                        int(work.awaiting_confirmation), work.confirmation_note,
                        work.laboratory_id,
                        _iso(work.expected_date),
                        work.expected_time.strftime("%H:%M") if work.expected_time else None,
                        int(work.confirmed_for_next_day), work.order_id, work.cash_entry_id,
                        work.shipment_id, _iso(work.consultation_date), work.observations, work.created_by,
                        _iso(work.created_at), _iso(work.updated_at),
                    ),
                )
                for sequence, transition in enumerate(work.transitions, start=1):
                    connection.execute(
                        """INSERT INTO tracked_work_transitions(
                            id,work_id,sequence,from_status,to_status,responsible,note,recorded_at
                        ) VALUES (?,?,?,?,?,?,?,?)
                        ON CONFLICT(work_id, sequence) DO NOTHING""",
                        (
                            transition.id, work.id, sequence,
                            transition.from_status.value if transition.from_status else None,
                            transition.to_status.value, transition.responsible,
                            transition.note, _iso(transition.recorded_at),
                        ),
                    )
                for sequence, contact in enumerate(work.contacts, start=1):
                    connection.execute(
                        """INSERT INTO tracked_work_contacts(
                            id,work_id,sequence,operator,channel,result,
                            next_expected_date,next_expected_time,recorded_at
                        ) VALUES (?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(work_id, sequence) DO NOTHING""",
                        (
                            contact.id, work.id, sequence, contact.operator,
                            contact.channel.value, contact.result,
                            _iso(contact.next_expected_date),
                            contact.next_expected_time.strftime("%H:%M")
                            if contact.next_expected_time else None,
                            _iso(contact.recorded_at),
                        ),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return work

    def get_tracked_work(self, work_id: str) -> TrackedWork | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM tracked_works WHERE id = ?", (work_id,)
            ).fetchone()
            if row is None:
                return None
            return self._hydrate_tracked_work(connection, row)

    def list_tracked_works(
        self, *, consultation_date: date | None = None, status: str | None = None,
        laboratory_id: str | None = None,
    ) -> Sequence[TrackedWork]:
        consulta = "SELECT * FROM tracked_works"
        condiciones, parametros = [], []
        if consultation_date is not None:
            condiciones.append("consultation_date = ?")
            parametros.append(_iso(consultation_date))
        if status:
            condiciones.append("status = ?")
            parametros.append(status)
        if laboratory_id:
            condiciones.append("laboratory_id = ?")
            parametros.append(laboratory_id)
        if condiciones:
            consulta += " WHERE " + " AND ".join(condiciones)
        consulta += " ORDER BY COALESCE(expected_date, '9999-12-31'), envelope, created_at"
        with self._connection() as connection:
            rows = connection.execute(consulta, tuple(parametros)).fetchall()
            return [self._hydrate_tracked_work(connection, row) for row in rows]

    def _hydrate_tracked_work(
        self, connection: sqlite3.Connection, row: sqlite3.Row,
    ) -> TrackedWork:
        transiciones = connection.execute(
            """SELECT * FROM tracked_work_transitions
            WHERE work_id = ? ORDER BY sequence""", (row["id"],),
        ).fetchall()
        contactos = connection.execute(
            """SELECT * FROM tracked_work_contacts
            WHERE work_id = ? ORDER BY sequence""", (row["id"],),
        ).fetchall()
        return TrackedWork(
            id=row["id"], envelope=row["envelope"], customer_name=row["customer_name"],
            status=row["status"], origin_branch=row["origin_branch"],
            processing_branch=row["processing_branch"],
            reception_issue=row["reception_issue"],
            awaiting_confirmation=bool(row["awaiting_confirmation"]),
            confirmation_note=row["confirmation_note"],
            laboratory_id=row["laboratory_id"], expected_date=row["expected_date"],
            expected_time=row["expected_time"],
            confirmed_for_next_day=bool(row["confirmed_for_next_day"]),
            order_id=row["order_id"], cash_entry_id=row["cash_entry_id"],
            shipment_id=row["shipment_id"], consultation_date=row["consultation_date"], observations=row["observations"],
            created_by=row["created_by"], created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]),
            transitions=tuple(
                TrackingTransition(
                    id=item["id"], from_status=item["from_status"],
                    to_status=item["to_status"], responsible=item["responsible"],
                    note=item["note"], recorded_at=_datetime(item["recorded_at"]),
                ) for item in transiciones
            ),
            contacts=tuple(
                ContactRecord(
                    id=item["id"], operator=item["operator"], channel=item["channel"],
                    result=item["result"], next_expected_date=item["next_expected_date"],
                    next_expected_time=item["next_expected_time"],
                    recorded_at=_datetime(item["recorded_at"]),
                ) for item in contactos
            ),
        )