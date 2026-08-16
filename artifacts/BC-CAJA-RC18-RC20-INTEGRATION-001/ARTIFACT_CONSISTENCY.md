# Artifact Consistency — BC-CAJA-RC18-RC20-INTEGRATION-001

## Alcance de la integración

| Archivo | Naturaleza | En alcance |
|---|---|---|
| `modulos/caja_diaria/application/tracking_service.py` | ventana por defecto de 3 días | sí, ajuste autorizado |
| `CajaDiaria.py` | el diálogo precarga esa ventana | sí |
| `tests/caja_diaria/test_rc18_rc20_integration.py` | focused tests del default | sí |
| `artifacts/BC-CAJA-RC18-RC20-INTEGRATION-001/` | evidencia de integración | sí |

Todo lo demás llega **heredado por linealidad**, sin recommit ni cherry-pick.

## Invariantes verificados

- **Sin duplicación de commits**: la rama nace en el tip de RC20; los 6
  commits de la cadena son los mismos objetos, no copias.
- **Sin reescritura de ramas CLOSED**: RC18, RC19 y RC20 quedan en sus HEAD
  originales y sincronizadas con origin.
- **Sin force-push**.
- **`main` no fue tocada.**
- **Comunicaciones intacto**: la integración vive en su propio worktree; el
  directorio principal de PX-Core conserva sus cambios ajenos sin modificar.
- **Sin lógica económica, correo, cierre, arqueo ni convenio tocados**,
  verificado por diff sobre la cadena completa, no por afirmación.
- **Criterio canónico de selección preservado**: fecha de creación del pedido.
- **Datos preservados**: migración 015→017 validada contra copia de la base
  real, con censo idéntico antes y después.
- **Privacidad de capturas**: las nueve capturas de este artifact provienen de
  sondas que capturan la ventana de Caja o el bounding box del diálogo. No hay
  escritorio completo ni contenido de otras aplicaciones.

## Evidencia presente

`SUMMARY.md`, `TEST_EVIDENCE.md`, `ARTIFACT_CONSISTENCY.md`,
`INSTALL_READINESS.md`, `WORKFLOW.json`, y seis capturas:
`rc18-resumen-{1920x1080,1366x768}.png`,
`rc19-seguimiento-{1920x1080,1366x768}.png`,
`rc20-envio-{1920x1080,1366x768}.png` más las de laboratorios generadas por la
sonda RC20.

## Consistencia de estado

`WORKFLOW.json` declara la integración `CLOSED` con commit y push ejecutados e
`installation: PENDING_HUMAN_GATE`, coherente con el estado real: el paquete
queda preparado y la instalación no fue ejecutada.
