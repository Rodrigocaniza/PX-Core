ALTER TABLE cash_entries ADD COLUMN withdrawal INTEGER;
ALTER TABLE cash_entries ADD COLUMN withdrawal_destination TEXT NOT NULL DEFAULT '';
ALTER TABLE cash_entries ADD COLUMN performed_by TEXT NOT NULL DEFAULT '';

ALTER TABLE cash_days ADD COLUMN initial_cash_expected INTEGER;
ALTER TABLE cash_days ADD COLUMN initial_cash_difference INTEGER;
ALTER TABLE cash_days ADD COLUMN initial_cash_source_day_id TEXT;
ALTER TABLE cash_days ADD COLUMN initial_cash_source_kind TEXT NOT NULL DEFAULT '';
ALTER TABLE cash_days ADD COLUMN initial_cash_source_count_id TEXT;
ALTER TABLE cash_days ADD COLUMN opened_by TEXT NOT NULL DEFAULT '';
ALTER TABLE cash_days ADD COLUMN closing_withdrawals INTEGER;

CREATE INDEX IF NOT EXISTS idx_cash_days_unit_closed_date
ON cash_days(unit, business_date DESC) WHERE status = 'CLOSED';

CREATE INDEX IF NOT EXISTS idx_cash_entries_withdrawals
ON cash_entries(cash_day_id, created_at) WHERE withdrawal IS NOT NULL;
