CREATE TABLE IF NOT EXISTS agreement_balance_corrections (
    entry_id TEXT PRIMARY KEY REFERENCES cash_entries(id) ON DELETE CASCADE,
    previous_balance_text TEXT NOT NULL,
    corrected_balance_text TEXT NOT NULL,
    corrected_at TEXT NOT NULL
);

INSERT OR IGNORE INTO agreement_balance_corrections(
    entry_id, previous_balance_text, corrected_balance_text, corrected_at
)
SELECT
    id,
    balance_text,
    CAST(MAX(0, COALESCE(total, 0) - COALESCE(cash, 0)
        - COALESCE(card_check, 0) - agreement_amount) AS TEXT),
    datetime('now')
FROM cash_entries
WHERE agreement_amount > 0
  AND balance_text <> CAST(MAX(0, COALESCE(total, 0) - COALESCE(cash, 0)
      - COALESCE(card_check, 0) - agreement_amount) AS TEXT);

UPDATE cash_entries
SET balance_text = CAST(MAX(0, COALESCE(total, 0) - COALESCE(cash, 0)
    - COALESCE(card_check, 0) - agreement_amount) AS TEXT)
WHERE agreement_amount > 0;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('011', datetime('now'));
