import tempfile
import unittest
from pathlib import Path

from modulos.caja_diaria.bootstrap import build_cash_day_controller


class UXControlPhoneContrastTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.controller = build_cash_day_controller(Path(self.temp.name) / "cash.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def values(self, phone=""):
        return {
            "fecha": "12-08-2026", "unidad": "PC", "caja_inicial": "1000",
            "descripcion": "Cliente", "cliente_documento": "", "cliente_telefono": phone,
            "vendedora": "Ana", "total": "10", "efectivo": "10",
        }

    def test_phone_is_optional_and_preserves_paraguayan_text(self):
        _, first = self.controller.add_manual_entry(self.values())
        _, second = self.controller.add_manual_entry(self.values("+595 981 123-456"))
        day = self.controller.load_day("12-08-2026", "PC")
        self.assertEqual(first.customer_phone, "")
        self.assertEqual(second.customer_phone, "+595 981 123-456")
        self.assertEqual(day.entries[-1].customer_phone, "+595 981 123-456")

    def test_pending_and_draft_have_dark_high_contrast_text(self):
        source = open("CajaDiaria.py", encoding="utf-8").read()
        self.assertIn('tag_configure("pending", foreground="#3B2A05", background="#FFF3CD")', source)
        self.assertIn('tag_configure("draft", foreground="#174A7E", background="#EAF3FF")', source)


if __name__ == "__main__":
    unittest.main()
