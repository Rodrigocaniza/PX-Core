# BC-CAJA-TIME-001 — Test Evidence

- Canonical base: `e0e0c7f2b9a7cecf3d3a27d0cae5dff8b4efa7e4`.
- Full BC Caja suite: **62/62 PASS**.
- New TIME-001 focal tests: **5/5 PASS**.
- Existing UX-002 and UX-004 contracts: **PASS**.
- Existing operation E2E, backup, restart and first-run self-checks: **PASS**.
- SQLite migration path from schema `001` through `004`: **PASS**.
- SQLite persistence/reload of timestamps, duration and overtime: **PASS**.
- `git diff --check`: **PASS**.

The Windows EXE/ZIP was not rebuilt in this Linux execution environment because
the canonical package pipeline is PowerShell + Windows PyInstaller. The prior
validated ZIP therefore remains unchanged at SHA-256
`52F29A087BE19C653294A6AD8C6868D1FCF60DAA7C87557D44B43C3897F176F9` until a
Windows packaging run incorporates TIME-001.
