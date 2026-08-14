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
            '("Todos", "Ventas", "Salidas", "Pendientes")',
            '"Caja inicial"',
            'resumen_compacto',
            '"Tarj./Transf."',
            '"Entregado"',
            'cabecera.configure(width=ancho_actual, height=alto_cab)',
            'formulario.configure(width=ancho_actual, height=alto_form_actual)',
            'formulario.place(x=x_actual, y=y_form_actual)',
            'toolbar_movimientos.place',
            'pie.configure(width=ancho_actual, height=alto_pie_actual)',
            'acciones_primarias = ctk.CTkFrame(acciones',
            'etiquetas_kpi["esperado"]',
            'recalcular_total_visible',
            'formulario.grid_propagate(False)',
            'width=ancho_derecho_actual, height=alto_observaciones',
            'zona_secundaria.configure(width=ancho_izquierdo_actual',
            'marco_grilla.configure(width=ancho_actual, height=alto_grid)',
            'marco_grilla.grid_propagate(False)',
            'grilla_caja.bind("<MouseWheel>"',
            '"Estado: ABIERTO"',
            '"Estado: CERRADO"',
            'controller.add_outflow(',
            'text="SALIDA DE CAJA"',
            'text="Guardar salida"',
            '"Efectivo esperado por sistema: —"',
            'describir_diferencia_arqueo',
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
    def test_non_cash_payment_methods_are_combined_for_persistence(self):
        self.assertEqual(
            CajaDiaria.sumar_medios_no_efectivo("500.000", "250.000"), 750000
        )

    def test_pending_balance_is_automatic_and_never_negative(self):
        self.assertEqual(
            CajaDiaria.calcular_saldo_pendiente(
                "1.750.000", "1.000.000", "500.000", "0"
            ),
            250000,
        )
        self.assertEqual(
            CajaDiaria.calcular_saldo_pendiente("100", "200", "0", "0"), 0
        )

    def test_cash_count_messages_cover_conforming_shortage_and_surplus(self):
        self.assertEqual(CajaDiaria.describir_diferencia_arqueo(0)[0], "ARQUEO CONFORME")
        self.assertEqual(CajaDiaria.describir_diferencia_arqueo(-50000)[1], "Faltan 50.000")
        self.assertEqual(CajaDiaria.describir_diferencia_arqueo(50000)[1], "Sobran 50.000")
        self.assertEqual(CajaDiaria.formatear_diferencia_ui(50000), "+50.000")

    def test_all_operational_fields_remain_mapped(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        self.assertIn('PRODUCTO_TRABAJO', source)
        self.assertIn('COBRO_PAGO', source)
        self.assertEqual(len(CajaDiaria.COLUMNAS_OPERATIVAS), 13)


if __name__ == "__main__":
    unittest.main()
