import tempfile
import unittest
from pathlib import Path

from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import CashDayClosedError


class CashOutflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.controller = build_cash_day_controller(Path(self.temp.name) / "cash.sqlite3")
        self.controller.open_or_load_day("14-08-2026", "PC", "1000000")
        self.controller.add_manual_entry({
            "fecha": "14-08-2026", "unidad": "PC", "caja_inicial": "1000000",
            "descripcion": "Venta mixta", "total": "900000", "efectivo": "500000",
            "tarjeta_cheque": "400000", "vendedora": "Ana",
        })

    def tearDown(self):
        self.controller.service.repository.close()
        self.temp.cleanup()

    def test_create_edit_void_expense_is_immediate_and_append_only(self):
        day, expense = self.controller.add_outflow(
            "14-08-2026", "PC", "GASTO", "Limpieza", "100000",
            observations="Compra inicial", performed_by="operadora",
        )
        self.assertIn(expense.id, [entry.id for entry in day.entries])
        self.assertEqual(day.totals().expected_cash, 1_400_000)
        day, edited = self.controller.update_outflow(
            "14-08-2026", "PC", expense.id, "GASTO", "Insumos", "150000",
            observations="Monto corregido", performed_by="supervisora", reason="Factura final",
        )
        self.assertEqual((edited.description, edited.expenses, edited.performed_by),
                         ("Insumos", 150_000, "operadora"))
        self.assertEqual(day.totals().expected_cash, 1_350_000)
        self.controller.void_entry(
            "14-08-2026", "PC", expense.id, "Compra cancelada", user="auditora"
        )
        day = self.controller.load_day("14-08-2026", "PC")
        self.assertEqual(day.totals().expenses, 0)
        audit = self.controller.service.repository.list_entry_revisions(expense.id)
        self.assertEqual([item["action"] for item in audit], ["CREATE", "UPDATE", "VOID"])
        self.assertEqual(audit[0]["snapshot"]["performed_by"], "operadora")
        self.assertEqual(audit[1]["snapshot"]["audit"]["user"], "supervisora")
        self.assertEqual(audit[2]["snapshot"]["audit"]["user"], "auditora")

    def test_delivery_reduces_cash_but_never_sales_or_economic_expenses(self):
        day, delivery = self.controller.add_outflow(
            "14-08-2026", "PC", "ENTREGA_ADMINISTRACION", "Entrega turno", "200000",
            observations="Recibe administración", performed_by="operadora",
        )
        totals = day.totals()
        self.assertEqual(totals.total, 900_000)
        self.assertEqual(totals.cash, 500_000)
        self.assertEqual(totals.card_check, 400_000)
        self.assertEqual(totals.expenses, 0)
        self.assertEqual(totals.withdrawals, 200_000)
        self.assertEqual(totals.expected_cash, 1_300_000)
        day, edited = self.controller.update_outflow(
            "14-08-2026", "PC", delivery.id, "ENTREGA_ADMINISTRACION",
            "Entrega corregida", "250000", observations="Ajuste",
            performed_by="supervisora", reason="Conteo final",
        )
        self.assertEqual(day.totals().expected_cash, 1_250_000)
        self.controller.void_entry("14-08-2026", "PC", edited.id, "Entrega revertida")
        self.assertEqual(self.controller.load_day("14-08-2026", "PC").totals().total, 900_000)

    def test_closed_day_blocks_outflow_edit_and_void(self):
        _, expense = self.controller.add_outflow(
            "14-08-2026", "PC", "GASTO", "Café", "50000",
            performed_by="operadora",
        )
        self.controller.close_day("14-08-2026", "PC")
        with self.assertRaises(CashDayClosedError):
            self.controller.update_outflow(
                "14-08-2026", "PC", expense.id, "GASTO", "Café", "60000",
                observations="", performed_by="operadora", reason="Cambio",
            )
        with self.assertRaises(CashDayClosedError):
            self.controller.void_entry("14-08-2026", "PC", expense.id, "No corresponde")

    def test_migration_classifies_historical_expenses(self):
        with self.controller.service.repository._connection() as connection:
            columns = {
                row[1] for row in connection.execute(
                    "PRAGMA table_info(cash_entries)"
                ).fetchall()
            }
        self.assertIn("outflow_type", columns)


if __name__ == "__main__":
    unittest.main()
