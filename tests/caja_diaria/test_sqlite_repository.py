from __future__ import annotations

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from modulos.caja_diaria.domain.models import CashCountStatus, CashDay, CashDayStatus, CashEntry
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository


class SQLiteCashDayRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "caja.sqlite3"
        self.repository = SQLiteCashDayRepository(self.database)

    def tearDown(self):
        self.repository.close()
        self.tempdir.cleanup()

    def test_migration_is_versioned_idempotent_and_enables_foreign_keys(self):
        self.repository.migrate()
        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall(),
                [("001",), ("002",), ("003",), ("004",), ("005",), ("006",), ("007",), ("008",), ("009",), ("010",), ("011",), ("012",), ("013",), ("014",), ("015",), ("016",), ("017",), ("018",)],
            )
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()
        self.assertTrue(
            {"cash_days", "cash_entries", "cash_counts", "cash_entry_revisions", "orders"}.issubset(tables)
        )

    def test_round_trip_preserves_all_entry_fields_and_null_money(self):
        day = CashDay.open(date="2026-08-02", unit="pc", opening_cash=500000)
        day.add_entry(CashEntry(
            description="CLIENTE", envelope="S-1", frame_origin="ARM", code="A1",
            frame="300000", lens="200000", laboratory="LAB CENTRAL",
            prescription_doctor="DR A", total=500000,
            cash=250000, card_check=200000, orders="ORD-1", installments="2x25000",
            balance="cancelado", expenses=None, origin="excel", source_reference="fixture:5",
        ))
        self.repository.save(day)
        loaded = self.repository.get(day.id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.business_date, date(2026, 8, 2))
        self.assertEqual(loaded.opening_cash, 500000)
        self.assertEqual(len(loaded.entries), 1)
        self.assertEqual(loaded.entries[0].balance, "cancelado")
        self.assertEqual(loaded.entries[0].laboratory, "LAB CENTRAL")
        self.assertIsNone(loaded.entries[0].expenses)
        self.assertEqual(loaded.entries[0].source_reference, "fixture:5")

    def test_save_is_transactional_when_an_entry_violates_database_constraints(self):
        day = CashDay.open(date="2026-08-02", unit="PC", opening_cash=0)
        day.add_entry(CashEntry(description="VÃLIDA", total=100))
        self.repository.save(day)
        invalid = replace(day.entries[0], id="otra", cash_day_id="dÃ­a-inexistente")
        day.entries.append(invalid)
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save(day)
        loaded = self.repository.get(day.id)
        self.assertEqual([entry.description for entry in loaded.entries], ["VÃLIDA"])

    def test_closed_snapshot_and_history_queries_round_trip(self):
        first = CashDay.open(date="2026-08-01", unit="PC", opening_cash=100000)
        first.add_entry(CashEntry(description="VENTA", total=200000, cash=200000))
        first.close()
        second = CashDay.open(date="2026-08-02", unit="PC", opening_cash=300000)
        self.repository.save(first)
        self.repository.save(second)

        loaded = self.repository.get_by_date_and_unit(date(2026, 8, 1), "pc")
        self.assertEqual(loaded.status, CashDayStatus.CLOSED)
        self.assertEqual(loaded.closing_totals.expected_cash, 300000)
        history = self.repository.list_between(date(2026, 8, 1), date(2026, 8, 31), "PC")
        self.assertEqual([day.business_date.day for day in history], [1, 2])

    def test_latest_cash_count_is_persisted(self):
        day = CashDay.open(date="2026-08-02", unit="PC", opening_cash=150000)
        self.repository.save(day)
        count = day.count_cash({100000: 1, 50000: 1})
        self.repository.save_cash_count(count)
        loaded = self.repository.get_latest_cash_count(day.id)
        self.assertEqual(loaded.counted_total, 150000)
        self.assertEqual(dict(loaded.quantities), {50000: 1, 100000: 1})

    def test_cash_count_with_difference_persists_expected_counted_status_and_detail(self):
        day = CashDay.open(date="2026-08-02", unit="PC", opening_cash=1500000)
        self.repository.save(day)
        shortage = day.count_cash({100000: 14, 50000: 1})
        self.repository.save_cash_count(shortage)
        loaded = self.repository.get_latest_cash_count(day.id)
        self.assertEqual(loaded.expected_total, 1500000)
        self.assertEqual(loaded.counted_total, 1450000)
        self.assertEqual(loaded.difference, -50000)
        self.assertEqual(loaded.status, CashCountStatus.SHORTAGE)
        self.assertEqual(dict(loaded.quantities), {50000: 1, 100000: 14})
        self.assertIsNotNone(loaded.recorded_at)
    def test_edit_and_void_keep_append_only_revisions(self):
        day = CashDay.open(date="2026-08-02", unit="PC", opening_cash=100000)
        created = day.add_entry(CashEntry(description="VENTA", total=200000, cash=200000))
        self.repository.save(day)
        edited = created.edited(total=250000, cash=250000)
        day.update_entry(edited)
        self.repository.save(day)
        day.void_entry(created.id, "Carga duplicada")
        self.repository.save(day)

        loaded = self.repository.get(day.id)
        self.assertEqual(len(loaded.entries), 1)
        self.assertEqual(loaded.entries[0].status.value, "VOIDED")
        self.assertEqual(loaded.entries[0].void_reason, "Carga duplicada")
        self.assertEqual(loaded.totals().expected_cash, 100000)
        revisions = self.repository.list_entry_revisions(created.id)
        self.assertEqual([item["action"] for item in revisions], ["CREATE", "UPDATE", "VOID"])
        self.assertEqual([item["revision"] for item in revisions], [0, 1, 2])
        self.assertEqual(revisions[1]["snapshot"]["total"], 250000)

    def test_existing_001_database_migrates_without_losing_entries(self):
        legacy_database = Path(self.tempdir.name) / "legacy-001.sqlite3"
        migration_001 = (
            Path(__file__).parents[2]
            / "modulos"
            / "caja_diaria"
            / "infrastructure"
            / "migrations"
            / "001_caja_diaria.sql"
        )
        connection = sqlite3.connect(legacy_database)
        try:
            connection.executescript(migration_001.read_text(encoding="utf-8"))
            connection.execute(
                """INSERT INTO cash_days(
                    id,business_date,unit,opening_cash,status,opened_at,version
                ) VALUES ('day-1','2026-08-01','PC',100000,'OPEN','2026-08-01T08:00:00+00:00',0)"""
            )
            connection.execute(
                """INSERT INTO cash_entries(
                    id,cash_day_id,description,total,cash,created_at,updated_at
                ) VALUES ('entry-1','day-1','VENTA',200000,200000,
                    '2026-08-01T09:00:00+00:00','2026-08-01T09:00:00+00:00')"""
            )
            connection.commit()
        finally:
            connection.close()

        migrated = SQLiteCashDayRepository(legacy_database)
        try:
            day = migrated.get("day-1")
            self.assertEqual(day.entries[0].status.value, "ACTIVE")
            self.assertEqual(day.entries[0].laboratory, "")
            self.assertEqual(day.totals().expected_cash, 300000)
            check = sqlite3.connect(legacy_database)
            try:
                versions = check.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            finally:
                check.close()
            self.assertEqual(versions, [("001",), ("002",), ("003",), ("004",), ("005",), ("006",), ("007",), ("008",), ("009",), ("010",), ("011",), ("012",), ("013",), ("014",), ("015",), ("016",), ("017",), ("018",)])
        finally:
            migrated.close()


if __name__ == "__main__":
    unittest.main()
