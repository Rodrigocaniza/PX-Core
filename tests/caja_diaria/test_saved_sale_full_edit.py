import inspect
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import CajaDiaria
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import SaleItem


class SavedSaleFullEditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.controller = build_cash_day_controller(Path(self.temp.name) / "edit.sqlite3")
        self.first = SaleItem(
            description="Armazón A", code="A-1", item_type="Metal",
            frame_price=300_000, lens_price=200_000, laboratory="Lab A",
            prescription_doctor="Dra. A",
        )
        self.second = SaleItem(
            description="Armazón B", code="B-2", item_type="Acetato",
            frame_price=250_000, lens_price=250_000, laboratory="Lab B",
            prescription_doctor="Dr. B",
        )
        self.values = {
            "fecha": "13-08-2026", "unidad": "PC", "caja_inicial": "500000",
            "descripcion": "Cliente edición", "cliente_telefono": "0981123456",
            "cliente_documento": "1234567", "sobre": "S-10",
            "fecha_entrega": "20-08-2026", "vendedora": "ANA",
            "notas": "Observación original", "arm_org": "", "cod": "",
            "armazon": "", "cristal": "", "laboratorio": "", "receta_dr": "",
            "total": "1000000", "efectivo": "400000", "tarjeta_cheque": "0",
            "ordenes": "CONVENIO TEST", "monto_convenio": "600000",
            "cuotas": "2", "saldo": "0", "gastos": "0",
            "items": (self.first, self.second),
        }
        _, self.entry = self.controller.add_manual_entry(self.values)

    def tearDown(self):
        self.controller.service.repository.close()
        self.temp.cleanup()

    def update(self, items, **overrides):
        values = {**self.values, "items": tuple(items), **overrides}
        return self.controller.update_manual_entry(
            self.entry.id, values, reason="Corrección solicitada", user="operadora"
        )[1]

    def reload(self):
        return self.controller.load_day("13-08-2026", "PC").entries[0]

    def test_case_1_edit_two_products_and_reopen(self):
        changed = replace(self.first, frame_price=350_000)
        saved = self.update(
            (changed, self.second), total="1050000", monto_convenio="650000"
        )
        reopened = self.reload()
        self.assertEqual(saved.id, self.entry.id)
        self.assertEqual([item.id for item in reopened.items], [self.first.id, self.second.id])
        self.assertEqual(reopened.items[0].frame_price, 350_000)
        self.assertEqual(reopened.total, 1_050_000)
        audit = self.controller.service.repository.list_entry_revisions(self.entry.id)[-1]
        self.assertEqual(audit["snapshot"]["audit"], {
            "reason": "Corrección solicitada", "user": "operadora"
        })
        self.assertEqual(len(audit["snapshot"]["item_changes"]["modified"]), 1)

    def test_rc5_long_prescription_round_trip_without_truncation(self):
        prescription = "\n".join(
            f"Línea clínica {index}: OD +1.50 / OI +1.25 / observación completa"
            for index in range(1, 31)
        )
        self.update((self.first, self.second), notas=prescription)
        reopened = self.reload()
        self.assertEqual(reopened.observations, prescription)
        self.assertEqual(reopened.source_reference, prescription)
    def test_case_2_remove_product_recalculates_and_persists(self):
        reopened = self.update(
            (self.first,), total="500000", efectivo="200000", monto_convenio="300000"
        )
        self.assertEqual((reopened.total, len(self.reload().items)), (500_000, 1))
        changes = self.controller.service.repository.list_entry_revisions(self.entry.id)[-1]
        self.assertEqual(changes["snapshot"]["item_changes"]["removed"][0]["id"], self.second.id)

    def test_case_3_add_third_product_without_duplicate_movement(self):
        third = SaleItem(description="Cristal extra", code="C-3", lens_price=200_000)
        self.update(
            (self.first, self.second, third), total="1200000", monto_convenio="800000"
        )
        day = self.controller.load_day("13-08-2026", "PC")
        self.assertEqual(len(day.entries), 1)
        self.assertEqual(day.entries[0].id, self.entry.id)
        self.assertEqual(len(day.entries[0].items), 3)

    def test_case_4_edit_action_and_double_click_share_loader(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        edit = source[source.index("def editar_seleccionado"):source.index("def cancelar_edicion")]
        self.assertIn("cargar_para_editar(cash_day, entry)", edit)
        self.assertIn('grilla_caja.bind("<Double-1>", editar_seleccionado)', source)
        loader = source[source.index("def cargar_para_editar"):source.index("def anular_desde_historial")]
        self.assertIn("items_venta[:] = list(entry.effective_items)", loader)
        self.assertIn('"cliente_telefono": entry.customer_phone', loader)
        self.assertIn('"monto_convenio": entry.agreement_amount', loader)

    def test_case_5_mixed_payment_and_agreement_are_preserved(self):
        saved = self.update((self.first, self.second), cuotas="4")
        self.assertEqual(
            (saved.total, saved.cash, saved.card_check, saved.agreement_amount,
             saved.installments, saved.balance),
            (1_000_000, 400_000, 0, 600_000, "4", "0"),
        )
        reopened = self.reload()
        self.assertEqual(reopened.installments, "4")
        with self.assertRaisesRegex(InvalidCashDayError, "excede"):
            self.update(
                (self.first,), total="500000", efectivo="400000", monto_convenio="200000"
            )

    def test_case_6_cancel_local_changes_does_not_persist(self):
        draft = list(self.entry.effective_items)
        draft.pop()
        draft[0] = replace(draft[0], frame_price=1)
        reopened = self.reload()
        self.assertEqual(len(reopened.items), 2)
        self.assertEqual(reopened.items[0].frame_price, 300_000)
        self.assertEqual(reopened.revision, 0)

    def test_movement_grid_exposes_installments_without_horizontal_scroll_at_1366(self):
        expected = [
            "hora", "descripcion", "cliente_telefono", "tipo_resumen", "sobre",
            "total", "efectivo", "tarjeta_transferencia", "monto_convenio",
            "cuotas", "saldo", "vendedora", "estado",
        ]
        self.assertEqual([column[0] for column in CajaDiaria.MOVEMENT_COLUMN_SPECS], expected)
        self.assertEqual(
            next(column[2] for column in CajaDiaria.MOVEMENT_COLUMN_SPECS
                 if column[0] == "descripcion"),
            180,
        )
        rendered_width = sum(
            max(width, 65) for _key, _title, width, _anchor
            in CajaDiaria.MOVEMENT_COLUMN_SPECS
        ) + 105
        self.assertLessEqual(rendered_width, 1342)
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        row_values = source[source.index("def valores_fila"):source.index("def refrescar_grilla")]
        self.assertIn("importe(entry.cash)", row_values)
        self.assertIn("importe(entry.card_check)", row_values)
        self.assertIn("entry.installments", row_values)
    def test_toby_agreement_is_not_customer_balance_and_counts_as_sale(self):
        toby_item = SaleItem(description="Producto Toby", frame_price=350_000)
        values = {
            **self.values,
            "descripcion": "Toby",
            "efectivo": "0",
            "tarjeta_cheque": "0",
            "ordenes": "Convenio Toby",
            "monto_convenio": "350000",
            "cuotas": "10",
            "saldo": "350000",
            "items": (toby_item,),
        }
        values["fecha"] = "14-08-2026"
        _, created = self.controller.add_manual_entry(values)
        self.assertEqual(
            (created.total, created.cash, created.card_check, created.agreement_amount,
             created.installments, created.balance, created.client_balance_amount),
            (350_000, 0, 0, 350_000, "10", "0", 0),
        )
        day = self.controller.load_day("14-08-2026", "PC")
        totals = day.totals()
        self.assertEqual(totals.total, 350_000)
        self.assertEqual((totals.cash, totals.card_check), (0, 0))
        self.assertEqual(totals.expected_cash, 500_000)
        cash_count = day.count_cash({100_000: 5})
        self.assertEqual((cash_count.expected_total, cash_count.difference), (500_000, 0))
        reopened = day.entries[0]
        self.assertEqual((reopened.agreement_amount, reopened.installments,
                          reopened.client_balance_amount), (350_000, "10", 0))

        edited_values = {**values, "cuotas": "12", "saldo": "350000"}
        _, edited = self.controller.update_manual_entry(
            created.id, edited_values, reason="Cambio de cuotas", user="operadora"
        )
        self.assertEqual((edited.installments, edited.balance), ("12", "0"))
        self.assertEqual(
            self.controller.load_day("14-08-2026", "PC").entries[0].installments,
            "12",
        )

    def test_grid_and_daily_summary_keep_agreement_out_of_balance_and_cash(self):
        source = inspect.getsource(CajaDiaria.abrir_caja_diaria)
        row_values = source[source.index("def valores_fila"):source.index("def refrescar_grilla")]
        daily = source[source.index("def actualizar_estado"):source.index("def abrir_o_consultar")]
        self.assertIn("importe(entry.agreement_amount), entry.installments", row_values)
        self.assertIn("importe(entry.client_balance_amount)", row_values)
        self.assertIn("saldo_pendiente += entry.client_balance_amount", daily)
        self.assertIn("cobrar_convenio += entry.agreement_amount or 0", daily)
        self.assertNotIn("agreement_amount", inspect.getsource(type(self.controller.load_day(
            "13-08-2026", "PC"
        )).totals))
    def test_migration_archives_and_corrects_duplicated_agreement_balance(self):
        import sqlite3

        connection = sqlite3.connect(self.controller.service.repository.database_path)
        try:
            connection.execute(
                "UPDATE cash_entries SET balance_text = '600000' WHERE id = ?",
                (self.entry.id,),
            )
            connection.execute("DELETE FROM schema_migrations WHERE version = '011'")
            connection.execute(
                "DELETE FROM agreement_balance_corrections WHERE entry_id = ?",
                (self.entry.id,),
            )
            connection.commit()
        finally:
            connection.close()
        self.controller.service.repository.migrate()
        connection = sqlite3.connect(self.controller.service.repository.database_path)
        try:
            corrected = connection.execute(
                "SELECT balance_text FROM cash_entries WHERE id = ?", (self.entry.id,)
            ).fetchone()[0]
            archived = connection.execute(
                """SELECT previous_balance_text, corrected_balance_text
                   FROM agreement_balance_corrections WHERE entry_id = ?""",
                (self.entry.id,),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(corrected, "0")
        self.assertEqual(archived, ("600000", "0"))
    def test_empty_edited_sale_is_rejected(self):
        with self.assertRaisesRegex(InvalidCashDayError, "sin productos"):
            self.update(())


if __name__ == "__main__":
    unittest.main()
