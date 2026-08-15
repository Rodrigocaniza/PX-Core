# Installation evidence

- Publicación protegida: commit funcional `dbd9799`, rama `feature/bc-caja-rc17-planilla-continua-pdf-001`, push sin force y remoto `0/0` tras la publicación.
- Instalación transaccional: BC Caja `1.0.0-rc.17`; EXE instalado SHA256 `25293DC98C3780F035E7EA06D7E710AF96058431E893F60749F85B314AF7CC50`.
- Rollback: RC16 íntegro en `%LOCALAPPDATA%\Programs\BC-Caja-Pilot.rollback-rc16-20260815`.
- Snapshot: data root previo completo en `%LOCALAPPDATA%\BC\Caja-RC17-preinstall-20260815`.
- Preservación: 31 archivos sustantivos coinciden byte a byte; sólo los archivos SQLite transitorios `-wal` y `-shm`, ambos sin datos pendientes antes del cambio, desaparecieron tras el cierre limpio.
- SQLite: `PRAGMA integrity_check=ok`; 6 cajas, 1 registro outbox y 1 estado `SENT`, sin variación pre/post.
- Smoke real: el ejecutable instalado inició, mostró la UI y cerró correctamente.
- Smoke PDF: se usó un backup SQLite temporal del último cierre existente; 1 página A4 horizontal, estado `CLOSED`, Totales por vendedora antes de la planilla, columna Doctor, contenido clínico/firma ausente y firma `%PDF-` válida.
- Correo y cierre: cero cierres y cero correos nuevos; SMTP, secretos, outbox, configuración y backups preservados.
