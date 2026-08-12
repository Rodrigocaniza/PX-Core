from __future__ import annotations

import unittest

from modulos.comunicaciones.domain.errors import InvalidTemplateError, MissingVariablesError
from modulos.comunicaciones.domain.models import (
    Category,
    DeliveryStatus,
    PreparedMessage,
    Template,
    VariableSpec,
    extract_variables,
    has_unsaved_changes,
    normalize_search_text,
    rank_templates,
    render_body,
    render_preview,
    slugify,
    variable_key,
)


def build_template(**changes) -> Template:
    payload = {
        "title": "Pedido listo",
        "body": "Hola {{cliente}}, tu pedido {{pedido}} está listo.",
        "category_slug": "pedidos-estados",
    }
    payload.update(changes)
    return Template(**payload)


class VariableEngineTests(unittest.TestCase):
    def test_variables_are_extracted_in_order_without_repeating(self):
        body = "Hola {{cliente}}, {{cliente}} tu pedido {{pedido}} llega el {{fecha}}."
        self.assertEqual(extract_variables(body), ("cliente", "pedido", "fecha"))

    def test_variable_names_tolerate_spaces_accents_and_case(self):
        self.assertEqual(extract_variables("{{ Cliente }} y {{Aseguradora}}"), ("cliente", "aseguradora"))
        self.assertEqual(variable_key("Número Pedido"), "numero_pedido")

    def test_text_without_variables_yields_none(self):
        self.assertEqual(extract_variables("Gracias por tu compra."), ())

    def test_render_replaces_every_occurrence(self):
        body = "Hola {{cliente}}, gracias {{cliente}}."
        self.assertEqual(render_body(body, {"cliente": "Ana"}), "Hola Ana, gracias Ana.")

    def test_render_refuses_missing_values_and_names_them_in_spanish(self):
        with self.assertRaises(MissingVariablesError) as captured:
            render_body("Hola {{cliente}} por {{numero_pedido}}", {"cliente": "Ana"})
        self.assertEqual(captured.exception.missing, ("Numero pedido",))
        self.assertIn("Numero pedido", str(captured.exception))

    def test_blank_value_counts_as_missing(self):
        with self.assertRaises(MissingVariablesError):
            render_body("Hola {{cliente}}", {"cliente": "   "})

    def test_preview_never_fails_and_marks_pending_values(self):
        preview = render_preview("Hola {{cliente}}, pedido {{pedido}}.", {"cliente": "Ana"})
        self.assertEqual(preview, "Hola Ana, pedido [Pedido].")

    def test_render_accepts_values_supplied_with_accents_or_capitals(self):
        self.assertEqual(render_body("Hola {{cliente}}", {"Cliente": "Ana"}), "Hola Ana")


class TemplateTests(unittest.TestCase):
    def test_title_and_body_are_required(self):
        with self.assertRaises(InvalidTemplateError):
            build_template(title="   ")
        with self.assertRaises(InvalidTemplateError):
            build_template(body="")

    def test_category_is_required_and_normalized(self):
        self.assertEqual(build_template(category_slug="Pedidos y Estados").category_slug, "pedidos-y-estados")
        with self.assertRaises(InvalidTemplateError):
            build_template(category_slug="   ")

    def test_variable_specs_cover_body_variables_and_drop_orphans(self):
        template = build_template(
            variable_specs=(
                VariableSpec("cliente", "Nombre del cliente", "Ana"),
                VariableSpec("inexistente", "No usada", ""),
            )
        )
        self.assertEqual([spec.name for spec in template.variable_specs], ["cliente", "pedido"])
        self.assertEqual(template.variable_specs[0].label, "Nombre del cliente")
        self.assertEqual(template.variable_specs[1].label, "Pedido")

    def test_editing_bumps_revision_and_refuses_protected_fields(self):
        template = build_template()
        edited = template.edited(title="Pedido terminado")
        self.assertEqual(edited.revision, template.revision + 1)
        self.assertEqual(edited.id, template.id)
        with self.assertRaises(InvalidTemplateError):
            template.edited(id="otro")
        with self.assertRaises(InvalidTemplateError):
            template.edited(usage_count=99)

    def test_favorite_active_and_usage_transitions(self):
        template = build_template()
        self.assertTrue(template.with_favorite(True).favorite)
        self.assertFalse(template.with_active(False).active)
        self.assertEqual(template.used_once().usage_count, 1)

    def test_search_blob_is_accent_insensitive(self):
        template = build_template(title="Cobertura aprobada", keywords="autorización seguro")
        self.assertIn("autorizacion", template.search_blob)
        self.assertIn("cobertura aprobada", template.search_blob)

    def test_missing_for_reports_pending_variables(self):
        template = build_template()
        self.assertEqual(template.missing_for({"cliente": "Ana"}), ("pedido",))
        self.assertEqual(template.missing_for({"cliente": "Ana", "pedido": "12"}), ())


