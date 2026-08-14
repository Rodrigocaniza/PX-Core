from __future__ import annotations

import inspect
import unittest

import CajaDiaria


class CashDayUX002ContractTests(unittest.TestCase):
    def test_capture_is_split_into_product_and_payment_rows(self):
        self.assertEqual(len(CajaDiaria.PRODUCTO_TRABAJO), 8)
        self.assertEqual(len(CajaDiaria.COBRO_PAGO), 8)
        self.assertIn(("ordenes", "Orden / Convenio", 150), CajaDiaria.COBRO_PAGO)
        self.assertIn(("cuotas", "Cuotas", 75), CajaDiaria.COBRO_PAGO)
        self.assertEqual(len(CajaDiaria.COLUMNAS_OPERATIVAS), 13)

    def test_window_shortcuts_actions_footer_and_target_are_explicit(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        for contract_text in (
            'ventana.geometry(f"{ancho_logico}x{alto_logico}+{area_x}+{area_y}")',
            '"CLIENTE Y COMPROBANTE"',
            '"DETALLE DE VENTA"',
            '"PAGO"',
            '"VENTA EN CURSO"',
            '"acciones"',
            '"<F2>"',
            '"<F3>"',
            '"<F9>"',
            '"<F12>"',
            'resolve_data_paths().root',
        ):
            self.assertIn(contract_text, source)
        self.assertEqual(CajaDiaria.perfil_visual(1366, 768)["ventana"], "1366x768")


if __name__ == "__main__":
    unittest.main()
