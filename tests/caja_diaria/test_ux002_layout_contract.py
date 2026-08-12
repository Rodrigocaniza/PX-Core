from __future__ import annotations

import inspect
import unittest

import CajaDiaria


class CashDayUX002ContractTests(unittest.TestCase):
    def test_capture_is_split_into_product_and_payment_rows(self):
        self.assertEqual(CajaDiaria.PRODUCTO_TRABAJO, CajaDiaria.COLUMNAS_OPERATIVAS[:8])
        self.assertEqual(CajaDiaria.COBRO_PAGO, CajaDiaria.COLUMNAS_OPERATIVAS[8:])
        self.assertEqual(len(CajaDiaria.PRODUCTO_TRABAJO), 8)
        self.assertEqual(len(CajaDiaria.COBRO_PAGO), 7)

    def test_window_shortcuts_actions_footer_and_target_are_explicit(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        for contract_text in (
            'geometry("1366x768")',
            '"Cliente y comprobante"',
            '"Detalle de venta"',
            '"Importes"',
            '"Cobro"',
            '"Notas y gasto"',
            '"acciones"',
            '"<F2>"',
            '"<F3>"',
            '"<F9>"',
            '"<F12>"',
            'Resumen para arqueo',
            'resolve_data_paths().root',
        ):
            self.assertIn(contract_text, source)


if __name__ == "__main__":
    unittest.main()
