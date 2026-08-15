# Safe Closure Evidence

- Cadena independiente: Librarian PASS → QA PASS → Auditor PASS.
- Pruebas: 3 específicas y 208 totales, todas PASS.
- Artifact Consistency: ZIP, EXE y PDF coinciden con `MANIFEST.json`; paquete con raíz única, 1149 entradas y cero datos/secretos/backups.
- Evidencia visual final: `release-v6-page-01.png` a `release-v6-page-14.png`.
- Alcance permitido para staging: `CajaDiaria.py`, `requirements.txt`, wiring/renderer PDF, build y documentación rc.16, tests rc15/rc16, generador de evidencia, directorio final de artifacts y ZIP rc.16.
- Exclusión obligatoria: `.test-tmp/**`, build/dist locales y cualquier archivo ajeno al alcance.
- Publicación: staging explícito, auditoría de diff staged y push sin force únicamente si el árbol staged respeta la allowlist.
- Instalación: gate separado; detener aplicación, snapshot y hashes pre de datos/configuración/backups, reemplazar sólo binarios, smoke, SQLite `integrity_check`, comparación post y rollback a rc.15 ante cualquier fallo.
