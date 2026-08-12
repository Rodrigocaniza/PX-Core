from __future__ import annotations

import unittest

from modulos.comunicaciones.application.seed import CATEGORY_SLUGS, initial_templates
from modulos.comunicaciones.application.services import (
    MessageLibraryService,
    MessagePreparationService,
)
from modulos.comunicaciones.domain.errors import (
    CategoryNotFoundError,
    DuplicateTemplateError,
    InvalidTemplateError,
    MissingVariablesError,
    TemplateInactiveError,
    TemplateNotFoundError,
)
from modulos.comunicaciones.infrastructure.clipboard import InMemoryClipboard
from modulos.comunicaciones.infrastructure.sqlite_repository import SQLiteCommunicationsRepository


class ServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SQLiteCommunicationsRepository(":memory:")
        self.addCleanup(self.repository.close)
        self.library = MessageLibraryService(self.repository)
        self.clipboard = InMemoryClipboard()
        self.preparation = MessagePreparationService(self.repository, clipboard=self.clipboard)
        self.library.ensure_seeded()


class SeedingTests(ServiceTestCase):
    def test_seeding_creates_the_five_required_categories(self):
        slugs = [category.slug for category in self.library.list_categories()]
        for required in (
            "cristales-productos", "pedidos-estados", "aseguradoras-recetas",
            "recomendaciones-cuidados", "generales",
        ):
            self.assertIn(required, slugs)

    def test_every_category_ships_with_templates(self):
        counts = self.library.counts_by_category()
        for slug in CATEGORY_SLUGS:
            self.assertGreaterEqual(counts.get(slug, 0), 3, slug)

    def test_seeding_is_idempotent_and_never_overwrites_operator_edits(self):
        original = self.library.search("Pedido listo")[0]
        self.library.update_template(original.id, title="Pedido listo — versión del local")
        self.library.set_active(original.id, False)
        total = len(self.library.search("", include_inactive=True))

        self.assertEqual(self.library.ensure_seeded(), 0)

        self.assertEqual(len(self.library.search("", include_inactive=True)), total)
        recovered = self.library.get(original.id)
        self.assertEqual(recovered.title, "Pedido listo — versión del local")
        self.assertFalse(recovered.active)

    def test_seed_templates_declare_a_spec_for_every_variable(self):
        for template in initial_templates():
            declared = {spec.name for spec in template.variable_specs}
            self.assertEqual(declared, set(template.variables), template.title)
            for spec in template.variable_specs:
                self.assertTrue(spec.label.strip(), f"{template.title}/{spec.name}")

    def test_seed_templates_have_no_leftover_braces_after_rendering(self):
        for template in initial_templates():
            values = {name: f"X{name}" for name in template.variables}
            rendered = template.render(values)
            self.assertNotIn("{{", rendered, template.title)
            self.assertNotIn("}}", rendered, template.title)


class SearchTests(ServiceTestCase):
    def test_search_finds_the_retrieval_template_by_everyday_words(self):
        for word in ("retirar", "listo", "pedido"):
            self.assertTrue(self.library.search(word), word)

    def test_search_ignores_accents(self):
        self.assertTrue(self.library.search("garantia"))
        self.assertTrue(self.library.search("GARANTÍA"))

    def test_category_filter_only_returns_that_category(self):
        found = self.library.search("", category_slug="aseguradoras-recetas")
        self.assertTrue(found)
        self.assertTrue(all(item.category_slug == "aseguradoras-recetas" for item in found))

    def test_favorites_filter_returns_only_marked_templates(self):
        self.assertEqual(self.library.search("", only_favorites=True), [])
        chosen = self.library.search("Pedido listo")[0]
        self.library.set_favorite(chosen.id, True)
        favourites = self.library.search("", only_favorites=True)
        self.assertEqual([item.id for item in favourites], [chosen.id])

    def test_unknown_words_return_nothing_rather_than_everything(self):
        self.assertEqual(self.library.search("zzzz-inexistente"), [])

    def test_getting_a_missing_template_raises_a_translatable_error(self):
        with self.assertRaises(TemplateNotFoundError):
            self.library.get("no-existe")


