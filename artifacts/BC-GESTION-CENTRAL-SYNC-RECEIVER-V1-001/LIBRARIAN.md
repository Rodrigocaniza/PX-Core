# Librarian — PASS

- Slice aislado en receiver, documentación y pruebas; no modifica Historial ni UI.
- Reutiliza `Unit`, contratos Sync y Security ↔ Sync; no mantiene catálogo paralelo.
- Backend nativo delega documentos, firmas y revocación a BC Seguridad.
- Harness y claves ilustrativas existen sólo en tests.
- No hay producción, servicios, credenciales, IP ni migración operativa.
