import tempfile
import unittest
from pathlib import Path

from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import InvalidCashDayError


class UXControlHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.controller = build_cash_day_controller(Path(self.temp.name) / "cash.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_range_is_validated_and_scoped_to_unit(self):
        self.controller.open_or_load_day("2026-08-01", "PC", 100)
        self.controller.open_or_load_day("2026-08-03", "PC", 200)
        self.controller.open_or_load_day("2026-08-02", "SUC", 300)
        days = self.controller.list_history_range("01-08-2026", "07-08-2026", "PC")
        self.assertEqual([day.opening_cash for day in days], [100, 200])
        with self.assertRaisesRegex(InvalidCashDayError, "Desde"):
            self.controller.list_history_range("07-08-2026", "01-08-2026", "PC")

    def test_open_and_closed_day_corrections_are_audited(self):
        day = self.controller.open_or_load_day("2026-08-01", "PC", 100)
        corrected = self.controller.correct_opening_cash(
            "01-08-2026", "PC", 150, "conteo corregido", "operadora"
        )
        self.assertEqual(corrected.opening_cash, 150)
        audit = self.controller.opening_cash_corrections(day.id)
        self.assertEqual((audit[0]["old_value"], audit[0]["new_value"]), ("100", "150"))
        self.controller.close_day("01-08-2026", "PC")
        corrected = self.controller.correct_opening_cash(
            "01-08-2026", "PC", 175, "ajuste autorizado", "supervisor"
        )
        self.assertEqual(corrected.opening_cash, 175)
        self.assertEqual(len(self.controller.opening_cash_corrections(day.id)), 2)
        with self.assertRaisesRegex(InvalidCashDayError, "motivo"):
            self.controller.correct_opening_cash("01-08-2026", "PC", 200, "", "supervisor")


if __name__ == "__main__":
    unittest.main()
