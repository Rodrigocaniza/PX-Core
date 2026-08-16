import sqlite3
import tempfile
import unittest
from pathlib import Path

from CajaDiaria import completar_items_para_guardar
from modulos.caja_diaria.bootstrap import build_cash_day_controller


class SQLiteSaveBugfixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "bc_caja.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def values(name="Venta moderna"):
        values = {
            "fecha": "12-08-2026", "unidad": "PC", "caja_inicial": "1.190.000",
            "descripcion": name, "cliente_documento": "1234567",
            "cliente_telefono": "+595 981 123456", "sobre": "123",
            "arm_org": "ArmazÃ³n", "cod": "456", "armazon": "1.500.000",
            "cristal": "250.000", "laboratorio": "LAB", "receta_dr": "Dr Test",
            "total": "1.750.000", "efectivo": "1.000.000", "tarjeta_cheque": "",
            "transferencia": "", "saldo": "750.000", "notas": "",
            "fecha_entrega": "14-08-2026", "vendedora": "Ana",
        }
        values["items"] = completar_items_para_guardar(values, ())
        return values

    def test_historical_database_can_save_current_sale_after_migrations(self):
        controller = build_cash_day_controller(self.database)
        try:
            _, historical = controller.add_manual_entry(self.values("Venta histÃ³rica"))
            self.assertIsNotNone(controller.service.repository.get_order_for_entry(historical.id))
            # Reproduce el caso real: otra venta en la misma jornada, cuando la
            # primera cabecera ya estÃ¡ referenciada por orders.cash_entry_id.
            day, current = controller.add_manual_entry(self.values("Venta actual"))
            self.assertEqual(len(day.entries), 2)
            self.assertEqual(len(current.items), 1)
        finally:
            controller.service.repository.close()
        restarted = build_cash_day_controller(self.database)
        try:
            day = restarted.load_day("12-08-2026", "PC")
            self.assertEqual(len(day.entries), 2)
            self.assertEqual(len(restarted.list_orders("Todos", today="12-08-2026")), 2)
            connection = sqlite3.connect(self.database)
            try:
                self.assertEqual(connection.execute("PRAGMA quick_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(
                    [row[0] for row in connection.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                )], ["001", "002", "003", "004", "005", "006", "007", "008", "009", "010", "011", "012", "013", "014", "015", "016", "017"]
                )
            finally:
                connection.close()
        finally:
            restarted.service.repository.close()

    def test_sqlite_save_failure_rolls_back_atomically_and_keeps_ui_data(self):
        controller = build_cash_day_controller(self.database)
        values = self.values("Datos visibles")
        try:
            controller.open_or_load_day("12-08-2026", "PC", "1.190.000")
            connection = sqlite3.connect(self.database)
            try:
                connection.execute(
                    "CREATE TRIGGER fail_sale_item BEFORE INSERT ON sale_items "
                    "BEGIN SELECT RAISE(ABORT, 'forced item failure'); END"
                )
                connection.commit()
            finally:
                connection.close()
            with self.assertRaises(sqlite3.IntegrityError):
                controller.add_manual_entry(values)
            # La capa UI conserva su mapping y el repositorio no deja parciales.
            self.assertEqual(values["descripcion"], "Datos visibles")
            connection = sqlite3.connect(self.database)
            try:
                self.assertEqual(connection.execute("SELECT count(*) FROM cash_entries").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT count(*) FROM sale_items").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT count(*) FROM orders").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT count(*) FROM cash_entry_revisions").fetchone()[0], 0)
            finally:
                connection.close()
            log = self.database.parent / "Logs" / "sqlite-errors.log"
            self.assertIn("stage=sale_items_refresh", log.read_text(encoding="utf-8"))
            self.assertIn("SQLITE_CONSTRAINT_TRIGGER", log.read_text(encoding="utf-8"))
        finally:
            controller.service.repository.close()


if __name__ == "__main__":
    unittest.main()
