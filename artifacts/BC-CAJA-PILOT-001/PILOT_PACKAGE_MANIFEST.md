# Pilot package manifest

Artifact: `releases/BC-CAJA-PILOT-001.zip`

- ZIP size: 21,013,755 bytes.
- ZIP SHA-256: `62CF3EE4D157FE1E8AC6ED54C5D943324F382413E3F08051923EF7D258AB04F3`.
- Executable: `BC-Caja/BC-Caja.exe`.
- Executable SHA-256: `ABDB1AC9AF288A5319DACB958251C2C6098DDAFE45C708D52D9B6612AE81C07D`.
- Extracted runtime: 1,024 files, 44,490,772 bytes.
- Build: Python 3.14.6, PyInstaller 6.21.0, Windows 10 x64, `pilot/build_pilot.ps1`.

Top-level package contents:

- `BC-Caja.exe`
- `_internal/` (embedded Python/runtime, CustomTkinter, OpenPyXL, SQLite and migrations)
- `INSTALACION.txt`
- `GUIA_RAPIDA.txt`
- `VERSION.txt`

Exclusion scan: zero `.git`, tests, internal mission artifacts, caches, `.pyc`, development databases or `.sqlite3` files. No workbook or real customer data is present.

The ZIP retains a single `BC-Caja/` root directory to prevent partial extraction. Runtime data is not part of this manifest because it is created externally at `%LOCALAPPDATA%\BC\Caja`.
