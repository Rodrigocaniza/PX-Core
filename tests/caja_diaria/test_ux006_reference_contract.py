from __future__ import annotations

import inspect
import unittest

import CajaDiaria


class CashDayUX006ReferenceContractTests(unittest.TestCase):
    def test_reference_macro_layout_and_controls_are_explicit(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        for text in (
            'BC Caja Diaria',
            'Óptica Central',
            '"Movimientos del día"',
            '"Buscar movimiento…"',
            '("Todos", "Ventas", "Gastos", "Pendientes")',
            '"CAJA INICIAL"',
            '"VENTA TOTAL"',
            '"EFECTIVO"',
            '"TARJ. / TRANSF."',
            '"GASTOS"',
            '"SALDO PEND."',
            '"EFECTIVO FINAL"',
            'cabecera.place(x=4, y=2)',
            'bloque_producto.place(x=4, y=128)',
            'toolbar_movimientos.place(x=562, y=128)',
            'resumen_dia.place(x=4, y=553)',
        ):
            self.assertIn(text, source)

    def test_all_operational_fields_remain_mapped(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        self.assertIn('PRODUCTO_TRABAJO', source)
        self.assertIn('COBRO_PAGO', source)
        self.assertEqual(len(CajaDiaria.COLUMNAS_OPERATIVAS), 15)


if __name__ == "__main__":
    unittest.main()
