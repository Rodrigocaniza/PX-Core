from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from modulos.comunicaciones.bootstrap import build_controller
from modulos.comunicaciones.domain.errors import (
    BackupError,
    DuplicateTemplateError,
    InvalidTemplateError,
    MissingVariablesError,
    RestoreError,
    TemplateInactiveError,
    TemplateNotFoundError,
)
from modulos.comunicaciones.infrastructure.clipboard import InMemoryClipboard
from modulos.comunicaciones.ui.controller import friendly_error


class ControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.clipboard = InMemoryClipboard()
        self.controller = build_controller(
            self.directory / "bc_comunicaciones.sqlite3", clipboard=self.clipboard
        )
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        try:
            self.controller.repository.close()
        except Exception:
            pass


class StartupTests(ControllerTestCase):
    def test_first_start_preloads_the_library_and_later_starts_do_not(self):
        self.assertGreater(len(self.controller.search("", include_inactive=True)), 0)
        self.assertEqual(self.controller.start(), 0)

    def test_category_options_include_a_total_and_per_category_counts(self):
        options = self.controller.category_options()
        self.assertEqual(options[0].slug, "")
        self.assertEqual(options[0].name, "Todas")
        self.assertEqual(options[0].count, sum(option.count for option in options[1:]))
        self.assertGreaterEqual(len(options), 6)

    def test_operator_name_is_remembered(self):
        self.assertEqual(self.controller.operator(), "")
        self.controller.set_operator("  Rocío  ")
        self.assertEqual(self.controller.operator(), "Rocío")


class NavigationTests(ControllerTestCase):
    def test_search_filters_combine(self):
        template = self.controller.search("Pedido listo")[0]
        self.controller.toggle_favorite(template.id)
        found = self.controller.search(
            "pedido", category_slug="pedidos-estados", only_favorites=True,
        )
        self.assertEqual([item.id for item in found], [template.id])

    def test_deactivated_templates_disappear_unless_explicitly_requested(self):
        template = self.controller.search("Pedido listo")[0]
        self.controller.set_active(template.id, False)
        self.assertNotIn(template.id, [item.id for item in self.controller.search("pedido")])
        self.assertIn(template.id, [item.id for item in self.controller.search("pedido", include_inactive=True)])

    def test_empty_state_messages_explain_what_to_do(self):
        sin_resultados = self.controller.empty_state_message("zzzz")
        self.assertIn("zzzz", sin_resultados)
        self.assertIn("F2", sin_resultados)

        sin_favoritas = self.controller.empty_state_message("", only_favorites=True)
        self.assertIn("favoritas", sin_favoritas)
        self.assertIn("☆", sin_favoritas)

        categoria_vacia = self.controller.empty_state_message("", category_slug="generales")
        self.assertIn("categoría", categoria_vacia)

    def test_opening_a_template_returns_blank_fields_for_each_variable(self):
        template = self.controller.search("Pedido listo")[0]
        form = self.controller.open_template(template.id)
        self.assertEqual(set(form.values), set(template.variables))
        self.assertTrue(all(value == "" for value in form.values.values()))
        self.assertEqual([spec.name for spec in form.specs], list(template.variables))

    def test_opening_a_template_can_prefill_known_values(self):
        template = self.controller.search("Pedido listo")[0]
        form = self.controller.open_template(template.id, values={"Cliente": "Ana"})
        self.assertEqual(form.values["cliente"], "Ana")

    def test_opening_a_missing_template_raises(self):
        with self.assertRaises(TemplateNotFoundError):
            self.controller.open_template("no-existe")


