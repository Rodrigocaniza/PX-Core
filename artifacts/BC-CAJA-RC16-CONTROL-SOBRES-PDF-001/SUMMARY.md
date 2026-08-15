# BC Caja RC16 — Control diario de sobres

El comprobante técnico vertical de RC15 se reemplaza por un informe A4 horizontal,
paginado y orientado al control operativo. Incluye resumen económico, una venta por
bloque, artículos múltiples sin duplicar cobros, recetas completas, alertas visuales,
salidas, anulaciones, totales por vendedora y espacio de firma.

No se modificaron cálculos, reglas económicas, cierre, SQLite, SMTP, outbox ni backups.
El mismo `generate_close_pdf` usado por el cierre produce el nuevo adjunto; la prueba de
correo confirma una sola fila outbox, un solo adjunto y cero reenvíos después de `SENT`.
