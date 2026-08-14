import sqlite3
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from CajaDiaria import (
    completar_items_para_guardar, escribir_importe_formateado,
    leer_valores_formulario, mostrar_error_guardado,
)
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import SaleDraft, SaleItem


class MultiItemSalesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "caja.sqlite3"
        self.controller = build_cash_day_controller(self.database)
        self.items = (
            SaleItem(description="A", frame_price="500000", lens_price="250000"),
            SaleItem(description="B", frame_price="300000", lens_price="0"),
            SaleItem(description="C", frame_price="600000", lens_price="200000"),
        )
        self.values = {
            "fecha": "12-08-2026", "unidad": "PC", "caja_inicial": "500000",
            "descripcion": "Juan Pérez", "cliente_documento": "4.123.456", "sobre": "583",
            "vendedora": "Ana", "fecha_entrega": "14-08-2026", "notas": "Multi",
            "arm_org": "", "cod": "", "armazon": "", "cristal": "",
            "laboratorio": "", "receta_dr": "", "total": "", "efectivo": "1000000",
            "tarjeta_cheque": "", "ordenes": "", "cuotas": "", "saldo": "850000",
            "gastos": "", "items": self.items,
        }

    def tearDown(self):
        self.controller.service.repository.close(); self.temp.cleanup()

    def test_three_items_are_one_header_one_order_and_total_1850000(self):
        day, entry = self.controller.add_manual_entry(self.values)
        self.assertEqual(entry.total, 1_850_000)
        self.assertEqual(len(day.entries), 1)
        self.assertEqual(len(entry.items), 3)
        self.assertEqual(len(self.controller.list_orders("Todos", today="12-08-2026")), 1)
        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM cash_entries").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM sale_items").fetchone()[0], 3)
        finally:
            connection.close()
        reloaded = self.controller.load_day("12-08-2026", "PC").entries[0]
        self.assertEqual([item.subtotal for item in reloaded.items], [750000, 300000, 800000])

    def test_draft_add_edit_remove_recalculates(self):
        draft = SaleDraft(list(self.items))
        self.assertEqual(draft.total, 1_850_000)
        draft.edit(1, SaleItem(description="B2", frame_price=400000, lens_price=100000))
        self.assertEqual(draft.total, 2_050_000)
        draft.remove(0)
        self.assertEqual(draft.total, 1_300_000)

    def test_explicit_empty_items_is_blocked(self):
        with self.assertRaisesRegex(InvalidCashDayError, "al menos un producto"):
            self.controller.add_manual_entry({**self.values, "items": ()})

    def test_historical_single_product_is_transparently_one_item(self):
        values = {**self.values}
        values.pop("items")
        values.update(armazon="500000", cristal="250000", total="750000", fecha_entrega="")
        _, entry = self.controller.add_manual_entry(values)
        self.assertEqual(len(entry.effective_items), 1)
        self.assertEqual(entry.effective_items[0].subtotal, 750000)

    def test_single_product_sale_can_be_saved_directly_from_visible_form(self):
        values = {
            **self.values,
            "caja_inicial": "1.500.000", "descripcion": "Prueba Uno",
            "cliente_documento": "", "sobre": "123", "arm_org": "Armazón",
            "cod": "456", "armazon": "1.500.000", "cristal": "250.000",
            "total": "1.750.000", "efectivo": "1.000.000",
            "tarjeta_cheque": "", "transferencia": "", "saldo": "750.000",
            "notas": "",
        }
        values["items"] = completar_items_para_guardar(values, ())

        day, entry = self.controller.add_manual_entry(values)
        reloaded = self.controller.load_day("12-08-2026", "PC")

        self.assertEqual(len(day.entries), 1)
        self.assertEqual(len(entry.items), 1)
        self.assertEqual(entry.total, 1_750_000)
        self.assertEqual(entry.balance, "750.000")
        self.assertEqual(len(reloaded.entries), 1)
        self.assertEqual(len(reloaded.entries[0].items), 1)
        self.assertEqual(reloaded.entries[0].total, 1_750_000)

    def test_initial_cash_uses_paraguayan_thousands_separator(self):
        class VisibleEntry:
            def __init__(self):
                self.value = "1500000"

            def get(self):
                return self.value

            def delete(self, _start, _end):
                self.value = ""

            def insert(self, _index, value):
                self.value = value

        field = VisibleEntry()
        self.assertEqual(escribir_importe_formateado(field, field.get()), "1.500.000")
        self.assertEqual(field.get(), "1.500.000")
        self.assertEqual(escribir_importe_formateado(field, 1_500_000), "1.500.000")

    def test_single_item_sale_with_optional_fields_blank_can_save(self):
        values = {**self.values, "ordenes": "", "cuotas": "", "tarjeta_cheque": "",
                  "transferencia": "", "notas": "", "cliente_documento": ""}
        values.update(arm_org="Armazon", cod="100234", armazon="280.000",
                      cristal="350.000", total="630.000", efectivo="400.000",
                      saldo="230.000")
        values["items"] = completar_items_para_guardar(values, ())
        _, entry = self.controller.add_manual_entry(values)
        self.assertEqual((entry.total, entry.cash, entry.balance), (630000, 400000, "230.000"))

    def test_single_item_visible_product_is_materialized_on_save(self):
        values = {**self.values, "arm_org": "Armazon", "cod": "100234",
                  "armazon": "280.000", "cristal": "350.000"}
        items = completar_items_para_guardar(values, ())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].subtotal, 630000)
        self.assertIs(completar_items_para_guardar(values, items)[0], items[0])

    def test_save_validation_errors_are_visible(self):
        with patch("CajaDiaria.messagebox.showerror") as visible_error:
            mostrar_error_guardado(InvalidCashDayError("Seleccione la vendedora."))
        visible_error.assert_called_once()
        self.assertIn("Seleccione la vendedora.", visible_error.call_args.args[1])

    def test_form_reader_ignores_non_input_widgets(self):
        class Field:
            def get(self): return " Sol "
        class Button: pass
        self.assertEqual(leer_valores_formulario({"descripcion": Field(), "accion_gasto": Button()}),
                         {"descripcion": "Sol"})


if __name__ == "__main__":
    unittest.main()
