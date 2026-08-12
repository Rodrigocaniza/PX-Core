from __future__ import annotations

import inspect
import unittest

import CajaDiaria


class CashDayUX004VisualContractTests(unittest.TestCase):
    def test_dense_grid_columns_fit_the_initial_1366_view(self):
        grid_width = sum(width for _, _, width in CajaDiaria.COLUMNAS_OPERATIVAS) + 105
        self.assertLessEqual(grid_width, 1330)

    def test_high_fidelity_elements_are_explicit(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        for text in (
            '"#F3F6FA"',
            '"#FFFFFF"',
            '"CAJA INICIAL"',
            '"VENTA TOTAL"',
            '"ABIERTA"',
            '"CERRADA"',
            'Guardar venta  —  F9',
            'Resumen para arqueo',
            'iconos_kpi = {',
            'pestañas._segmented_button.grid_forget()',
            'boton_cancelar.pack_forget()',
        ):
            self.assertIn(text, source)


    def test_close_and_count_show_the_operational_breakdown(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        for text in (
            '"Caja inicial: "',
            '"Ventas en efectivo: "',
            '"Tarjeta / transferencia: "',
            '"Gastos: "',
            '"Efectivo esperado: "',
            'f"Efectivo contado:',
            'f"Diferencia:',
        ):
            self.assertIn(text, source)

if __name__ == "__main__":
    unittest.main()
