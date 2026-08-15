# Safe Closure Evidence

- Cadena: Librarian PASS → QA PASS → Auditor PASS.
- Allowlist de publicación: `CajaDiaria.py`; `admin_ops.py`; `close_report.py`; `continuous_report.py`; versión/build/docs; tests RC15/RC17; generador RC17; artifacts finales RC17; ZIP RC17.
- Exclusiones obligatorias: `.test-tmp/**`, `.pytest_cache/**`, build/dist locales, preview real temporal y cualquier archivo ajeno al alcance.
- Staging: rutas explícitas solamente, seguido por `git diff --cached --name-status`, control temporal vacío y `git diff --cached --check`.
- Publicación autorizada y completada: commit funcional `dbd9799`, push sin force y verificación remota `0/0`.
- Instalación autorizada y completada mediante gate transaccional: RC16 detenido y conservado, snapshot preinstalación, reemplazo exclusivo del programa, smoke e `integrity_check=ok`; rollback RC16 disponible.
