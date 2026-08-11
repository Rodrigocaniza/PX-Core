# Test evidence

- `python -m unittest discover -s tests -v`: PASS (55 tests).
- Domain, SQLite, audit revision history, Excel contract, UI controller and UI smoke: PASS.
- Operation E2E (create, edit, logical void, close, backup and restart): PASS.
- Pilot first-run on an empty temporary directory: PASS.
- UX-002 layout contract and 1366 x 768 GUI capture: PASS.
- Extracted packaged EXE first-run: exit 0, SQLite created externally, backup count 1.
- Artifact Consistency: 1,057 ZIP entries, forbidden entries 0.
- ZIP SHA-256: `03ECF69AB00271B0788C7778CE6AD85A624979360A20CFDE1C1950FAF7A1889B`.
- EXE SHA-256: `69629138AB29D7A30999E0C9DC6598741E7B3366E45E90C8C550AE5219C8D12C`.

The GUI capture used temporary empty storage. Productive data under
`%LOCALAPPDATA%\BC\Caja` was neither opened nor packaged.
