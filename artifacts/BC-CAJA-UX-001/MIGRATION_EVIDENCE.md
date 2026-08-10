# Migration evidence

- Migration: `003_laboratory.sql`.
- Change: adds `cash_entries.laboratory TEXT NOT NULL DEFAULT ''`.
- Existing 001 database migration test: PASS through versions 001, 002 and 003.
- Existing entries preserve data and receive empty Laboratory.
- New manual entries preserve Laboratory through create, edit, SQLite reload and revision snapshots.
- Excel imports remain compatible and default Laboratory to empty because the validated workbook has no dedicated column.