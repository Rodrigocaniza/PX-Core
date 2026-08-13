import unittest
from pathlib import Path

from CajaDiaria import COLUMNAS_OPERATIVAS, perfil_visual


SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


class OperatorUXContractTests(unittest.TestCase):
    def test_only_three_global_financial_kpis_are_primary(self):
        for title in ("VENTA TOTAL DEL DÍA", "EFECTIVO", "SALDO PENDIENTE"):
            self.assertEqual(SOURCE.count(f'"{title}"'), 1)
        for title in ("TARJ. / TRANSF.", "EFECTIVO FINAL"):
            self.assertNotIn(title, SOURCE)

    def test_full_hd_uses_three_operator_blocks(self):
        for title in ("CLIENTE Y COMPROBANTE", "DETALLE DE VENTA", "PAGO"):
            self.assertIn(f'"{title}"', SOURCE)
        self.assertIn("columnas_bloque = 3", SOURCE)

    def test_draft_has_own_non_persistent_grid(self):
        self.assertIn('text="VENTA EN CURSO"', SOURCE)
        self.assertIn('grilla_items.pack(in_=panel_items, fill="both"', SOURCE)
        self.assertNotIn('iid="draft"', SOURCE)

    def test_primary_actions_belong_to_their_operator_panels(self):
        self.assertEqual(SOURCE.count('text="+ Agregar artículo"'), 1)
        self.assertIn('detalle_venta = secciones_widgets["DETALLE DE VENTA"]', SOURCE)
        self.assertIn('pago = secciones_widgets["PAGO"]', SOURCE)
        self.assertIn('text="TOTAL DE LA VENTA"', SOURCE)
        self.assertIn('panel_total_draft.grid(row=0, column=1', SOURCE)

    def test_operator_fields_are_vertical_rows_in_bordered_panels(self):
        self.assertIn('border_width=2, border_color="#8FB3D9"', SOURCE)
        self.assertIn('enumerate(columnas, start=1)', SOURCE)
        self.assertIn('campo.grid(row=fila_campo, column=1', SOURCE)

    def test_movements_are_reduced_to_operational_columns(self):
        self.assertEqual(
            [key for key, _, _ in COLUMNAS_OPERATIVAS],
            ["hora", "descripcion", "cliente_telefono", "tipo_resumen", "sobre",
             "total", "saldo", "vendedora", "estado"],
        )

    def test_privacy_only_masks_global_kpi_refresh(self):
        self.assertIn("# El modo privacidad sólo afecta KPIs globales", SOURCE)
        refresh = SOURCE[SOURCE.index("def refrescar_items"):SOURCE.index("def agregar_producto")]
        self.assertNotIn("privacidad.display", refresh)

    def test_both_profiles_remain_responsive(self):
        full = perfil_visual(1920, 1080)
        compact = perfil_visual(1366, 768)
        self.assertEqual((full["nombre"], compact["nombre"]), ("full-hd", "compacto"))
        self.assertGreater(full["campo_alto"], compact["campo_alto"])
        self.assertGreater(full["fila"], compact["fila"])

    def test_sqlite_upsert_regression_marker_remains(self):
        repository = Path("modulos/caja_diaria/infrastructure/sqlite_repository.py").read_text(encoding="utf-8")
        self.assertIn("ON CONFLICT(id) DO UPDATE SET", repository)
        self.assertNotIn("DELETE FROM cash_entries WHERE cash_day_id = ?", repository)


if __name__ == "__main__":
    unittest.main()
