"""Regresiones de defectos reales encontrados en la revisión QA y la auditoría.

Cada test acá reproduce un defecto que existió y que llegó a manifestarse: no son
casos hipotéticos. Referencia: `artifacts/BC-COMUNICACIONES-MVP-001/QA_AUDIT_REPORT.md`.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modulos.comunicaciones.bootstrap import build_controller
from modulos.comunicaciones.domain.errors import MissingVariablesError, RestoreError
from modulos.comunicaciones.domain.models import (
    find_malformed_variables,
    unresolved_in_final_text,
)
from modulos.comunicaciones.infrastructure.backup import LocalBackupService
from modulos.comunicaciones.infrastructure.clipboard import InMemoryClipboard


class RestoreRetentionRegressionTests(unittest.TestCase):
    """D-1 — La retención borraba el respaldo que se estaba restaurando.

    La copia «previo-a-restaurar» empujaba el total por encima del tope y la
    retención eliminaba la más vieja, que podía ser justamente el origen. Después
    `sqlite3.connect()` recreaba ese archivo como una base vacía y la copiaba
    encima de los datos vivos: 27 plantillas → 0, informando éxito.
    """

    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.controller = build_controller(
            self.directory / "bc_comunicaciones.sqlite3", clipboard=InMemoryClipboard()
        )
        self.addCleanup(self._cleanup)
        self.controller.set_operator("OPERADOR REAL")
        self.controller.save_template({
            "title": "TRABAJO DE MESES", "body": "Hola {{cliente}}",
            "category_slug": "generales", "active": True,
        })
        self.backups = LocalBackupService(self.controller.repository, self.directory / "Backups", keep=3)
        self.controller.backup_service = self.backups

    def _cleanup(self) -> None:
        try:
            self.controller.repository.close()
        except Exception:
            pass

    def test_restoring_the_oldest_backup_at_the_retention_cap_keeps_every_template(self):
        copias = [self.backups.create_backup(f"dia{index}") for index in range(3)]
        esperado = len(self.controller.search("", include_inactive=True))
        self.assertEqual(len(self.backups.list_backups()), 3)

        resultado = self.controller.restore_backup(copias[0])

        self.assertEqual(len(self.controller.search("", include_inactive=True)), esperado)
        self.assertEqual(resultado.templates, esperado)
        self.assertEqual(self.controller.operator(), "OPERADOR REAL")
        self.assertTrue(self.controller.search("TRABAJO DE MESES"))

    def test_retention_never_deletes_the_backup_being_restored(self):
        copias = [self.backups.create_backup(f"dia{index}") for index in range(3)]
        self.controller.restore_backup(copias[0])
        self.assertTrue(copias[0].is_file())

    def test_retention_still_prunes_normally_outside_a_restore(self):
        for index in range(6):
            self.backups.create_backup(f"n{index}")
        self.assertEqual(len(self.backups.list_backups()), 3)

    def test_a_vanished_source_can_never_blank_the_database(self):
        """Última línea de defensa: el origen se abre en sólo lectura."""
        copia = self.backups.create_backup("desaparece")
        esperado = len(self.controller.search("", include_inactive=True))
        copia.unlink()
        with self.assertRaises(RestoreError):
            self.controller.restore_backup(copia)
        self.assertEqual(len(self.controller.search("", include_inactive=True)), esperado)

        # Ni siquiera saltándose la validación previa se pierden datos.
        with self.assertRaises(Exception):
            self.controller.repository.restore_from(copia)
        self.assertEqual(len(self.controller.search("", include_inactive=True)), esperado)
        self.assertFalse(copia.exists(), "no debe materializarse una base vacía")


class BackupPathRegressionTests(unittest.TestCase):
    """D-6 — Una carpeta con `#` o `%` hacía rechazar un respaldo válido."""

    def test_backups_in_folders_with_uri_characters_are_accepted(self):
        # `?` no se prueba: Windows no admite ese carácter en un nombre de carpeta.
        for nombre in ("Copias #1", "copias 100%", "Copias del Año", "Copias & más"):
            with self.subTest(carpeta=nombre):
                directory = Path(tempfile.mkdtemp())
                controller = build_controller(
                    directory / "bc_comunicaciones.sqlite3", clipboard=InMemoryClipboard()
                )
                try:
                    backups = LocalBackupService(controller.repository, directory / nombre)
                    controller.backup_service = backups
                    copia = backups.create_backup("prueba")
                    esperado = len(controller.search("", include_inactive=True))
                    controller.save_template({
                        "title": "POSTERIOR AL RESPALDO", "body": "Hola {{cliente}}",
                        "category_slug": "generales", "active": True,
                    })
                    resultado = controller.restore_backup(copia)
                    self.assertEqual(resultado.templates, esperado)
                    self.assertEqual(controller.search("POSTERIOR AL RESPALDO"), [])
                finally:
                    controller.repository.close()


class MalformedVariableRegressionTests(unittest.TestCase):
    """D-4 — Variables mal escritas viajaban tal cual al cliente."""

    def test_malformed_placeholders_are_detected_next_to_valid_ones(self):
        malas = find_malformed_variables("Hola {{cliente}}, tu {{2do par}} está listo.")
        self.assertEqual(malas, ("{{2do par}}",))

    def test_every_shape_a_person_would_naturally_type_is_caught(self):
        for cuerpo, esperado in (
            ("{{nombre del cliente}}", "{{nombre del cliente}}"),
            ("{{2do par}}", "{{2do par}}"),
            ("{{}}", "{{}}"),
            ("{{ }}", "{{ }}"),
            ("{{precio-final}}", "{{precio-final}}"),
        ):
            with self.subTest(cuerpo=cuerpo):
                self.assertIn(esperado, find_malformed_variables(cuerpo))

    def test_valid_variables_are_never_flagged(self):
        for cuerpo in ("{{cliente}}", "{{ Cliente }}", "{{numero_pedido}}", "{{año}}", "{{düo}}"):
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(find_malformed_variables(cuerpo), ())

    def test_the_editor_refuses_to_save_a_malformed_template(self):
        directory = Path(tempfile.mkdtemp())
        controller = build_controller(
            directory / "bc_comunicaciones.sqlite3", clipboard=InMemoryClipboard()
        )
        try:
            problemas = controller.validate_draft({
                "title": "Aviso", "body": "Hola {{cliente}}, tu {{2do par}} está listo.",
                "category_slug": "generales",
            })
            self.assertTrue(problemas)
            self.assertIn("{{2do par}}", problemas[0])
        finally:
            controller.repository.close()


class FinalTextRegressionTests(unittest.TestCase):
    """D-2 y D-3 — El texto final se validaba mal y se copiaba texto viejo."""

    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.clipboard = InMemoryClipboard()
        self.controller = build_controller(
            self.directory / "bc_comunicaciones.sqlite3", clipboard=self.clipboard
        )
        self.addCleanup(self._cleanup)
        self.template = self.controller.save_template({
            "title": "Aviso de regresión",
            "body": "Hola {{cliente}}, tu pedido {{pedido}} está listo.",
            "category_slug": "generales", "active": True,
        })

    def _cleanup(self) -> None:
        try:
            self.controller.repository.close()
        except Exception:
            pass

    def test_a_preview_placeholder_can_never_reach_the_customer(self):
        with self.assertRaises(MissingVariablesError) as capturado:
            self.controller.copy_message(
                self.template.id, {"cliente": "Ana"},
                final_text="Hola Ana, tu pedido [Pedido] está listo.",
            )
        self.assertIn("Pedido", str(capturado.exception))
        self.assertEqual(self.clipboard.copies, 0)

    def test_an_unreplaced_variable_can_never_reach_the_customer(self):
        with self.assertRaises(MissingVariablesError):
            self.controller.copy_message(
                self.template.id, {"cliente": "Ana", "pedido": "12"},
                final_text="Hola {{cliente}}, tu pedido 12 está listo.",
            )
        self.assertEqual(self.clipboard.copies, 0)

    def test_a_hand_written_message_is_accepted_even_with_empty_fields(self):
        """El operador reescribió el mensaje: no se le exigen los campos."""
        mensaje = self.controller.copy_message(
            self.template.id, {},
            final_text="Hola Ana, pasá cuando quieras a retirar. ¡Gracias!",
        )
        self.assertEqual(self.clipboard.text, "Hola Ana, pasá cuando quieras a retirar. ¡Gracias!")
        self.assertTrue(mensaje.manually_edited)

    def test_pending_detection_matches_what_is_about_to_be_copied(self):
        pendientes = self.controller.pending_in_text(
            self.template, "Hola [Cliente], tu pedido {{pedido}} está listo."
        )
        self.assertIn("Cliente", pendientes)
        self.assertIn("{{pedido}}", pendientes)
        self.assertEqual(
            self.controller.pending_in_text(self.template, "Hola Ana, tu pedido 12 está listo."), ()
        )

    def test_unresolved_helper_ignores_text_that_merely_looks_like_a_marker(self):
        # Un corchete cualquiera no es un marcador pendiente.
        self.assertEqual(
            unresolved_in_final_text("Hola Ana [urgente], tu pedido 12.", ("cliente", "pedido")), ()
        )


if __name__ == "__main__":
    unittest.main()