class PreparationTests(ControllerTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.template = self.controller.save_template({
            "title": "Aviso de control",
            "body": "Hola {{cliente}}, te esperamos el {{fecha}}.",
            "category_slug": "generales",
            "keywords": "control",
            "active": True,
        })

    def test_preview_updates_as_values_are_typed(self):
        vacio = self.controller.preview(self.template, {})
        self.assertFalse(vacio.is_complete)
        self.assertEqual(vacio.missing_labels, ("Cliente", "Fecha"))

        parcial = self.controller.preview(self.template, {"cliente": "Ana"})
        self.assertIn("Hola Ana", parcial.text)
        self.assertEqual(parcial.missing_labels, ("Fecha",))

        completo = self.controller.preview(self.template, {"cliente": "Ana", "fecha": "martes"})
        self.assertTrue(completo.is_complete)
        self.assertEqual(completo.text, "Hola Ana, te esperamos el martes.")

    def test_copy_uses_the_stored_operator_when_none_is_given(self):
        self.controller.set_operator("Rocío")
        message = self.controller.copy_message(self.template.id, {"cliente": "Ana", "fecha": "martes"})
        self.assertEqual(message.operator, "Rocío")
        self.assertEqual(self.clipboard.text, "Hola Ana, te esperamos el martes.")

    def test_copy_records_the_edited_text_when_the_operator_adjusts_it(self):
        message = self.controller.copy_message(
            self.template.id, {"cliente": "Ana", "fecha": "martes"},
            final_text="Hola Ana, te esperamos el martes a las 10. ¡Gracias!",
        )
        self.assertTrue(message.manually_edited)
        self.assertEqual(self.clipboard.text, "Hola Ana, te esperamos el martes a las 10. ¡Gracias!")
        self.assertEqual(self.controller.recent()[0].final_text, self.clipboard.text)

    def test_copy_is_blocked_while_values_are_missing(self):
        with self.assertRaises(MissingVariablesError):
            self.controller.copy_message(self.template.id, {"cliente": "Ana"})
        self.assertEqual(self.clipboard.copies, 0)
        self.assertEqual(self.controller.recent(), [])

    def test_copying_a_deactivated_template_is_blocked(self):
        self.controller.set_active(self.template.id, False)
        with self.assertRaises(TemplateInactiveError):
            self.controller.copy_message(self.template.id, {"cliente": "Ana", "fecha": "martes"})


class AdministrationTests(ControllerTestCase):
    def test_saving_an_incomplete_draft_is_refused_before_touching_the_database(self):
        before = len(self.controller.search("", include_inactive=True))
        with self.assertRaises(InvalidTemplateError):
            self.controller.save_template({"title": "", "body": "", "category_slug": ""})
        self.assertEqual(len(self.controller.search("", include_inactive=True)), before)

    def test_draft_from_template_round_trips_through_save(self):
        original = self.controller.search("Pedido listo")[0]
        draft = self.controller.draft_from(original)
        self.assertFalse(self.controller.has_unsaved_changes(original, draft))

        draft["body"] = original.body + "\n\nPD: traé tu cédula."
        self.assertTrue(self.controller.has_unsaved_changes(original, draft))

        updated = self.controller.save_template(draft, template_id=original.id)
        self.assertIn("PD: traé tu cédula.", updated.body)
        self.assertFalse(self.controller.has_unsaved_changes(updated, self.controller.draft_from(updated)))

    def test_draft_for_a_new_template_starts_on_the_current_category(self):
        draft = self.controller.draft_from(None, default_category="aseguradoras-recetas")
        self.assertEqual(draft["category_slug"], "aseguradoras-recetas")
        self.assertTrue(draft["active"])

    def test_saving_a_duplicate_title_is_refused(self):
        with self.assertRaises(DuplicateTemplateError):
            self.controller.save_template({
                "title": "Pedido listo para retirar", "body": "Otro texto.",
                "category_slug": "pedidos-estados", "active": True,
            })


class BackupTests(ControllerTestCase):
    def test_backup_and_restore_round_trip_through_the_controller(self):
        snapshot = self.controller.create_backup("prueba")
        self.assertTrue(snapshot.is_file())
        self.assertEqual(self.controller.last_backup_path, snapshot)
        self.assertIn(snapshot, self.controller.list_backups())

        created = self.controller.save_template({
            "title": "Temporal", "body": "Hola {{cliente}}", "category_slug": "generales", "active": True,
        })
        self.assertTrue(self.controller.search("Temporal"))

        result = self.controller.restore_backup(snapshot)
        self.assertEqual(self.controller.search("Temporal"), [])
        self.assertTrue(result.safety_backup.is_file())
        with self.assertRaises(TemplateNotFoundError):
            self.controller.library.get(created.id)

    def test_restoring_an_invalid_file_is_reported_and_changes_nothing(self):
        bogus = self.directory / "cualquiera.sqlite3"
        bogus.write_text("no soy una base", encoding="utf-8")
        before = len(self.controller.search("", include_inactive=True))
        with self.assertRaises(RestoreError):
            self.controller.restore_backup(bogus)
        self.assertEqual(len(self.controller.search("", include_inactive=True)), before)


class PersistenceAcrossRestartTests(unittest.TestCase):
    def test_everything_the_operator_did_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "bc_comunicaciones.sqlite3"

            first = build_controller(database, clipboard=InMemoryClipboard())
            try:
                first.set_operator("Rocío")
                favorita = first.search("Pedido listo")[0]
                first.toggle_favorite(favorita.id)
                creada = first.save_template({
                    "title": "Aviso propio del local",
                    "body": "Hola {{cliente}}, novedades sobre {{producto}}.",
                    "category_slug": "generales", "keywords": "propio", "active": True,
                })
                desactivada = first.search("Bienvenida")[0]
                first.set_active(desactivada.id, False)
                first.copy_message(creada.id, {"cliente": "Ana", "producto": "tus lentes"})
                total = len(first.search("", include_inactive=True))
            finally:
                first.repository.close()

            second = build_controller(database, clipboard=InMemoryClipboard())
            try:
                self.assertEqual(second.operator(), "Rocío")
                self.assertEqual(len(second.search("", include_inactive=True)), total)
                self.assertTrue(second.library.get(favorita.id).favorite)
                self.assertFalse(second.library.get(desactivada.id).active)
                recuperada = second.library.get(creada.id)
                self.assertEqual(recuperada.title, "Aviso propio del local")
                self.assertEqual(recuperada.usage_count, 1)
                historial = second.recent()
                self.assertEqual(len(historial), 1)
                self.assertIn("Hola Ana, novedades sobre tus lentes.", historial[0].final_text)
            finally:
                second.repository.close()


class FriendlyErrorTests(unittest.TestCase):
    def test_every_expected_failure_has_a_title_and_a_plain_explanation(self):
        cases = [
            MissingVariablesError(["Cliente"]),
            DuplicateTemplateError("Ya existe una plantilla llamada «x»."),
            TemplateInactiveError("Esa plantilla está desactivada."),
            TemplateNotFoundError("Esa plantilla ya no existe."),
            InvalidTemplateError("Falta el título."),
            RestoreError("No es una copia válida."),
            BackupError("Sin espacio."),
            sqlite3.OperationalError("database is locked"),
            OSError("disco lleno"),
            RuntimeError("algo raro"),
        ]
        for error in cases:
            titulo, detalle = friendly_error(error)
            self.assertTrue(titulo.strip(), error)
            self.assertTrue(detalle.strip(), error)
            self.assertNotIn("Traceback", detalle)

    def test_technical_errors_reassure_the_operator_that_nothing_was_lost(self):
        _, detalle = friendly_error(sqlite3.OperationalError("database is locked"))
        self.assertIn("sigue en pantalla", detalle)


if __name__ == "__main__":
    unittest.main()
