import unittest

from modulos.caja_diaria.ui.privacy import FinancialPrivacy


class UXControlPrivacyTests(unittest.TestCase):
    def test_timeout_is_five_minutes_and_activity_resets_without_reveal(self):
        now = [0.0]
        privacy = FinancialPrivacy(clock=lambda: now[0])
        self.assertEqual(privacy.timeout_seconds, 300)
        now[0] = 299
        self.assertFalse(privacy.check_timeout())
        privacy.activity()
        now[0] = 598
        self.assertFalse(privacy.check_timeout())
        now[0] = 599
        self.assertTrue(privacy.check_timeout())
        privacy.activity()
        self.assertTrue(privacy.hidden)

    def test_form_and_draft_amounts_are_not_sent_through_privacy_display(self):
        source = open("CajaDiaria.py", encoding="utf-8").read()
        self.assertIn('"total": formatear_monto(total)', source)
        self.assertIn("formatear_monto(item.subtotal)", source)
        refresh = source[source.index("def refrescar_items"):source.index("def agregar_producto")]
        self.assertNotIn("privacidad.display", refresh)
        self.assertIn("👁 Mostrar totales", source)
        self.assertIn("👁 Ocultar totales", source)


if __name__ == "__main__":
    unittest.main()
