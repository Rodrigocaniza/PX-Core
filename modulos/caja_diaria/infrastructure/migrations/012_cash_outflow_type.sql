ALTER TABLE cash_entries ADD COLUMN outflow_type TEXT NOT NULL DEFAULT '';

UPDATE cash_entries
SET outflow_type = CASE
    WHEN COALESCE(expenses, 0) > 0 THEN 'GASTO'
    WHEN COALESCE(withdrawal, 0) > 0 THEN 'ENTREGA_ADMINISTRACION'
    ELSE ''
END
WHERE outflow_type = '';

CREATE INDEX IF NOT EXISTS idx_cash_entries_outflow_type
ON cash_entries(cash_day_id, outflow_type, created_at)
WHERE outflow_type <> '';
