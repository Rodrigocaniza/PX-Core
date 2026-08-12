import inspect
import unittest

from modulos.comunicaciones.ui import inbox_app


class InboxUIContractTests(unittest.TestCase):
    def test_window_targets_1366_by_768_and_has_three_operational_columns(self):
        source = inspect.getsource(inbox_app.InboxWindow)
        self.assertIn('self.geometry("1366x768")', source)
        for feature in ("FILTROS", "CONVERSACIONES", "Enviar (simulado)", "Asignar", "Resolver"):
            self.assertIn(feature, source)

    def test_demo_data_is_explicitly_labeled(self):
        source = inspect.getsource(inbox_app.InboxWindow)
        self.assertIn("Cargar datos DEMO", source)
        self.assertIn("proveedor simulado", source)

    def test_filters_are_labeled_and_statuses_have_distinct_colors(self):
        source = inspect.getsource(inbox_app.InboxWindow)
        for label in ('text="Negocio"', 'text="Sucursal"', 'text="Estado"'):
            self.assertIn(label, source)
        self.assertEqual(set(inbox_app.STATUS_COLORS), set(inbox_app.ConversationStatus))
        self.assertEqual(3, len(set(inbox_app.STATUS_COLORS.values())))
