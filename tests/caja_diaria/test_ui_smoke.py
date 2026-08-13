from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

import CajaDiaria
import interfaz
from modulos.caja_diaria.bootstrap import build_cash_day_controller


class CashDayUISmokeTests(unittest.TestCase):
    def test_legacy_window_accepts_injected_controller(self):
        signature = inspect.signature(CajaDiaria.abrir_caja_diaria)
        self.assertIn("controller", signature.parameters)
        self.assertIn("usar_ventana_raiz", signature.parameters)
        self.assertTrue(callable(interfaz.iniciar))

    def test_window_is_resizable_and_not_forced_modal(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        self.assertIn("ventana.resizable(True, True)", source)
        self.assertNotIn("ventana.grab_set()", source)
        self.assertNotIn("ventana.transient(ventana_padre)", source)

    def test_fresh_temporary_database_boots_without_development_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "fresh" / "bc_caja.sqlite3"
            self.assertFalse(database.exists())
            controller = build_cash_day_controller(database)
            try:
                day = controller.open_or_load_day("10-08-2026", "PC", "250000")
                self.assertTrue(database.exists())
                self.assertEqual(day.opening_cash, 250000)
                self.assertEqual(controller.load_day("10-08-2026", "PC").id, day.id)
            finally:
                controller.service.repository.close()


if __name__ == "__main__":
    unittest.main()
