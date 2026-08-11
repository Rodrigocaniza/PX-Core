# Pilot package manifest

Artifact: `releases/BC-CAJA-PILOT-001.zip`

- UX mission: `BC-CAJA-UX-004`.
- ZIP size: 31,643,984 bytes.
- ZIP SHA-256: `52F29A087BE19C653294A6AD8C6868D1FCF60DAA7C87557D44B43C3897F176F9`.
- Executable: `BC-Caja/BC-Caja.exe`.
- Executable SHA-256: `9411EBF7A087A68AD7D61357893B4DDA8B53EA61CAF3966AE28E02D263F51AFD`.
- ZIP entries: 1,057.
- Build: Python 3.13.14, PyInstaller 6.21.0, Windows 11 x64, `pilot/build_pilot.ps1`.

Top-level package contents:

- `BC-Caja.exe`
- `_internal/` (embedded Python/runtime, CustomTkinter, OpenPyXL, SQLite and migrations, including `003_laboratory.sql`)
- `INSTALACION.txt`
- `GUIA_RAPIDA.txt`
- `VERSION.txt` identifying `BC-CAJA-UX-004`

Exclusion scan: zero `.git`, tests, internal mission artifacts, caches, `.pyc`, development databases or `.sqlite3` files. No workbook or real customer data is present.

The ZIP retains a single `BC-Caja/` root directory. Runtime data remains external at `%LOCALAPPDATA%\BC\Caja`.
