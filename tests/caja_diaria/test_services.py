from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modulos.caja_diaria.application.services import CashDayService
from modulos.caja_diaria.domain.errors import CashDayAlreadyExistsError, CashDayClosedError
from modulos.caja_diaria.domain.models import CashEntry
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository


class CashDayServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = SQLiteCashDayRepository(Path(self.tempdir.name) / "service.sqlite3")
        self.service = CashDayService(self.repository)

    def tearDown(self):
        self.repository.close()
        self.tempdir.cleanup()

    def test_open_add_close_and_historical_query(self):
        day = self.service.open_day(business_date="02-08-2026", unit="pc", opening_cash=500000)
        self.service.add_entry(day.id, CashEntry(description="VENTA", total=300000, cash=300000))
        closed = self.service.close_day(day.id)
        self.assertEqual(closed.closing_totals.expected_cash, 800000)
        found = self.service.get_by_date_and_unit("2026-08-02", "PC")
        self.assertEqual(found.id, day.id)
        with self.assertRaises(CashDayClosedError):
            self.service.add_entry(day.id, CashEntry(description="TARDE"))

    def test_duplicate_business_date_and_unit_is_rejected(self):
        self.service.open_day(business_date="2026-08-02", unit="PC", opening_cash=0)
        with self.assertRaises(CashDayAlreadyExistsError):
            self.service.open_day(business_date="02-08-2026", unit="pc", opening_cash=0)

    def test_batch_import_replaces_entries_atomically(self):
        day = self.service.open_day(business_date="2026-08-02", unit="PC", opening_cash=0)
        imported = self.service.import_entries(day.id, [
            CashEntry(description="LÍNEA 1", total=100000, cash=100000, origin="excel"),
            CashEntry(description="LÍNEA 2", total=200000, card_check=200000, origin="excel"),
        ])
        self.assertEqual(imported.totals().total, 300000)
        self.assertEqual(len(self.service.get_day(day.id).entries), 2)


if __name__ == "__main__":
    unittest.main()
