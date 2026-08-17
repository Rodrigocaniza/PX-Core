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
            '"#EAF2FB"',
            '"#FFFFFF"',
            '"Caja inicial"',
            'resumen_compacto',
            # El rótulo del estado lo compone `estado_dia` (RC29) y el port de
            # Apertura le suma la hora; sigue siendo "Estado: " en español.
            'f"Estado: {estado_dia(cash_day)}"',
            'sufijo_hora_apertura(cash_day)',
            'Guardar venta  —  F9',
            'pestañas._segmented_button.grid_forget()',
            'boton_cancelar.pack_forget()',
        ):
            self.assertIn(text, source)
        # RC18 movio la definicion de los KPI a constantes de modulo; el
        # contrato se verifica sobre ellas en vez de sobre el texto fuente.
        self.assertIn(("esperado", "Esperado", "#0F5FB9"), CajaDiaria.KPI_PRINCIPALES)
        self.assertNotIn("Resumen para arqueo", source)


    def test_close_and_count_show_the_operational_breakdown(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        for text in (
            'solicitar_conteo_obligatorio("Arqueo de apertura")',
            '"Arqueo de cierre"',
            'esperado=totales.expected_cash',
            'f"Efectivo contado:',
            'f"Diferencia:',
        ):
            self.assertIn(text, source)
        self.assertNotIn("Resumen para arqueo", source)

if __name__ == "__main__":
    unittest.main()
