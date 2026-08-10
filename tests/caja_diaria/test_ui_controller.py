from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import CashDayClosedError, InvalidCashDayError, InvalidMoneyError
from modulos.caja_diaria.ui.controller import friendly_error


class CashDayUIControllerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "ui.sqlite3"
        self.controller = build_cash_day_controller(self.database)

    def tearDown(self):
        self.controller.service.repository.close()
        self.tempdir.cleanup()

    @staticmethod
    def manual_values(**overrides):
        values = {
            "fecha": "02-08-2026",
            "unidad": "PC",
            "caja_inicial": "500.000",
            "descripcion": "CLIENTE",
            "sobre": "S-1",
            "arm_org": "ARM",
            "cod": "A1",
            "armazon": "300000",
            "cristal": "200000",
            "receta_dr": "DR A",
            "total": "500.000",
            "efectivo": "300.000",
            "tarjeta_cheque": "200.000",
            "ordenes": "",
            "cuotas": "",
            "saldo": "cancelado",
            "gastos": "",
        }
        values.update(overrides)
        return values

    def test_manual_flow_persists_and_reloads_with_new_controller(self):
        day, entry = self.controller.add_manual_entry(self.manual_values())
        self.assertEqual(day.totals().expected_cash, 800000)
        self.assertEqual(entry.balance, "cancelado")

        self.controller.service.repository.close()
        reloaded_controller = build_cash_day_controller(self.database)
        try:
            reloaded = reloaded_controller.load_day("2026-08-02", "pc")
            self.assertEqual(reloaded.id, day.id)
            self.assertEqual(len(reloaded.entries), 1)
            self.assertEqual(reloaded.entries[0].description, "CLIENTE")
            self.assertEqual(reloaded.totals().total, 500000)
        finally:
            reloaded_controller.service.repository.close()

    def test_initial_cash_is_required_only_when_day_does_not_exist(self):
        with self.assertRaises(InvalidCashDayError):
            self.controller.open_or_load_day("02-08-2026", "PC", "")
        self.controller.open_or_load_day("02-08-2026", "PC", "100000")
        loaded = self.controller.open_or_load_day("02-08-2026", "PC", "")
        self.assertEqual(loaded.opening_cash, 100000)

    def test_invalid_input_does_not_create_day(self):
        with self.assertRaises(InvalidMoneyError):
            self.controller.add_manual_entry(self.manual_values(total="importe malo"))
        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM cash_days").fetchone()[0], 0)
        finally:
            connection.close()

    def test_close_survives_reload_and_blocks_new_entry(self):
        day, _ = self.controller.add_manual_entry(self.manual_values())
        closed = self.controller.close_day("02-08-2026", "PC")
        self.assertEqual(closed.status.value, "CLOSED")

        self.controller.service.repository.close()
        reloaded_controller = build_cash_day_controller(self.database)
        try:
            reloaded = reloaded_controller.load_day("02-08-2026", "PC")
            self.assertEqual(reloaded.status.value, "CLOSED")
            self.assertEqual(reloaded.closing_totals.expected_cash, 800000)
            with self.assertRaises(CashDayClosedError):
                reloaded_controller.add_manual_entry(self.manual_values(caja_inicial=""))
            with self.assertRaises(CashDayClosedError):
                reloaded_controller.update_manual_entry(
                    reloaded.entries[0].id,
                    self.manual_values(caja_inicial="", total="600000"),
                )
            with self.assertRaises(CashDayClosedError):
                reloaded_controller.void_entry(
                    "02-08-2026", "PC", reloaded.entries[0].id, "No permitido"
                )
        finally:
            reloaded_controller.service.repository.close()

    def test_legacy_analysis_imports_without_txt_dual_write(self):
        result = {"por_dia": {"03-08-2026": {
            "unidad": "PC",
            "caja_inicial": 100000,
            "hoja": "Día 3",
            "registros": [{
                "descripcion": "VENTA", "total": 200000, "efectivo": 200000,
                "tarjeta_cheque": 0, "gastos": 0, "saldo": "cancelado",
            }],
        }}}
        summary = self.controller.import_legacy_analysis(result)
        self.assertEqual((summary.days, summary.entries), (1, 1))
        day = self.controller.load_day("03-08-2026", "PC")
        self.assertEqual(day.totals().expected_cash, 300000)
        self.assertEqual(day.entries[0].source_reference, "Día 3")

    def test_friendly_errors_never_expose_tracebacks_or_sql(self):
        title, message = friendly_error(sqlite3.OperationalError("database is locked at SELECT secret"))
        self.assertEqual(title, "No se pudo guardar")
        self.assertNotIn("SELECT", message)
        self.assertNotIn("Traceback", message)

    def test_edit_and_void_update_totals_without_erasing_history(self):
        day, entry = self.controller.add_manual_entry(self.manual_values())
        edited_day, edited = self.controller.update_manual_entry(
            entry.id,
            self.manual_values(total="600000", efectivo="400000", tarjeta_cheque="200000"),
        )
        self.assertEqual(edited.revision, 1)
        self.assertEqual(edited_day.totals().total, 600000)
        voided_day = self.controller.void_entry(
            "02-08-2026", "PC", entry.id, "Operación cancelada"
        )
        self.assertEqual(len(voided_day.entries), 1)
        self.assertEqual(voided_day.entries[0].status.value, "VOIDED")
        self.assertEqual(voided_day.totals().total, 0)
        self.assertEqual(
            [
                revision["action"]
                for revision in self.controller.service.repository.list_entry_revisions(entry.id)
            ],
            ["CREATE", "UPDATE", "VOID"],
        )

    def test_close_creates_a_valid_local_backup(self):
        self.controller.add_manual_entry(self.manual_values())
        self.controller.close_day("02-08-2026", "PC")
        backup = self.controller.last_backup_path
        self.assertIsNotNone(backup)
        self.assertTrue(backup.is_file())
        backup_repository = type(self.controller.service.repository)(backup)
        try:
            backup_repository.integrity_check()
            restored = backup_repository.get_by_date_and_unit(date(2026, 8, 2), "PC")
            self.assertEqual(restored.status.value, "CLOSED")
            self.assertEqual(restored.totals().expected_cash, 800000)
        finally:
            backup_repository.close()


if __name__ == "__main__":
    unittest.main()