class AdministrationTests(ServiceTestCase):
    def test_create_edit_and_deactivate_a_template(self):
        created = self.library.create_template(
            title="Aviso de promoción",
            body="Hola {{cliente}}, tenemos {{promocion}} hasta el {{fecha}}.",
            category_slug="generales",
            keywords="promo descuento",
        )
        self.assertEqual(created.variables, ("cliente", "promocion", "fecha"))
        self.assertTrue(self.library.search("promoción"))

        edited = self.library.update_template(created.id, title="Aviso de promoción vigente")
        self.assertEqual(edited.revision, created.revision + 1)

        deactivated = self.library.set_active(created.id, False)
        self.assertFalse(deactivated.active)
        self.assertNotIn(created.id, [item.id for item in self.library.search("promoción")])
        self.assertIn(created.id, [item.id for item in self.library.search("promoción", include_inactive=True)])

        self.assertTrue(self.library.set_active(created.id, True).active)
        self.assertIn(created.id, [item.id for item in self.library.search("promoción")])

    def test_toggle_favorite_flips_both_ways_and_persists(self):
        template = self.library.search("Pedido listo")[0]
        self.assertTrue(self.library.toggle_favorite(template.id).favorite)
        self.assertTrue(self.library.get(template.id).favorite)
        self.assertFalse(self.library.toggle_favorite(template.id).favorite)

    def test_creating_in_an_unknown_category_is_refused(self):
        with self.assertRaises(CategoryNotFoundError):
            self.library.create_template(title="X", body="Hola {{cliente}}", category_slug="no-existe")

    def test_duplicate_titles_within_a_category_are_refused(self):
        with self.assertRaises(DuplicateTemplateError):
            self.library.create_template(
                title="Pedido listo para retirar", body="Otro texto.", category_slug="pedidos-estados",
            )

    def test_validate_draft_reports_every_problem_in_plain_spanish(self):
        problems = self.library.validate_draft(title="  ", body="  ", category_slug="")
        self.assertEqual(len(problems), 3)
        self.assertTrue(any("título" in item for item in problems))
        self.assertTrue(any("texto del mensaje" in item for item in problems))
        self.assertTrue(any("categoría" in item for item in problems))

    def test_validate_draft_catches_malformed_variable_braces(self):
        problems = self.library.validate_draft(
            title="X", body="Hola {{  }} y {{}}", category_slug="generales",
        )
        self.assertTrue(any("mal escritos" in item for item in problems))

    def test_validate_draft_catches_a_malformed_variable_next_to_a_valid_one(self):
        problems = self.library.validate_draft(
            title="X", body="Hola {{cliente}}, tu {{2do par}} está listo.", category_slug="generales",
        )
        self.assertTrue(problems)
        self.assertIn("{{2do par}}", problems[0])

    def test_valid_draft_reports_no_problems(self):
        self.assertEqual(
            self.library.validate_draft(title="X", body="Hola {{cliente}}", category_slug="generales"), ()
        )

    def test_new_category_can_be_created_and_reused(self):
        category = self.library.create_category("Campañas locales")
        self.assertEqual(category.slug, "campanas-locales")
        self.assertEqual(self.library.create_category("Campañas locales").slug, category.slug)
        self.library.create_template(title="Aviso", body="Hola {{cliente}}", category_slug=category.slug)
        self.assertTrue(self.library.search("", category_slug="campanas-locales"))

    def test_empty_category_name_is_refused(self):
        with self.assertRaises(InvalidTemplateError):
            self.library.create_category("   ")


