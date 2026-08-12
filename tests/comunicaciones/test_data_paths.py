from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from modulos.comunicaciones.config import DATA_DIR_ENV, resolve_data_paths


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class DataPathTests(unittest.TestCase):
    def test_explicit_environment_variable_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = resolve_data_paths({DATA_DIR_ENV: directory})
            self.assertEqual(paths.root, Path(directory).resolve())
            self.assertEqual(paths.database.name, "bc_comunicaciones.sqlite3")

    def test_windows_default_lives_under_local_appdata(self):
        paths = resolve_data_paths({"LOCALAPPDATA": r"C:\Users\Alguien\AppData\Local"})
        self.assertEqual(paths.root, Path(r"C:\Users\Alguien\AppData\Local") / "BC" / "Comunicaciones")

    def test_data_never_lands_inside_the_source_tree(self):
        for environment in (
            {DATA_DIR_ENV: ""},
            {"LOCALAPPDATA": r"C:\Users\Alguien\AppData\Local"},
            {"XDG_DATA_HOME": "/home/alguien/.local/share"},
            {},
        ):
            root = resolve_data_paths(environment).root.resolve()
            self.assertFalse(
                str(root).startswith(str(REPOSITORY_ROOT)),
                f"los datos no pueden vivir dentro del repositorio: {root}",
            )

    def test_communications_data_is_separate_from_cash_data(self):
        from modulos.caja_diaria.config import resolve_data_paths as caja_paths

        environment = {"LOCALAPPDATA": r"C:\Users\Alguien\AppData\Local"}
        self.assertNotEqual(
            resolve_data_paths(environment).root, caja_paths(environment).root
        )
        self.assertNotEqual(
            resolve_data_paths(environment).database, caja_paths(environment).database
        )

    def test_ensure_creates_the_full_layout_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nuevo"
            paths = resolve_data_paths({DATA_DIR_ENV: str(target)}).ensure()
            paths.ensure()
            self.assertTrue(paths.root.is_dir())
            self.assertTrue(paths.backups.is_dir())
            self.assertTrue(paths.logs.is_dir())

    def test_real_environment_resolves_without_raising(self):
        paths = resolve_data_paths(dict(os.environ))
        self.assertTrue(paths.database.name.endswith(".sqlite3"))


if __name__ == "__main__":
    unittest.main()
