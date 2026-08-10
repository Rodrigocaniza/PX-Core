# Pilot package manifest

Artifact: `releases/BC-CAJA-PILOT-001.zip`

- UX mission: `BC-CAJA-UX-001`.
- ZIP size: 21,018,149 bytes.
- ZIP SHA-256: `A9A44007F007623139FDD0D37D5BC35F3D731A8A2BC0AB01B3F7FAA14E8640A0`.
- Executable: `BC-Caja/BC-Caja.exe`.
- Executable SHA-256: `8D8B2CE9D7F6D2ECD9DE9CEA92D9EB3BA3E7C2497B87C51B9C2C215BEAC143F3`.
- Extracted runtime: 1,025 files, 44,495,259 bytes.
- Build: Python 3.14.6, PyInstaller 6.21.0, Windows 10 x64, `pilot/build_pilot.ps1`.

Top-level package contents:

- `BC-Caja.exe`
- `_internal/` (embedded Python/runtime, CustomTkinter, OpenPyXL, SQLite and migrations, including `003_laboratory.sql`)
- `INSTALACION.txt`
- `GUIA_RAPIDA.txt`
- `VERSION.txt` identifying `BC-CAJA-UX-001`

Exclusion scan: zero `.git`, tests, internal mission artifacts, caches, `.pyc`, development databases or `.sqlite3` files. No workbook or real customer data is present.

The ZIP retains a single `BC-Caja/` root directory. Runtime data remains external at `%LOCALAPPDATA%\BC\Caja`.