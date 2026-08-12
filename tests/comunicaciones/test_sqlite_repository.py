from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from modulos.comunicaciones.domain.errors import DuplicateTemplateError
from modulos.comunicaciones.domain.models import Category, PreparedMessage, Template, VariableSpec
from modulos.comunicaciones.infrastructure.sqlite_repository import SQLiteCommunicationsRepository


CATEGORIA = Category(slug="pedidos-estados", name="Pedidos y estados", position=10)


def build_repository(path=":memory:") -> SQLiteCommunicationsRepository:
    repository = SQLiteCommunicationsRepository(path)
    repository.save_category(CATEGORIA)
    return repository


def build_template(**changes) -> Template:
    payload = {
        "title": "Pedido listo",
        "body": "Hola {{cliente}}, tu pedido {{pedido}} está listo.",
        "category_slug": "pedidos-estados",
        "keywords": "retiro entrega",
    }
    payload.update(changes)
    return Template(**payload)


class SchemaTests(unittest.TestCase):
    def test_migration_creates_every_expected_table_once(self):
        repository = build_repository()
        self.addCleanup(repository.close)
        self.assertTrue(repository.schema_looks_valid())
        repository.migrate()  # idempotente
        with repository._connection() as connection:
            versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations")]
        self.assertEqual(versions, ["001", "002"])

    def test_integrity_check_passes_on_a_fresh_database(self):
        repository = build_repository()
        self.addCleanup(repository.close)
        repository.integrity_check()


class TemplatePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = build_repository()
        self.addCleanup(self.repository.close)

    def test_saved_template_round_trips_with_its_variable_specs(self):
        template = build_template(
            variable_specs=(VariableSpec("cliente", "Nombre del cliente", "Ana"),)
        )
        self.repository.save_template(template)
        recovered = self.repository.get_template(template.id)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.title, template.title)
        self.assertEqual(recovered.body, template.body)
        self.assertEqual(recovered.keywords, "retiro entrega")
        self.assertEqual([spec.name for spec in recovered.variable_specs], ["cliente", "pedido"])
        self.assertEqual(recovered.variable_specs[0].label, "Nombre del cliente")
        self.assertEqual(recovered.variable_specs[0].example, "Ana")

    def test_saving_the_same_id_updates_instead_of_duplicating(self):
        template = build_template()
        self.repository.save_template(template)
        self.repository.save_template(template.edited(title="Pedido terminado"))
        self.assertEqual(self.repository.count_templates(), 1)
        self.assertEqual(self.repository.get_template(template.id).title, "Pedido terminado")

    def test_duplicate_title_in_same_category_is_rejected_with_a_clear_error(self):
        self.repository.save_template(build_template())
        with self.assertRaises(DuplicateTemplateError) as captured:
            self.repository.save_template(build_template(title="  pedido LISTO  "))
        # El mensaje cita el título que el operador acaba de escribir.
        self.assertIn("pedido LISTO", str(captured.exception))
        self.assertIn("Ya existe una plantilla", str(captured.exception))
        self.assertEqual(self.repository.count_templates(), 1)

    def test_same_title_in_another_category_is_allowed(self):
        self.repository.save_category(Category(slug="generales", name="Mensajes generales", position=50))
        self.repository.save_template(build_template())
        self.repository.save_template(build_template(category_slug="generales"))
        self.assertEqual(self.repository.count_templates(), 2)

    def test_unknown_category_is_refused_by_the_foreign_key(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_template(build_template(category_slug="inexistente"))

    def test_updating_variable_specs_removes_the_previous_ones(self):
        template = build_template(variable_specs=(VariableSpec("cliente", "Cliente", "Ana"),))
        self.repository.save_template(template)
        self.repository.save_template(template.edited(body="Hola {{cliente}}."))
        recovered = self.repository.get_template(template.id)
        self.assertEqual([spec.name for spec in recovered.variable_specs], ["cliente"])


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = build_repository()
        self.repository.save_category(Category(slug="generales", name="Mensajes generales", position=50))
        self.addCleanup(self.repository.close)
        self.listo = build_template(title="Pedido listo", keywords="retiro entrega")
        self.demora = build_template(
            title="Demora en el laboratorio",
            body="Hola {{cliente}}, tu pedido va a demorar.",
            keywords="atraso",
        )
        self.saludo = build_template(
            title="Bienvenida", body="Hola {{cliente}}, gracias por escribir.",
            category_slug="generales", keywords="",
        )
        self.inactiva = build_template(
            title="Vieja", body="Texto viejo {{cliente}}", category_slug="generales", active=False,
        )
        for template in (self.listo, self.demora, self.saludo, self.inactiva):
            self.repository.save_template(template)

    def test_inactive_templates_are_hidden_by_default(self):
        titles = {item.title for item in self.repository.search_templates()}
        self.assertNotIn("Vieja", titles)
        self.assertIn("Vieja", {item.title for item in self.repository.search_templates(include_inactive=True)})

    def test_category_filter_restricts_results(self):
        found = self.repository.search_templates(category_slug="generales")
        self.assertEqual({item.title for item in found}, {"Bienvenida"})

    def test_search_matches_title_keywords_and_body(self):
        self.assertIn("Pedido listo", {i.title for i in self.repository.search_templates(query="retiro")})
        self.assertIn("Demora en el laboratorio", {i.title for i in self.repository.search_templates(query="atraso")})
        self.assertIn("Bienvenida", {i.title for i in self.repository.search_templates(query="gracias por escribir")})

    def test_search_ignores_accents_and_case(self):
        self.repository.save_template(build_template(
            title="Cobertura autorizada", body="Hola {{cliente}}, quedó aprobada.",
            category_slug="generales", keywords="",
        ))
        self.assertTrue(self.repository.search_templates(query="APROBADA"))
        self.assertTrue(self.repository.search_templates(query="quedo aprobada"))

    def test_favorites_filter(self):
        self.repository.save_template(self.listo.with_favorite(True))
        found = self.repository.search_templates(only_favorites=True)
        self.assertEqual({item.title for item in found}, {"Pedido listo"})

    def test_like_wildcards_in_the_query_are_treated_as_plain_text(self):
        self.assertEqual(self.repository.search_templates(query="%"), [])
        self.assertEqual(self.repository.search_templates(query="_"), [])


class HistoryAndOutboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = build_repository()
        self.addCleanup(self.repository.close)
        self.template = build_template()
        self.repository.save_template(self.template)

    def _message(self, text: str) -> PreparedMessage:
        return PreparedMessage(
            template_id=self.template.id, template_title=self.template.title,
            category_slug=self.template.category_slug, final_text=text,
            values={"cliente": "Ana", "pedido": "12"}, operator="Rocío",
        )

    def test_prepared_messages_round_trip_newest_first(self):
        self.repository.save_prepared_message(self._message("Mensaje uno"))
        self.repository.save_prepared_message(self._message("Mensaje dos"))
        recent = self.repository.list_prepared_messages(limit=5)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0].final_text, "Mensaje dos")
        self.assertEqual(recent[0].values, {"cliente": "Ana", "pedido": "12"})
        self.assertEqual(recent[0].operator, "Rocío")
        self.assertEqual(recent[0].status.value, "PENDIENTE")

    def test_limit_is_respected(self):
        for index in range(5):
            self.repository.save_prepared_message(self._message(f"Mensaje {index}"))
        self.assertEqual(len(self.repository.list_prepared_messages(limit=3)), 3)

    def test_outbox_events_are_queued_as_pending(self):
        event_id = self.repository.append_outbox_event("message_prepared", {"template_id": self.template.id})
        pending = self.repository.list_pending_outbox_events()
        self.assertEqual([item["id"] for item in pending], [event_id])
        self.assertEqual(pending[0]["payload"], {"template_id": self.template.id})
        self.assertEqual(pending[0]["attempts"], 0)

    def test_settings_round_trip_and_overwrite(self):
        self.assertEqual(self.repository.get_setting("operator", "sin nombre"), "sin nombre")
        self.repository.set_setting("operator", "Rocío")
        self.repository.set_setting("operator", "Ana")
        self.assertEqual(self.repository.get_setting("operator"), "Ana")


class FilePersistenceTests(unittest.TestCase):
    def test_data_survives_closing_and_reopening_the_database_file(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "nested" / "bc_comunicaciones.sqlite3"
            repository = build_repository(database)
            template = build_template()
            repository.save_template(template)
            repository.close()

            reopened = SQLiteCommunicationsRepository(database)
            self.addCleanup(reopened.close)
            self.assertTrue(database.is_file())
            self.assertEqual(reopened.get_template(template.id).title, "Pedido listo")


if __name__ == "__main__":
    unittest.main()
