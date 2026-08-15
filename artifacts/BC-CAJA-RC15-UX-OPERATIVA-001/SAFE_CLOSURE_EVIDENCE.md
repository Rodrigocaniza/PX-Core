# Safe Closure Evidence

Librarian PASS → QA PASS → Auditor PASS.

La allowlist de commit se limita a:

- `CajaDiaria.py`
- `pilot/build_pilot.ps1`
- `pilot/package_docs/INSTALACION.txt`
- `pilot/package_docs/VERSION.txt`
- `tools/capture_caja_ux006.py`
- `tests/caja_diaria/test_rc15_ux_operativa.py`
- `artifacts/BC-CAJA-RC15-UX-OPERATIVA-001/**`
- `releases/BC-CAJA-1.0.0-rc.15-win64.zip`

Exclusión obligatoria: `.test-tmp/**`. La instalación reemplaza únicamente la
carpeta de programa y preserva `%LOCALAPPDATA%\BC\Caja`; requiere backup SQLite,
hashes pre/post de SQLite y secretos SMTP, conteo de backups y rollback RC14.
