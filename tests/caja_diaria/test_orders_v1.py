from datetime import date
from pathlib import Path
import tempfile
import unittest

from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import InvalidCashDayError


class OrdersV1Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.controller = build_cash_day_controller(Path(self.directory.name) / "caja.sqlite3")
        self.values = {
            "fecha": "12-08-2026", "unidad": "PC", "caja_inicial": "500000",
            "descripcion": "Juan Pérez", "cliente_documento": "4.123.456",
            "cliente_telefono": "0981 555 444",
            "sobre": "583", "vendedora": "Ana", "fecha_entrega": "14-08-2026",
            "notas": "Entregar por la tarde", "arm_org": "", "cod": "",
            "armazon": "100000", "cristal": "200000", "laboratorio": "LAB",
            "receta_dr": "DR", "total": "300000", "efectivo": "300000",
            "tarjeta_cheque": "", "ordenes": "Caja Municipal", "cuotas": "3", "saldo": "",
            "gastos": "",
        }

    def tearDown(self):
        self.controller.service.repository.close()
        self.directory.cleanup()

    def test_saleswoman_is_required_and_document_is_optional(self):
        with self.assertRaisesRegex(InvalidCashDayError, "Seleccione la vendedora"):
            self.controller.add_manual_entry({**self.values, "vendedora": "Seleccionar..."})
        day, entry = self.controller.add_manual_entry({
            **self.values, "cliente_documento": "", "fecha_entrega": "",
        })
        self.assertEqual(entry.customer_document, "")
        self.assertEqual(day.entries[0].saleswoman, "Ana")

    def test_delivery_creates_exactly_one_structured_order(self):
        _, entry = self.controller.add_manual_entry(self.values)
        first = self.controller.list_orders("Todos", today="12-08-2026")
        self.assertEqual(len(first), 1)
        order = first[0]
        self.assertEqual((order.origin.value, order.customer_document, order.envelope), ("CAJA", "4.123.456", "583"))
        self.assertEqual(order.customer_phone, "0981 555 444")
        self.assertEqual((entry.orders, entry.installments), ("Caja Municipal", "3"))
        self.assertEqual(order.cash_entry_id, entry.id)
        day = self.controller.load_day("12-08-2026", "PC")
        self.controller.service._ensure_order(day, day.entries[0])
        self.assertEqual(len(self.controller.list_orders("Todos", today="12-08-2026")), 1)

        self.controller.service.repository.close()
        self.controller = build_cash_day_controller(Path(self.directory.name) / "caja.sqlite3")
        recovered = self.controller.list_orders("Todos", today="12-08-2026")
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].customer_phone, "0981 555 444")

    def test_filters_and_state_transitions_persist(self):
        _, entry = self.controller.add_manual_entry(self.values)
        self.assertEqual(len(self.controller.list_orders("Próximos", today="12-08-2026")), 1)
        self.assertEqual(len(self.controller.list_orders("Hoy", today="14-08-2026")), 1)
        self.assertEqual(len(self.controller.list_orders("Atrasados", today="15-08-2026")), 1)
        order = self.controller.service.repository.get_order_for_entry(entry.id)
        self.controller.update_order_status(order.id, "LISTO")
        delivered = self.controller.update_order_status(order.id, "ENTREGADO")
        self.assertEqual(delivered.status.value, "ENTREGADO")
        self.assertEqual(self.controller.service.repository.get_order_for_entry(entry.id).status.value, "ENTREGADO")


if __name__ == "__main__":
    unittest.main()
