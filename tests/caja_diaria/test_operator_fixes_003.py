from pathlib import Path
import unittest

import CajaDiaria


SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


class OperatorFixes003ContractTests(unittest.TestCase):
    def test_draft_rows_render_real_item_values_in_expanding_grid(self):
        self.assertIn('columnas_items = ("producto", "codigo", "tipo", "armazon", "cristal", "subtotal")', SOURCE)
        self.assertIn('panel_items.grid_rowconfigure(0, weight=1)', SOURCE)
        self.assertIn('grilla_items.grid(row=0, column=0, sticky="nsew")', SOURCE)
        for expression in (
            "item.description", "item.code", "item.no_cost",
            "formatear_monto(item.frame_final_price)", "formatear_monto(item.lens_final_price)",
            "formatear_monto(item.subtotal)",
        ):
            self.assertIn(expression, SOURCE)

    def test_movement_headers_and_rows_share_one_canonical_spec(self):
        keys = [key for key, _title, _width, _anchor in CajaDiaria.MOVEMENT_COLUMN_SPECS]
        self.assertEqual(keys, [key for key, _title, _width in CajaDiaria.COLUMNAS_OPERATIVAS])
        self.assertIn("for clave, etiqueta, ancho, anchor in MOVEMENT_COLUMN_SPECS", SOURCE)
        self.assertIn("grilla_caja.heading(clave, text=etiqueta, anchor=anchor)", SOURCE)
        self.assertIn("stretch=False, anchor=anchor", SOURCE)

    def test_payment_restores_order_and_installments(self):
        self.assertIn(("ordenes", "Orden / Convenio", 150), CajaDiaria.COBRO_PAGO)
        self.assertIn(("cuotas", "Cuotas", 75), CajaDiaria.COBRO_PAGO)
        self.assertIn('"ordenes", "monto_convenio",', SOURCE)
        self.assertIn('"cuotas", "saldo", "notas"', SOURCE)

    def test_orders_table_exposes_persisted_phone(self):
        # El port de Pedidos quitó CI/RUC de la grilla; el teléfono persistido sigue visible.
        self.assertIn(("telefono", "Teléfono", 125, "center"), CajaDiaria.ORDER_COLUMN_SPECS)
        self.assertIn("pedido.customer_phone, pedido.envelope", SOURCE)

    def test_responsive_profiles_and_native_chrome_contract_remain(self):
        self.assertEqual(CajaDiaria.perfil_visual(1366, 768)["nombre"], "compacto")
        self.assertEqual(CajaDiaria.perfil_visual(1920, 1080)["nombre"], "full-hd")
        self.assertNotIn("overrideredirect(True)", SOURCE)
        self.assertNotIn('attributes("-fullscreen", True)', SOURCE)


if __name__ == "__main__":
    unittest.main()