class PreparationTests(ServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.template = self.library.create_template(
            title="Aviso de prueba",
            body="Hola {{cliente}}, tu pedido {{pedido}} está listo.",
            category_slug="pedidos-estados",
        )

    def test_preview_shows_pending_values_without_failing(self):
        preview = self.preparation.preview(self.template, {"cliente": "Ana"})
        self.assertFalse(preview.is_complete)
        self.assertEqual(preview.missing, ("pedido",))
        self.assertEqual(preview.missing_labels, ("Pedido",))
        self.assertIn("[Pedido]", preview.text)

    def test_complete_preview_is_ready_to_copy(self):
        preview = self.preparation.preview(self.template, {"cliente": "Ana", "pedido": "12"})
        self.assertTrue(preview.is_complete)
        self.assertEqual(preview.text, "Hola Ana, tu pedido 12 está listo.")

    def test_preparing_copies_records_history_and_counts_usage(self):
        message = self.preparation.prepare(
            self.template, {"cliente": "Ana", "pedido": "12"}, operator="Rocío",
        )
        self.assertEqual(self.clipboard.text, "Hola Ana, tu pedido 12 está listo.")
        self.assertEqual(self.clipboard.copies, 1)
        self.assertEqual(message.operator, "Rocío")
        self.assertFalse(message.manually_edited)
        self.assertEqual(message.status.value, "PENDIENTE")

        history = self.preparation.recent()
        self.assertEqual([item.id for item in history], [message.id])
        self.assertEqual(self.library.get(self.template.id).usage_count, 1)

    def test_missing_values_block_the_copy_and_leave_no_trace(self):
        with self.assertRaises(MissingVariablesError):
            self.preparation.prepare(self.template, {"cliente": "Ana"})
        self.assertEqual(self.clipboard.copies, 0)
        self.assertEqual(self.preparation.recent(), [])
        self.assertEqual(self.library.get(self.template.id).usage_count, 0)

    def test_manual_edit_is_copied_verbatim_and_flagged(self):
        message = self.preparation.prepare(
            self.template, {"cliente": "Ana", "pedido": "12"},
            final_text="Hola Ana, pasá cuando quieras. ¡Gracias!",
        )
        self.assertEqual(self.clipboard.text, "Hola Ana, pasá cuando quieras. ¡Gracias!")
        self.assertTrue(message.manually_edited)
        self.assertEqual(self.preparation.recent()[0].final_text, "Hola Ana, pasá cuando quieras. ¡Gracias!")

    def test_inactive_template_cannot_be_used(self):
        self.library.set_active(self.template.id, False)
        with self.assertRaises(TemplateInactiveError):
            self.preparation.prepare(self.library.get(self.template.id), {"cliente": "Ana", "pedido": "12"})
        self.assertEqual(self.clipboard.copies, 0)

    def test_preparing_queues_a_local_outbox_event_for_future_delivery(self):
        message = self.preparation.prepare(self.template, {"cliente": "Ana", "pedido": "12"})
        pending = self.repository.list_pending_outbox_events()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["event_type"], "message_prepared")
        self.assertEqual(pending[0]["payload"]["message_id"], message.id)
        self.assertEqual(pending[0]["payload"]["template_id"], self.template.id)

    def test_template_without_variables_is_copied_as_is(self):
        plain = self.library.create_template(
            title="Saludo fijo", body="Gracias por comunicarte con nosotros.", category_slug="generales",
        )
        message = self.preparation.prepare(plain, {})
        self.assertEqual(message.final_text, "Gracias por comunicarte con nosotros.")
        self.assertEqual(self.clipboard.text, "Gracias por comunicarte con nosotros.")

    def test_history_is_newest_first_and_respects_the_limit(self):
        for index in range(4):
            self.preparation.prepare(self.template, {"cliente": f"Cliente {index}", "pedido": str(index)})
        recent = self.preparation.recent(limit=2)
        self.assertEqual(len(recent), 2)
        self.assertIn("Cliente 3", recent[0].final_text)


if __name__ == "__main__":
    unittest.main()
