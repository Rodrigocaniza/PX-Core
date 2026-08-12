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
            'cabecera.place(x=4, y=4)',
            'formulario.place(x=4, y=146)',
            'toolbar_movimientos.place(x=590, y=146)',
            'pie_movimientos.place(x=590, y=512)',
            'resumen_dia.place(x=4, y=554)',
            'acciones_primarias = ctk.CTkFrame(acciones',
            'iconos_kpi = {',
            'recalcular_total_visible',
            'formulario.grid_propagate(False)',
            'acciones.pack_propagate(False)',
            'resumen_dia.pack_propagate(False)',
            'marco_grilla.grid_propagate(False)',
            'grilla_caja.bind("<MouseWheel>"',
            '"Efectivo contado"',
            '"Diferencia"',
        ):
            self.assertIn(text, source)

    def test_visible_money_format_and_total_rule(self):
        self.assertEqual(CajaDiaria.formatear_importe_ui("1250000"), "1.250.000")
        self.assertEqual(CajaDiaria.formatear_importe_ui("1.250.000"), "1.250.000")
        self.assertEqual(CajaDiaria.formatear_importe_ui(""), "")
        self.assertEqual(
            CajaDiaria.sumar_importes_formulario("1.250.000", "1.450.000"),
            2700000,
        )
    def test_all_operational_fields_remain_mapped(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        self.assertIn('PRODUCTO_TRABAJO', source)
        self.assertIn('COBRO_PAGO', source)
        self.assertEqual(len(CajaDiaria.COLUMNAS_OPERATIVAS), 15)


if __name__ == "__main__":
    unittest.main()
