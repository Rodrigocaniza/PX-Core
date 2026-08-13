import sqlite3
import tempfile
import unittest
from pathlib import Path

from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.ui.privacy import FinancialPrivacy


class CashContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "cash.sqlite3"
        self.controller = build_cash_day_controller(self.database)

    def tearDown(self):
        self.controller.service.repository.close()
        self.temp.cleanup()

    def test_withdrawal_is_not_expense_and_reduces_expected_cash(self):
        self.controller.open_or_load_day("12-08-2026", "ASU", "2.000.000")
        day, withdrawal = self.controller.add_withdrawal(
            "12-08-2026", "ASU", "500.000", "Administración", "Entrega diaria", "operadora"
        )
        totals = day.totals()
        self.assertEqual(withdrawal.origin, "cash-withdrawal")
        self.assertEqual(totals.withdrawals, 500_000)
        self.assertEqual(totals.expenses, 0)
        self.assertEqual(totals.total, 0)
        self.assertEqual(totals.expected_cash, 1_500_000)

    def test_withdrawal_persists_and_is_auditable(self):
        self.controller.open_or_load_day("12-08-2026", "ASU", "2.000.000")
        _, withdrawal = self.controller.add_withdrawal(
            "12-08-2026", "ASU", "500.000", performed_by="operadora"
        )
        reloaded = self.controller.load_day("12-08-2026", "ASU")
        self.assertEqual(reloaded.entries[0].withdrawal, 500_000)
        self.assertEqual(reloaded.entries[0].performed_by, "operadora")
        revisions = self.controller.service.repository.list_entry_revisions(withdrawal.id)
        self.assertEqual(revisions[0]["snapshot"]["withdrawal"], 500_000)

    def _closed_day(self, date_text, unit, opening, counted=None):
        day = self.controller.open_or_load_day(date_text, unit, opening)
        if counted is not None:
            quantities = {100_000: counted // 100_000}
            self.controller.record_cash_count(date_text, unit, quantities)
        return self.controller.close_day(date_text, unit)

    def test_continuity_prefers_previous_physical_count_same_branch(self):
        previous = self._closed_day("12-08-2026", "ASU", "1.500.000", counted=1_400_000)
        current = self.controller.open_or_load_day("13-08-2026", "ASU", "1.450.000")
        self.assertEqual(current.initial_cash_expected, 1_400_000)
        self.assertEqual(current.initial_cash_difference, 50_000)
        self.assertEqual(current.initial_cash_source_day_id, previous.id)
        self.assertEqual(current.initial_cash_source_kind, "ARQUEO_PREVIO")
        self.assertIsNotNone(current.initial_cash_source_count_id)
        self.assertIn("sobran 50.000", self.controller.opening_difference_message(current))

    def test_continuity_falls_back_to_previous_closed_expected(self):
        previous = self._closed_day("12-08-2026", "ASU", "1.500.000")
        current = self.controller.open_or_load_day("13-08-2026", "ASU", "1.450.000")
        self.assertEqual(current.initial_cash_expected, 1_500_000)
        self.assertEqual(current.initial_cash_difference, -50_000)
        self.assertEqual(current.initial_cash_source_day_id, previous.id)
        self.assertEqual(current.initial_cash_source_kind, "CIERRE_ESPERADO")
        self.assertIn("faltan 50.000", self.controller.opening_difference_message(current))

    def test_conforming_opening_has_no_alert(self):
        self._closed_day("12-08-2026", "ASU", "1.500.000")
        current = self.controller.open_or_load_day("13-08-2026", "ASU", "1.500.000")
        self.assertEqual(current.initial_cash_difference, 0)
        self.assertIsNone(self.controller.opening_difference_message(current))

    def test_no_previous_close_has_no_false_difference(self):
        current = self.controller.open_or_load_day("13-08-2026", "PILAR", "2.300.000")
        self.assertIsNone(current.initial_cash_expected)
        self.assertIsNone(current.initial_cash_difference)
        self.assertIsNone(self.controller.opening_difference_message(current))
        self.assertEqual(current.initial_cash_source_kind, "NO_DISPONIBLE")

    def test_branches_never_share_continuity(self):
        self._closed_day("12-08-2026", "ASU", "1.500.000")
        pilar = self.controller.open_or_load_day("13-08-2026", "PILAR", "2.300.000")
        self.assertIsNone(pilar.initial_cash_expected)

    def test_migration_007_is_incremental_and_columns_round_trip(self):
        connection = sqlite3.connect(self.database)
        try:
            versions = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
            day_columns = {row[1] for row in connection.execute("PRAGMA table_info(cash_days)")}
            entry_columns = {row[1] for row in connection.execute("PRAGMA table_info(cash_entries)")}
        finally:
            connection.close()
        self.assertIn("007", versions)
        self.assertIn("initial_cash_expected", day_columns)
        self.assertIn("withdrawal", entry_columns)

    def test_new_amounts_respect_privacy_mode(self):
        privacy = FinancialPrivacy(timeout_seconds=120)
        privacy.hide()
        self.assertNotIn("500.000", privacy.display("500.000"))
        privacy.show()
        self.assertEqual(privacy.display("500.000"), "500.000")


if __name__ == "__main__":
    unittest.main()
