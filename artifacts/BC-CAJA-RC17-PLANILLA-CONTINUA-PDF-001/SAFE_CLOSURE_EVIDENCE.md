# Safe Closure Evidence

- Cadena: Librarian PASS → QA PASS → Auditor PASS.
- Allowlist de publicación: `CajaDiaria.py`; `admin_ops.py`; `close_report.py`; `continuous_report.py`; versión/build/docs; tests RC15/RC17; generador RC17; artifacts finales RC17; ZIP RC17.
- Exclusiones obligatorias: `.test-tmp/**`, `.pytest_cache/**`, build/dist locales, preview real temporal y cualquier archivo ajeno al alcance.
- Staging: rutas explícitas solamente, seguido por `git diff --cached --name-status`, control temporal vacío y `git diff --cached --check`.
- Publicación: requiere HUMAN_GATE exacto; push sin force y verificación remota `0/0`.
- Instalación: requiere HUMAN_GATE exacto y gate transaccional separado con RC16 detenido, snapshot/hashes pre/post de SQLite/SMTP/outbox/backups/configuración, reemplazo exclusivo de programa, smoke e `integrity_check`; rollback RC16 ante fallo.
