# Installation Evidence

- Publicación protegida: commit `1f30b9b19134bff27ab56bf640d4457ed68d2fc7`, rama RC16, remoto `0/0`, sin force.
- Instalación: BC Caja `1.0.0-rc.16`; EXE instalado SHA256 `8A7602D9BD8D4399A24E7AABCC2090858AB6760D6461553207CD33BC6A5F43EA`.
- Transacción: RC15 y snapshot de datos conservados en un directorio de rollback separado; sólo se reemplazó el directorio del programa.
- Preservación: 33 archivos del data root coinciden byte a byte con el snapshot final; SMTP, outbox, backups y configuración permanecen presentes.
- SQLite: 10 bases detectadas pasaron `integrity_check`; la base activa finalizó con `integrity_check=ok`.
- Smoke instalado: el ejecutable RC16 inició y cerró correctamente.
- Ruta PDF/correo: outbox activo conserva un único estado `SENT`; `sent_at` presente; reporte adjunto existente con firma `%PDF-`; SMTP y destinatario configurados, sin revelar valores.
- Idempotencia: no se creó cierre ni envío adicional durante instalación o smoke.
- Rollback: RC15 y el snapshot previo están disponibles si se detecta una regresión posterior.
