from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.config import DATA_DIR_ENV, resolve_data_paths


class CashDataPathTests(unittest.TestCase):
    def test_configured_path_is_stable_and_separates_data_backups_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            configured = Path(directory) / "operacion" / "caja"
            with patch.dict(os.environ, {DATA_DIR_ENV: str(configured)}, clear=False):
                paths = resolve_data_paths()
                self.assertEqual(paths.root, configured.resolve())
                self.assertEqual(paths.database, configured.resolve() / "bc_caja.sqlite3")
                self.assertEqual(paths.backups, configured.resolve() / "Backups")
                self.assertEqual(paths.logs, configured.resolve() / "Logs")

                controller = build_cash_day_controller()
                try:
                    controller.open_or_load_day("10-08-2026", "PC", 100000)
                    self.assertTrue(paths.database.is_file())
                    self.assertTrue(paths.backups.is_dir())
                    self.assertTrue(paths.logs.is_dir())
                finally:
                    controller.service.repository.close()

    def test_explicit_test_database_never_uses_production_backup_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "isolated.sqlite3"
            controller = build_cash_day_controller(database)
            try:
                controller.open_or_load_day("10-08-2026", "PC", 0)
                controller.close_day("10-08-2026", "PC")
                self.assertEqual(controller.last_backup_path.parent, database.parent / "Backups")
            finally:
                controller.service.repository.close()


if __name__ == "__main__":
    unittest.main()
