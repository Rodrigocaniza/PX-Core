import unittest

from modulos.caja_diaria.ui.privacy import FinancialPrivacy


class FinancialPrivacyTests(unittest.TestCase):
    def test_manual_hide_show_and_no_automatic_reveal(self):
        now = [0.0]
        privacy = FinancialPrivacy(clock=lambda: now[0])
        privacy.hide()
        self.assertEqual(privacy.display("Gs. 500.000"), privacy.MASK)
        privacy.activity()
        self.assertTrue(privacy.hidden)
        privacy.show()
        self.assertEqual(privacy.display("Gs. 500.000"), "Gs. 500.000")

    def test_timeout_hides_and_activity_only_restarts_timer(self):
        now = [0.0]
        privacy = FinancialPrivacy(timeout_seconds=120, clock=lambda: now[0])
        now[0] = 121
        self.assertTrue(privacy.check_timeout())
        privacy.activity()  # mouse/keyboard activity does not reveal
        self.assertTrue(privacy.hidden)


if __name__ == "__main__":
    unittest.main()
