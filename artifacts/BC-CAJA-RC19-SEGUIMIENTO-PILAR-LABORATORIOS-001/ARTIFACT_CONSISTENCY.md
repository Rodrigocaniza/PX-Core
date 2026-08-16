# Artifact Consistency — BC-CAJA-RC19-SEGUIMIENTO-PILAR-LABORATORIOS-001

## Alcance declarado vs. archivos tocados

| Archivo | Naturaleza | En alcance |
|---|---|---|
| `modulos/caja_diaria/domain/tracking.py` | dominio nuevo del circuito | sí |
| `modulos/caja_diaria/application/tracking_service.py` | servicio nuevo | sí |
| `modulos/caja_diaria/infrastructure/migrations/016_work_tracking.sql` | migración nueva | sí |
| `modulos/caja_diaria/infrastructure/sqlite_repository.py` | persistencia del seguimiento | sí, solo se agrega |
| `modulos/caja_diaria/ui/controller.py` | expone `controller.tracking` | sí, solo se agrega |
| `CajaDiaria.py` | pestaña Seguimiento | sí |
| `tests/caja_diaria/test_rc19_tracking_*.py` | pruebas nuevas | sí |
| `tools/capture_caja_rc19.py` | sonda de smoke GUI | sí |
| 4 pruebas con la cadena de migraciones | extendidas a 016 | declarado en SUMMARY |

## Invariantes verificados

- **Nada económico fue tocado.** Sin cambios en importes, fórmulas, totales,
  arqueos, cierres, correo, convenios ni comisiones. El repositorio solo recibe
  métodos nuevos; ningún método existente fue modificado.
- **Comunicaciones intacto.** Los cambios ajenos del directorio principal de
  PX-Core no fueron tocados: RC19 vive en su propio worktree.
- **`main` no fue tocada.** El trabajo va en rama de misión propia.
- **Un solo registro por trabajo.** Índice único sobre `order_id`; guardar dos
  veces no duplica ni el trabajo ni su traza (probado).
- **Transiciones validadas en dos capas.** `ALLOWED_TRANSITIONS` en el dominio
  y `CHECK` de estados en SQLite.
- **Auditoría preservada.** Cada transición guarda origen, destino, responsable,
  nota e instante; cada contacto guarda operadora, medio, resultado y plazo
  nuevo. Ambas tablas son append-only por secuencia.
- **Local-first.** Sin red en todo el circuito, verificado con `socket`
  inutilizado.
- **Fuera de alcance respetado.** Sin FactuFácil, sin entrega final al cliente,
  sin WhatsApp API, sin rediseño de Caja.

## Evidencia presente

`SUMMARY.md`, `TEST_EVIDENCE.md`, `ARTIFACT_CONSISTENCY.md`,
`SAFE_CLOSURE_EVIDENCE.md`, `WORKFLOW.json`, `seguimiento-1920x1080.png`,
`seguimiento-1366x768.png`.

## Consistencia de estado

`WORKFLOW.json` declara `CLOSED` con `commit`/`push` ejecutados e
`installation: false`. Coincide con el estado real: instalación no ejecutada,
RC17 sigue siendo la versión instalada.
