# Artifact Consistency — BC-CAJA-RC21-TABLA-SEGUIMIENTO-LOGISTICA-001

## Archivos tocados

| Archivo | Naturaleza | En alcance |
|---|---|---|
| `modulos/caja_diaria/application/tracking_service.py` | rótulos, `physical_status`, `alert`, `work_type`, `SIN ASIGNAR` | sí, solo se agrega |
| `CajaDiaria.py` | cinco columnas y chips de estado | sí |
| `tests/caja_diaria/test_rc21_tabla_seguimiento.py` | pruebas nuevas | sí |
| `tools/gui_capture.py` | captura segura compartida | sí, regla de privacidad vigente |
| `tools/capture_caja_rc18.py` / `rc19` / `rc20` | migradas a la captura segura | sí |

## Invariantes verificados

- **Modelo RC19 intacto**: `ATRASADO` y `CONFIRMADO PARA MAÑANA` siguen siendo
  derivados; ninguna migración nueva, ningún cron, ninguna reescritura de
  filas. Verificado además contra la base.
- **Vendedora solo sale de esta vista**: `saleswoman` sigue en el dominio y en
  las otras grillas.
- **Sin lógica económica, cierres, correo, convenios ni arqueos tocados.**
- **FactuFácil y Comunicaciones intactos.**
- **`main` no fue tocada**; rama de misión propia.
- **Sin migraciones nuevas**: el esquema sigue en 001–017.
- **Privacidad**: ninguna captura versionada contiene contenido fuera de la
  aplicación; las sondas ya no leen la pantalla.

## Evidencia

`SUMMARY.md`, `TEST_EVIDENCE.md`, `ARTIFACT_CONSISTENCY.md`, `WORKFLOW.json`,
`tabla-1920x1080.png`, `tabla-1366x768.png`, `rc18-1920x1080.png`,
`rc20-envio-1920x1080.png`, `rc20-laboratorios-1920x1080.png`.

## Estado

`WORKFLOW.json` declara `CLOSED` con `installation: PENDING_HUMAN_GATE`,
coherente con el estado real: producción sigue en `1.0.0-rc.20` y este cambio
todavía no se instaló.
