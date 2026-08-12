from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from modulos.comunicaciones.application.services import MessageLibraryService
from modulos.comunicaciones.domain.errors import RestoreError
from modulos.comunicaciones.infrastructure.backup import LocalBackupService
from modulos.comunicaciones.infrastructure.sqlite_repository import SQLiteCommunicationsRepository


class BackupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup)
        self.repository = SQLiteCommunicationsRepository(self.directory / "bc_comunicaciones.sqlite3")
        self.library = MessageLibraryService(self.repository)
        self.library.ensure_seeded()
        self.backups = LocalBackupService(self.repository, self.directory / "Backups")

    def _cleanup(self) -> None:
        try:
            self.repository.close()
        except Exception:
            pass


class BackupTests(BackupTestCase):
    def test_backup_creates_a_readable_copy_in_the_backup_folder(self):
        destination = self.backups.create_backup("prueba")
        self.assertTrue(destination.is_file())
        self.assertEqual(destination.parent, self.directory / "Backups")
        self.assertIn("prueba", destination.name)

        copy = sqlite3.connect(destination)
        try:
            count = copy.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        finally:
            copy.close()
        self.assertEqual(count, self.repository.count_templates())

    def test_listing_returns_backups_newest_first(self):
        first = self.backups.create_backup("uno")
        second = self.backups.create_backup("dos")
        listed = self.backups.list_backups()
        self.assertEqual(set(listed), {first, second})
        self.assertEqual(listed[0], second)

    def test_retention_keeps_only_the_configured_amount(self):
        limited = LocalBackupService(self.repository, self.directory / "Backups", keep=3)
        for index in range(6):
            limited.create_backup(f"n{index}")
        self.assertEqual(len(limited.list_backups()), 3)

    def test_label_is_sanitized_into_a_safe_filename(self):
        destination = self.backups.create_backup("cierre/../raro *")
        self.assertTrue(destination.is_file())
        self.assertEqual(destination.parent, self.directory / "Backups")
        self.assertNotIn("..", destination.name)


class RestoreValidationTests(BackupTestCase):
    def test_missing_file_is_reported_clearly(self):
        with self.assertRaises(RestoreError):
            self.backups.restore(self.directory / "no-existe.sqlite3")

    def test_a_file_that_is_not_a_database_is_refused(self):
        bogus = self.directory / "notas.sqlite3"
        bogus.write_text("esto no es una base de datos", encoding="utf-8")
        with self.assertRaises(RestoreError):
            self.backups.restore(bogus)

    def test_a_database_from_another_product_is_refused(self):
        foreign = self.directory / "otra-app.sqlite3"
        connection = sqlite3.connect(foreign)
        try:
            connection.execute("CREATE TABLE cash_days (id TEXT)")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(RestoreError) as captured:
            self.backups.restore(foreign)
        self.assertIn("no es una copia de BC Comunicaciones", str(captured.exception))

    def test_a_refused_restore_leaves_the_current_data_untouched(self):
        before = self.repository.count_templates()
        bogus = self.directory / "roto.sqlite3"
        bogus.write_text("basura", encoding="utf-8")
        with self.assertRaises(RestoreError):
            self.backups.restore(bogus)
        self.assertEqual(self.repository.count_templates(), before)


class RestoreTests(BackupTestCase):
    def test_restore_brings_back_the_state_captured_by_the_backup(self):
        original = self.library.search("Pedido listo")[0]
        snapshot = self.backups.create_backup("antes-de-tocar")

        self.library.set_active(original.id, False)
        self.library.create_template(
            title="Plantilla posterior", body="Hola {{cliente}}", category_slug="generales",
        )
        self.assertFalse(self.library.get(original.id).active)
        posterior_total = self.repository.count_templates()

        result = self.backups.restore(snapshot)

        self.assertTrue(self.library.get(original.id).active)
        self.assertEqual(self.repository.count_templates(), posterior_total - 1)
        self.assertEqual(result.templates, self.repository.count_templates())
        self.assertEqual(self.library.search("Plantilla posterior"), [])

    def test_restore_saves_a_safety_copy_of_the_previous_state_first(self):
        snapshot = self.backups.create_backup("estado-1")
        self.library.create_template(
            title="Sólo en el estado 2", body="Hola {{cliente}}", category_slug="generales",
        )

        result = self.backups.restore(snapshot)
        self.assertEqual(self.library.search("Sólo en el estado 2"), [])
        self.assertTrue(result.safety_backup.is_file())

        # La copia de seguridad automática permite deshacer la restauración.
        undo = self.backups.restore(result.safety_backup)
        self.assertTrue(self.library.search("Sólo en el estado 2"))
        self.assertEqual(undo.restored_from, result.safety_backup)

    def test_restore_also_recovers_the_prepared_message_history(self):
        from modulos.comunicaciones.application.services import MessagePreparationService
        from modulos.comunicaciones.infrastructure.clipboard import InMemoryClipboard

        preparation = MessagePreparationService(self.repository, clipboard=InMemoryClipboard())
        template = self.library.search("Bienvenida")[0]
        values = {name: "dato" for name in template.variables}
        preparation.prepare(template, values, operator="Rocío")
        self.assertEqual(len(preparation.recent()), 1)

        snapshot = self.backups.create_backup("con-historial")
        preparation.prepare(template, values, operator="Ana")
        self.assertEqual(len(preparation.recent()), 2)

        result = self.backups.restore(snapshot)
        self.assertEqual(len(preparation.recent()), 1)
        self.assertEqual(result.prepared_messages, 1)
        self.assertEqual(preparation.recent()[0].operator, "Rocío")

    def test_the_database_stays_usable_right_after_a_restore(self):
        snapshot = self.backups.create_backup("uso-posterior")
        self.backups.restore(snapshot)
        self.repository.integrity_check()
        created = self.library.create_template(
            title="Creada después de restaurar", body="Hola {{cliente}}", category_slug="generales",
        )
        self.assertEqual(self.library.get(created.id).title, "Creada después de restaurar")


if __name__ == "__main__":
    unittest.main()
