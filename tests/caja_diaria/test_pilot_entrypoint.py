from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bc_caja


class FakeRepository:
    def __init__(self):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


class FakeWindow:
    def __init__(self):
        self.exists = True
        self.destroy_calls = 0
        self.quit_calls = 0

    def winfo_exists(self):
        return self.exists

    def destroy(self):
        self.destroy_calls += 1
        self.exists = False

    def quit(self):
        self.quit_calls += 1


class PilotEntrypointTests(unittest.TestCase):
    def test_application_lifecycle_closes_repository_and_window_once(self):
        repository = FakeRepository()
        controller = type(
            "Controller", (), {
                "service": type("Service", (), {"repository": repository})()
            }
        )()
        window = FakeWindow()
        lifecycle = bc_caja.ApplicationLifecycle(controller, window)

        lifecycle.close()
        lifecycle.close()

        self.assertTrue(lifecycle.closed)
        self.assertEqual(repository.close_calls, 1)
        self.assertEqual(window.destroy_calls, 1)
        self.assertEqual(window.quit_calls, 1)

    def test_main_uses_real_root_and_finally_cleanup(self):
        source = Path("bc_caja.py").read_text(encoding="utf-8")
        self.assertNotIn("root.withdraw()", source)
        self.assertIn("usar_ventana_raiz=True", source)
        self.assertIn('window.protocol("WM_DELETE_WINDOW", lifecycle.close)', source)
        self.assertIn('window.bind("<Alt-F4>"', source)
        self.assertIn("finally:\n        lifecycle.close()", source)

    def test_self_check_creates_external_data_layout_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "production-like-data"
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(bc_caja.self_check(data), 0)
                self.assertEqual(bc_caja.self_check(data), 0)

            self.assertTrue((data / "bc_caja.sqlite3").is_file())
            self.assertTrue((data / "Backups").is_dir())
            self.assertTrue((data / "Logs").is_dir())

    def test_cli_self_check_accepts_path_independent_of_current_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            elsewhere = Path(directory) / "elsewhere"
            elsewhere.mkdir()
            previous = Path.cwd()
            try:
                os.chdir(elsewhere)
                self.assertEqual(bc_caja.main(["--self-check", "--data-dir", str(data)]), 0)
            finally:
                os.chdir(previous)
            self.assertTrue((data / "bc_caja.sqlite3").is_file())

    def test_first_run_check_closes_restarts_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "first-run"
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(bc_caja.first_run_check(data), 0)
            self.assertTrue((data / "bc_caja.sqlite3").is_file())
            self.assertEqual(len(list((data / "Backups").glob("*.sqlite3"))), 1)

    def test_first_run_check_refuses_non_empty_target(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "keep.txt").write_text("do not overwrite", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "directorio temporal vacio"):
                bc_caja.first_run_check(data)
            self.assertEqual((data / "keep.txt").read_text(encoding="utf-8"), "do not overwrite")


if __name__ == "__main__":
    unittest.main()
