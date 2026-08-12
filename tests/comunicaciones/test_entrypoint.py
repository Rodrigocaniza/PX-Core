from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bc_comunicaciones


class EntrypointTests(unittest.TestCase):
    def test_self_check_creates_the_external_data_layout_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "production-like-data"
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(bc_comunicaciones.self_check(data), 0)
                self.assertEqual(bc_comunicaciones.self_check(data), 0)

            self.assertTrue((data / "bc_comunicaciones.sqlite3").is_file())
            self.assertTrue((data / "Backups").is_dir())
            self.assertTrue((data / "Logs").is_dir())

    def test_cli_self_check_is_independent_of_the_current_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            elsewhere = Path(directory) / "elsewhere"
            elsewhere.mkdir()
            previous = Path.cwd()
            try:
                os.chdir(elsewhere)
                self.assertEqual(bc_comunicaciones.main(["--self-check", "--data-dir", str(data)]), 0)
            finally:
                os.chdir(previous)
            self.assertTrue((data / "bc_comunicaciones.sqlite3").is_file())

    def test_first_run_check_walks_the_whole_operator_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "first-run"
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(bc_comunicaciones.first_run_check(data), 0)
            self.assertTrue((data / "bc_comunicaciones.sqlite3").is_file())
            # Un respaldo explícito más el automático previo a restaurar.
            self.assertEqual(len(list((data / "Backups").glob("*.sqlite3"))), 2)

    def test_first_run_check_refuses_a_non_empty_target(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "keep.txt").write_text("no sobrescribir", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "directorio temporal vacio"):
                bc_comunicaciones.first_run_check(data)
            self.assertEqual((data / "keep.txt").read_text(encoding="utf-8"), "no sobrescribir")

    def test_startup_failures_are_written_where_support_can_read_them(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"BC_COMUNICACIONES_DATA_DIR": directory}, clear=True):
                bc_comunicaciones.report_fatal_error(RuntimeError("fallo simulado"))
            log = Path(directory) / "Logs" / "startup-error.log"
            self.assertTrue(log.is_file())
            self.assertIn("fallo simulado", log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
