# Auditor — PASS

- La conexión abre `mode=ro` y degrada a `PRAGMA query_only=ON`; `INSERT`,
  `UPDATE` y `DELETE` fallan en la conexión real, comprobado por prueba.
- Los módulos no contienen sentencias de escritura ni de esquema; el receptor
  sigue siendo el único autor del inbox, la proyección y la auditoría.
- Base inexistente se lee como vacío y no se crea el archivo: abrir la pantalla
  no inicializa almacenamiento.
- `dashboard.read` gobierna proyecciones y totales; `audit.read` gobierna
  rechazos y duplicados, y su ausencia falla cerrado en servicio y en pantalla.
- Un principal atado a una unidad sólo ve su sucursal en filas, totales y
  auditoría; pedir otra sucursal devuelve vacío, no error informativo.
- Los rechazos muestran el motivo ya saneado por el receptor; no exponen
  credenciales, firmas ni cuerpos.
- Orden estable por `occurred_at`/`event_id`, idéntico al del receptor.
- No hay red, endpoint, servicio ni escritura hacia las sedes.
