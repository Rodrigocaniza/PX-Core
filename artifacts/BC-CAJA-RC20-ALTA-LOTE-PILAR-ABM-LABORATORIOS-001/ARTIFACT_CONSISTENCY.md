# Artifact Consistency — BC-CAJA-RC20-ALTA-LOTE-PILAR-ABM-LABORATORIOS-001

## Alcance declarado vs. archivos tocados

| Archivo | Naturaleza | En alcance |
|---|---|---|
| `modulos/caja_diaria/domain/tracking.py` | `PilarShipment`, `shipment_progress`, `shipment_id` | sí, solo se agrega |
| `modulos/caja_diaria/application/tracking_service.py` | candidatos, alta de lote, ABM | sí, solo se agrega |
| `modulos/caja_diaria/infrastructure/migrations/017_pilar_shipments.sql` | migración nueva | sí |
| `modulos/caja_diaria/infrastructure/sqlite_repository.py` | persistencia del lote y candidatos | sí |
| `CajaDiaria.py` | dos botones y dos diálogos en Seguimiento | sí |
| `tests/caja_diaria/test_rc20_*.py` | pruebas nuevas | sí |
| `tools/capture_caja_rc20.py` | sonda de smoke GUI | sí |
| 5 pruebas con la cadena de migraciones | extendidas a 017 | declarado en SUMMARY |

## Invariantes verificados

- **Sin lógica económica tocada.** Ningún cambio en importes, fórmulas,
  totales, arqueos, cierres, correo, convenios ni comisiones.
- **`main` no fue tocada**; el trabajo va en rama de misión propia.
- **Comunicaciones intacto**: RC20 vive en su propio worktree.
- **RC19 no fue reimplementado.** El alta de lote delega en las transiciones y
  en `reception_progress` ya existentes; la recepción uno por uno es el mismo
  código.
- **La identidad individual del trabajo se conserva.** El lote agrupa; cada
  `TrackedWork` mantiene id, traza, estado y enlaces propios.
- **Sin segunda fuente de verdad del cliente.** El seguimiento no copia
  teléfono ni documento; se reutiliza `orders`.
- **Sin borrado físico de laboratorios.** Solo baja lógica, con advertencia
  cuando hay historial asociado.
- **Doble defensa contra duplicados**: exclusión en la consulta de candidatos y
  verificación previa a la escritura, sin dejar lotes a medias.
- **Local-first**: verificado con `socket` inutilizado.
- **Sin contenido ajeno en artifacts**: las capturas se recortan al diálogo.

## Evidencia presente

`SUMMARY.md`, `TEST_EVIDENCE.md`, `ARTIFACT_CONSISTENCY.md`,
`SAFE_CLOSURE_EVIDENCE.md`, `WORKFLOW.json`, `envio-1920x1080.png`,
`laboratorios-1920x1080.png`, `envio-1366x768.png`,
`laboratorios-1366x768.png`.

## Consistencia de estado

`WORKFLOW.json` declara `CLOSED` con commit y push ejecutados e
`installation: false`, coherente con el estado real: instalación no ejecutada,
RC17 sigue siendo la versión instalada.
