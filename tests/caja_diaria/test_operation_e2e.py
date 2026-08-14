from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modulos.caja_diaria.bootstrap import build_cash_day_controller


class CashOperationE2ETests(unittest.TestCase):
    def test_two_days_edit_void_close_backup_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "pilot.sqlite3"
            controller = build_cash_day_controller(database)
            try:
                base = {
                    "fecha": "01-08-2026", "unidad": "PC", "caja_inicial": "500000",
                    "sobre": "", "arm_org": "", "cod": "", "armazon": "",
                    "cristal": "", "receta_dr": "", "ordenes": "", "cuotas": "",
                    "saldo": "", "gastos": "", "tarjeta_cheque": "",
                    "vendedora": "ANA",
                }
                day1, cash_sale = controller.add_manual_entry({
                    **base, "descripcion": "VENTA EFECTIVO", "total": "300000", "efectivo": "300000",
                })
                _, card_sale = controller.add_manual_entry({
                    **base, "caja_inicial": "", "descripcion": "VENTA TARJETA",
                    "total": "400000", "efectivo": "", "tarjeta_cheque": "400000",
                })
                _, expense = controller.add_manual_entry({
                    **base, "caja_inicial": "", "descripcion": "GASTO ENVÍO",
                    "total": "", "efectivo": "", "gastos": "50000",
                })
                _, edited = controller.update_manual_entry(
                    cash_sale.id,
                    {**base, "caja_inicial": "", "descripcion": "VENTA EFECTIVO CORREGIDA",
                     "total": "350000", "efectivo": "350000"},
                )
                controller.void_entry("01-08-2026", "PC", card_sale.id, "Venta cancelada")
                totals = controller.totals("01-08-2026", "PC")
                self.assertEqual((totals.total, totals.cash, totals.card_check, totals.expenses),
                                 (350000, 350000, 0, 50000))
                self.assertEqual(totals.expected_cash, 800000)
                closed = controller.close_day("01-08-2026", "PC")
                self.assertEqual(closed.closing_totals.expected_cash, 800000)
                self.assertTrue(controller.last_backup_path.is_file())
            finally:
                controller.service.repository.close()

            restarted = build_cash_day_controller(database)
            try:
                history = restarted.list_history("01-08-2026", "PC")
                self.assertEqual(history.status.value, "CLOSED")
                self.assertEqual(len(history.entries), 3)
                self.assertEqual(history.closing_totals.expected_cash, 800000)
                carried = restarted.open_or_load_day("03-08-2026", "PC", "")
                self.assertEqual(carried.opening_cash, 800000)
                day2, _ = restarted.add_manual_entry({
                    **base, "fecha": "03-08-2026", "caja_inicial": "",
                    "descripcion": "VENTA DÍA 2", "total": "100000", "efectivo": "100000",
                })
                self.assertEqual(day2.opening_cash, 800000)
                self.assertEqual(day2.totals().expected_cash, 900000)
            finally:
                restarted.service.repository.close()

            final_restart = build_cash_day_controller(database)
            try:
                day2_reloaded = final_restart.list_history("03-08-2026", "PC")
                self.assertEqual(day2_reloaded.status.value, "OPEN")
                self.assertEqual(day2_reloaded.totals().expected_cash, 900000)
            finally:
                final_restart.service.repository.close()


if __name__ == "__main__":
    unittest.main()