class RankingTests(unittest.TestCase):
    def test_title_prefix_beats_keyword_match_and_favorites_beat_the_rest(self):
        exacta = build_template(title="Retiro de pedido")
        favorita = build_template(title="Aviso general", keywords="retiro", favorite=True)
        lejana = build_template(title="Otra cosa", body="Pasá a retiro cuando quieras {{cliente}}")
        ordenadas = rank_templates([lejana, favorita, exacta], "retiro")
        self.assertEqual([item.title for item in ordenadas], ["Retiro de pedido", "Aviso general", "Otra cosa"])

    def test_without_query_favorites_and_usage_lead(self):
        usada = build_template(title="B usada", usage_count=10)
        favorita = build_template(title="C favorita", favorite=True)
        nueva = build_template(title="A nueva")
        ordenadas = rank_templates([nueva, usada, favorita], "")
        self.assertEqual([item.title for item in ordenadas], ["C favorita", "B usada", "A nueva"])


class PreparedMessageTests(unittest.TestCase):
    def test_message_defaults_to_pending_and_normalizes_values(self):
        message = PreparedMessage(
            template_id="t1", template_title="Pedido listo", category_slug="pedidos-estados",
            final_text="  Hola Ana  ", values={"Cliente": "Ana"},
        )
        self.assertEqual(message.status, DeliveryStatus.PENDIENTE)
        self.assertEqual(message.final_text, "Hola Ana")
        self.assertEqual(message.values, {"cliente": "Ana"})

    def test_empty_final_text_is_rejected(self):
        with self.assertRaises(InvalidTemplateError):
            PreparedMessage(template_id="t1", template_title="x", category_slug="c", final_text="   ")

    def test_summary_collapses_and_truncates(self):
        message = PreparedMessage(
            template_id="t1", template_title="x", category_slug="c",
            final_text="linea uno\n\nlinea dos " + "z" * 200,
        )
        self.assertLessEqual(len(message.summary), 90)
        self.assertTrue(message.summary.endswith("…"))


class UnsavedChangesTests(unittest.TestCase):
    def test_identical_draft_is_not_dirty(self):
        template = build_template()
        draft = {
            "title": template.title, "body": template.body,
            "category_slug": template.category_slug, "keywords": template.keywords,
            "active": template.active,
        }
        self.assertFalse(has_unsaved_changes(template, draft))

    def test_any_edited_field_marks_the_draft_dirty(self):
        template = build_template()
        for field, value in (
            ("title", "Otro título"), ("body", "Otro cuerpo {{cliente}}"),
            ("category_slug", "generales"), ("keywords", "nuevas"), ("active", False),
        ):
            draft = {
                "title": template.title, "body": template.body,
                "category_slug": template.category_slug, "keywords": template.keywords,
                "active": template.active,
            }
            draft[field] = value
            self.assertTrue(has_unsaved_changes(template, draft), field)

    def test_new_template_is_dirty_only_once_something_was_typed(self):
        self.assertFalse(has_unsaved_changes(None, {"title": "", "body": ""}))
        self.assertTrue(has_unsaved_changes(None, {"title": "Algo", "body": ""}))


class NormalizationTests(unittest.TestCase):
    def test_slug_and_search_normalization(self):
        self.assertEqual(slugify("Aseguradoras y Recetas"), "aseguradoras-y-recetas")
        self.assertEqual(normalize_search_text("  Cobertura   APROBADA  "), "cobertura aprobada")

    def test_category_requires_slug_and_name(self):
        self.assertEqual(Category(slug="Generales", name="Mensajes generales").slug, "generales")
        with self.assertRaises(InvalidTemplateError):
            Category(slug="generales", name="  ")


if __name__ == "__main__":
    unittest.main()
