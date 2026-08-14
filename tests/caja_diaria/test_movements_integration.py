import tempfile
import unittest
from pathlib import Path

from modulos.caja_diaria.domain.models import CashDay, CashEntry
from modulos.caja_diaria.infrastructure.movements_exporter import LegacyMovementsExporter
from modulos.caja_diaria.bootstrap import build_cash_day_controller


class MovementsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "movimientos.txt"
        self.exporter = LegacyMovementsExporter(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def _closed_day(self):
        day = CashDay.open(date="13-08-2026", unit="PC", opening_cash=100_000)
        day.add_entry(CashEntry(description="Venta", total=500_000, cash=300_000, card_check=200_000))
        day.add_entry(CashEntry(description="Limpieza", expenses=50_000))
        return day.close()

    def test_closed_day_creates_income_and_expense_compatible_with_legacy_format(self):
        day = self._closed_day()
        result = self.exporter.sync_closed_day(day)

        self.assertEqual((result.created, result.existing), (2, 0))
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0].split("|")[:6], ["Ingreso", "13-08-2026", "Externo", "PC", "500000", "Si"])
        self.assertEqual(lines[1].split("|")[:6], ["Egreso", "13-08-2026", "PC", "Externo", "50000", "Si"])

    def test_retry_is_idempotent_and_preserves_foreign_movements(self):
        self.path.write_text("Ingreso|12-08-2026|Externo|PC|10|Si\n", encoding="utf-8")
        day = self._closed_day()

        first = self.exporter.sync_closed_day(day)
        second = self.exporter.sync_closed_day(day)

        self.assertEqual(first.created, 2)
        self.assertEqual((second.created, second.existing), (0, 2))
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "Ingreso|12-08-2026|Externo|PC|10|Si")
        self.assertEqual(len(lines), 3)

    def test_open_day_is_rejected_and_zero_totals_create_no_lines(self):
        open_day = CashDay.open(date="13-08-2026", unit="PC", opening_cash=0)
        with self.assertRaises(ValueError):
            self.exporter.sync_closed_day(open_day)

        result = self.exporter.sync_closed_day(open_day.close())
        self.assertEqual((result.created, result.existing), (0, 0))
        self.assertFalse(self.path.exists())

    def test_composition_root_targets_the_existing_legacy_movements_file(self):
        database = Path(self.temp.name) / "bc_caja.sqlite3"
        controller = build_cash_day_controller(database)
        expected = database.parent / "movimientos.txt"
        self.assertEqual(controller.movements_exporter.movements_path, expected)


if __name__ == "__main__":
    unittest.main()
