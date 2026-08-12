from __future__ import annotations

import unittest

from modulos.comunicaciones.application.inbox_service import InboxService
from modulos.comunicaciones.domain.inbox import Account, ConversationFilter, ConversationStatus
from modulos.comunicaciones.infrastructure.inbox_repository import SQLiteInboxRepository
from modulos.comunicaciones.infrastructure.sqlite_repository import SQLiteCommunicationsRepository


class InboxTestCase(unittest.TestCase):
    def setUp(self):
        self.base = SQLiteCommunicationsRepository(":memory:")
        self.repo = SQLiteInboxRepository(self.base)
        self.service = InboxService(self.repo)
        self.repo.save_account(Account("asuncion-centro", "Óptica BC", "Asunción Centro", "WhatsApp mostrador"))
        self.repo.save_account(Account("pilar", "Consultorio BC", "Pilar", "WhatsApp consultorio"))

    def tearDown(self):
        self.base.close()

    def conversation(self, **kwargs):
        return self.service.open_conversation("asuncion-centro", kwargs.pop("name", "Ana Demo"), **kwargs)


class PersistenceAndFlowTests(InboxTestCase):
    def test_full_flow_is_persistent_and_audited(self):
        conversation = self.conversation(contact_reference="demo-001", subject="Retiro de lentes", actor="SOL")
        incoming = self.service.receive(conversation.id, "¿Ya están mis lentes?")
        self.service.assign(conversation.id, "SOL", "SOL")
        outgoing = self.service.reply(conversation.id, "Sí, ya puede retirar.", "SOL")
        self.service.transition(conversation.id, ConversationStatus.RESUELTO, "SOL")

        stored = self.repo.get_conversation(conversation.id)
        self.assertEqual(stored.status, ConversationStatus.RESUELTO)
        self.assertEqual(stored.assigned_operator, "SOL")
        self.assertEqual([incoming.id, outgoing.id], [m.id for m in self.repo.list_messages(conversation.id)])
        self.assertTrue(outgoing.provider_reference.startswith("sim-"))
        self.assertEqual(
            ["CONVERSATION_CREATED", "MESSAGE_APPENDED", "ASSIGNMENT_CHANGED", "MESSAGE_APPENDED", "STATUS_CHANGED", "STATUS_CHANGED"],
            [event["action"] for event in self.repo.audit_log(conversation.id)],
        )

    def test_reply_moves_new_conversation_to_in_progress(self):
        conversation = self.conversation()
        self.service.reply(conversation.id, "Respuesta demo", "SOL")
        self.assertEqual(self.repo.get_conversation(conversation.id).status, ConversationStatus.EN_CURSO)

    def test_operator_is_required_for_reply(self):
        conversation = self.conversation()
        with self.assertRaisesRegex(ValueError, "operador"):
            self.service.reply(conversation.id, "Respuesta", "  ")


class TransitionTests(InboxTestCase):
    def test_resolved_can_be_reopened(self):
        conversation = self.conversation()
        self.service.transition(conversation.id, ConversationStatus.RESUELTO, "SOL")
        reopened = self.service.transition(conversation.id, ConversationStatus.EN_CURSO, "SOL")
        self.assertEqual(reopened.status, ConversationStatus.EN_CURSO)

    def test_resolved_cannot_go_directly_to_new(self):
        conversation = self.conversation()
        self.service.transition(conversation.id, ConversationStatus.RESUELTO, "SOL")
        with self.assertRaisesRegex(ValueError, "transición no permitida"):
            self.service.transition(conversation.id, ConversationStatus.NUEVO, "SOL")


class FilterAndCounterTests(InboxTestCase):
    def setUp(self):
        super().setUp()
        self.ana = self.conversation(name="Ana Demo", subject="Retiro")
        self.service.receive(self.ana.id, "¿Puedo retirar hoy?")
        self.luis = self.service.open_conversation("pilar", "Luis Demo", subject="Consulta")
        self.service.assign(self.luis.id, "SOL", "SOL")
        self.service.transition(self.luis.id, ConversationStatus.EN_CURSO, "SOL")

    def test_filters_compose(self):
        result = self.service.search(ConversationFilter(business="Consultorio BC", branch="Pilar", status=ConversationStatus.EN_CURSO, assigned_operator="SOL", text="Luis"))
        self.assertEqual([self.luis.id], [item.id for item in result])

    def test_text_filter_searches_message_body(self):
        self.assertEqual([self.ana.id], [item.id for item in self.service.search(ConversationFilter(text="retirar hoy"))])

    def test_counts_include_zero_states(self):
        counts = self.repo.counts()
        self.assertEqual((1, 1, 0), (counts[ConversationStatus.NUEVO], counts[ConversationStatus.EN_CURSO], counts[ConversationStatus.RESUELTO]))

    def test_account_filter(self):
        self.assertEqual([self.ana.id], [item.id for item in self.service.search(ConversationFilter(account_id="asuncion-centro"))])


class MigrationTests(unittest.TestCase):
    def test_second_migration_is_idempotent_and_schema_is_complete(self):
        repository = SQLiteCommunicationsRepository(":memory:")
        try:
            repository.migrate()
            self.assertTrue(repository.schema_looks_valid())
            with repository._connection() as db:
                versions = [r[0] for r in db.execute("SELECT version FROM schema_migrations ORDER BY version")]
            self.assertEqual(["001", "002"], versions)
        finally:
            repository.close()


class DemoTests(InboxTestCase):
    def test_demo_seed_is_explicit_fictitious_and_idempotent(self):
        # Este caso parte con cuentas configuradas pero sin conversaciones.
        self.assertEqual(3, self.service.seed_demo())
        self.assertEqual(0, self.service.seed_demo())
        conversations = self.service.search()
        self.assertEqual(3, len(conversations))
        self.assertTrue(all("Fict" in c.contact_name or "Ejemplo" in c.contact_name for c in conversations))
