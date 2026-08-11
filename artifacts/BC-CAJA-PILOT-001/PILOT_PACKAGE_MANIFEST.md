# Pilot package manifest

Artifact: `releases/BC-CAJA-PILOT-001.zip`

- UX mission: `BC-CAJA-UX-002`.
- ZIP size: 31,642,630 bytes.
- ZIP SHA-256: `03ECF69AB00271B0788C7778CE6AD85A624979360A20CFDE1C1950FAF7A1889B`.
- Executable: `BC-Caja/BC-Caja.exe`.
- Executable SHA-256: `69629138AB29D7A30999E0C9DC6598741E7B3366E45E90C8C550AE5219C8D12C`.
- ZIP entries: 1,057.
- Build: Python 3.13.14, PyInstaller 6.21.0, Windows 11 x64, `pilot/build_pilot.ps1`.

Top-level package contents:

- `BC-Caja.exe`
- `_internal/` (embedded Python/runtime, CustomTkinter, OpenPyXL, SQLite and migrations, including `003_laboratory.sql`)
- `INSTALACION.txt`
- `GUIA_RAPIDA.txt`
- `VERSION.txt` identifying `BC-CAJA-UX-002`

Exclusion scan: zero `.git`, tests, internal mission artifacts, caches, `.pyc`, development databases or `.sqlite3` files. No workbook or real customer data is present.

The ZIP retains a single `BC-Caja/` root directory. Runtime data remains external at `%LOCALAPPDATA%\BC\Caja`.
