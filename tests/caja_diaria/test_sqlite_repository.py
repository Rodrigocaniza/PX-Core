from __future__ import annotations

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from modulos.caja_diaria.domain.models import CashDay, CashDayStatus, CashEntry
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
            self.assertEqual(connection.execute("SELECT version FROM schema_migrations").fetchall(), [("001",)])
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()
        self.assertTrue({"cash_days", "cash_entries", "cash_counts"}.issubset(tables))

    def test_round_trip_preserves_all_entry_fields_and_null_money(self):
        day = CashDay.open(date="2026-08-02", unit="pc", opening_cash=500000)
        day.add_entry(CashEntry(
            description="CLIENTE", envelope="S-1", frame_origin="ARM", code="A1",
            frame="300000", lens="200000", prescription_doctor="DR A", total=500000,
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
        self.assertIsNone(loaded.entries[0].expenses)
        self.assertEqual(loaded.entries[0].source_reference, "fixture:5")

    def test_save_is_transactional_when_an_entry_violates_database_constraints(self):
        day = CashDay.open(date="2026-08-02", unit="PC", opening_cash=0)
        day.add_entry(CashEntry(description="VÁLIDA", total=100))
        self.repository.save(day)
        invalid = replace(day.entries[0], id="otra", cash_day_id="día-inexistente")
        day.entries.append(invalid)
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save(day)
        loaded = self.repository.get(day.id)
        self.assertEqual([entry.description for entry in loaded.entries], ["VÁLIDA"])

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


if __name__ == "__main__":
    unittest.main()
