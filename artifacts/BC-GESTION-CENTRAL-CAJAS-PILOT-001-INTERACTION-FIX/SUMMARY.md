# Corrección interactiva

- Las cuatro tarjetas son botones con cursor y callback de detalle.
- Cada detalle identifica la unidad y ofrece `← Volver al panel`.
- `Actualizar` reconstruye datos y muestra hora/cantidad de alertas.
- Filtro real: Todas, Con alertas, Sin alertas.
- Selección simple y doble clic de alertas enlazados.
- Reconocimiento actualiza la lista y deja auditoría durable.
- El reconocimiento no se recrea mientras persiste la misma condición.
- Clics incompletos muestran mensaje y estado; errores se registran localmente
  en `Data/Logs/ui-errors.log`, sin secretos ni payloads sensibles.
- El EXE incluye `--interaction-smoke` para pulsar widgets reales, reiniciar y
  comprobar persistencia sobre datos sintéticos aislados.
