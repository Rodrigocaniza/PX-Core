import unittest

from CajaDiaria import perfil_visual


class FullHDLayoutContractTests(unittest.TestCase):
    def test_compact_profile_preserves_validated_1366_metrics(self):
        compact = perfil_visual(1366, 768)
        self.assertEqual(compact["nombre"], "compacto")
        self.assertEqual(compact["ventana"], "1366x768")
        self.assertEqual((compact["fuente"], compact["fila"]), (9, 27))
        self.assertEqual((compact["izquierda"], compact["grilla_alto"]), (570, 354))

    def test_full_hd_uses_extra_space_for_readability_and_movements(self):
        compact = perfil_visual(1366, 768)
        full = perfil_visual(1920, 1080)
        self.assertEqual(full["nombre"], "full-hd")
        for metric in ("fuente", "fuente_label", "fuente_seccion", "fuente_kpi",
                       "campo_alto", "fila", "izquierda", "grilla_alto"):
            self.assertGreater(full[metric], compact[metric], metric)
        self.assertGreaterEqual(full["contenido_ancho"], 1880)
        self.assertGreaterEqual(full["grilla_alto"] // full["fila"], 15)

    def test_dpi_is_not_applied_twice(self):
        self.assertEqual(perfil_visual(1920, 1080, 1.0), perfil_visual(1920, 1080, 1.25))

    def test_scrollbars_and_privacy_contract_remain_present(self):
        source = open("CajaDiaria.py", encoding="utf-8").read()
        self.assertIn('orient="horizontal", command=grilla_caja.xview', source)
        self.assertIn('orient="vertical", command=grilla_caja.yview', source)
        self.assertIn("FinancialPrivacy(timeout_seconds=300)", source)
        self.assertIn("resumen_venta_en_curso", source)


if __name__ == "__main__":
    unittest.main()
