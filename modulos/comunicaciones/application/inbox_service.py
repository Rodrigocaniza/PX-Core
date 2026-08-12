"""Casos de uso de la bandeja y frontera estable de proveedores."""

from __future__ import annotations

from ..domain.inbox import Account, Conversation, ConversationFilter, ConversationStatus, Direction, Message, identifier


class SimulatedMessageProvider:
    """Proveedor determinista de demo; nunca usa red ni credenciales."""
    name = "SIMULADO"

    def send(self, *, conversation: Conversation, body: str) -> str:
        return f"sim-{conversation.id}-{identifier()[:8]}"


class InboxService:
    def __init__(self, repository, provider=None) -> None:
        self.repository = repository
        self.provider = provider or SimulatedMessageProvider()

    def open_conversation(self, account_id: str, contact_name: str, *, contact_reference: str = "", subject: str = "", actor: str = "SISTEMA") -> Conversation:
        conversation = Conversation(identifier(), account_id, contact_name.strip(), contact_reference.strip(), subject=subject.strip())
        self.repository.create_conversation(conversation, actor)
        return conversation

    def receive(self, conversation_id: str, body: str) -> Message:
        message = Message(identifier(), conversation_id, Direction.ENTRANTE, body.strip())
        self.repository.append_message(message, "PROVEEDOR SIMULADO")
        return message

    def reply(self, conversation_id: str, body: str, operator: str) -> Message:
        conversation = self.repository.get_conversation(conversation_id)
        if conversation is None:
            raise KeyError(conversation_id)
        operator = operator.strip()
        if not operator:
            raise ValueError("el operador es obligatorio")
        reference = self.provider.send(conversation=conversation, body=body)
        message = Message(identifier(), conversation_id, Direction.SALIENTE, body.strip(), operator=operator, provider_reference=reference)
        self.repository.append_message(message, operator)
        if conversation.status == ConversationStatus.NUEVO:
            self.repository.update_status(conversation_id, ConversationStatus.EN_CURSO, operator)
        return message

    def transition(self, conversation_id, status, actor):
        return self.repository.update_status(conversation_id, status, actor)

    def assign(self, conversation_id, operator, actor):
        return self.repository.assign(conversation_id, operator, actor)

    def search(self, filters=ConversationFilter()):
        return self.repository.list_conversations(filters)

    def seed_demo(self) -> int:
        """Carga ficticia explícita e idempotente; nunca pretende ser WhatsApp real."""
        accounts = (
            Account("demo-optica-asuncion", "Óptica Demo", "Asunción", "WhatsApp DEMO"),
            Account("demo-consultorio-pilar", "Consultorio Demo", "Pilar", "WhatsApp DEMO"),
        )
        for account in accounts:
            self.repository.save_account(account)
        if self.repository.list_conversations():
            return 0
        samples = (
            (accounts[0].id, "Ana Ficticia", "Pedido de lentes", "¿Mis lentes ya están listos?"),
            (accounts[1].id, "Luis Ficticio", "Confirmar turno", "Quiero confirmar mi turno de mañana."),
            (accounts[0].id, "Marta Ejemplo", "Horario", "¿Hasta qué hora atienden?"),
        )
        for account_id, contact, subject, body in samples:
            conversation = self.open_conversation(account_id, contact, subject=subject, actor="DEMO")
            self.receive(conversation.id, body)
        return len(samples)
