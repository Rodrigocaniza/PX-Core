import unittest

from CajaDiaria import resumen_venta_en_curso
from modulos.caja_diaria.domain.models import SaleDraft, SaleItem
from modulos.caja_diaria.ui.privacy import FinancialPrivacy


class MultiItemDraftUXTests(unittest.TestCase):
    def setUp(self):
        self.items = [
            SaleItem(description="Armazón X", frame_price=500000, lens_price=250000),
            SaleItem(description="Lente de sol", frame_price=300000),
            SaleItem(description="Armazón Y", frame_price=600000, lens_price=200000),
        ]
        self.privacy = FinancialPrivacy(timeout_seconds=120)

    def test_draft_multi_item_appears_in_movements_summary(self):
        result = resumen_venta_en_curso("Juan Pérez", self.items, self.privacy)
        self.assertEqual((result["cantidad"], result["total"], result["estado"]),
                         (3, "1.850.000", "EN CURSO"))

    def test_draft_does_not_persist_and_clear_removes_it(self):
        draft = SaleDraft(list(self.items))
        self.assertEqual(draft.total, 1_850_000)
        draft.items.clear()
        self.assertEqual(draft.total, 0)

    def test_edit_and_remove_update_total(self):
        draft = SaleDraft(list(self.items))
        draft.edit(1, SaleItem(description="Lente", frame_price=400000))
        self.assertEqual(draft.total, 1_950_000)
        draft.remove(0)
        self.assertEqual(draft.total, 1_200_000)

    def test_privacy_masks_draft_amounts(self):
        self.privacy.hide()
        result = resumen_venta_en_curso("Juan", self.items, self.privacy)
        self.assertNotIn("1.850.000", result["total"])


if __name__ == "__main__":
    unittest.main()
