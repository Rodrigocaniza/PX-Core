CREATE TABLE IF NOT EXISTS communication_accounts (
    id TEXT PRIMARY KEY,
    business TEXT NOT NULL,
    branch TEXT NOT NULL,
    label TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'SIMULADO',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES communication_accounts(id),
    contact_name TEXT NOT NULL,
    contact_reference TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'NUEVO' CHECK(status IN ('NUEVO','EN_CURSO','RESUELTO')),
    assigned_operator TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK(direction IN ('ENTRANTE','SALIENTE')),
    body TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    operator TEXT NOT NULL DEFAULT '',
    provider_reference TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS communication_audit (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_queue ON conversations(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_account ON conversations(account_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON conversation_messages(conversation_id, occurred_at, id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON communication_audit(entity_type, entity_id, sequence);
