# Artifact Consistency — BC-CAJA-RC18-UX-VIEWSONIC-24-001

## Alcance declarado vs. archivos tocados

| Archivo | Naturaleza | Dentro de alcance |
|---|---|---|
| `CajaDiaria.py` | presentación de cabecera y resumen | sí |
| `tests/caja_diaria/test_ux_viewsonic_24_kpi.py` | pruebas nuevas del contrato RC18 | sí |
| `tools/capture_caja_rc18.py` | sonda de smoke GUI real | sí |
| `tests/caja_diaria/test_ux004_visual_contract.py` | contrato adaptado a constantes de módulo | sí |
| `tests/caja_diaria/test_ux006_reference_contract.py` | contrato adaptado a constantes de módulo | sí |
| `tests/caja_diaria/test_rc16_daily_envelope_report.py` | fixture determinista | declarado fuera de UX, ver SUMMARY |
| `tools/generate_caja_rc17_pdf_evidence.py` | misma corrección de fecha | declarado fuera de UX, ver SUMMARY |

Sin cambios en dominio, servicios, repositorio SQLite, migraciones, correo,
cierre, arqueo, pedidos, convenios, salidas de caja, FactuFácil ni datos.

## Invariantes verificados

- Los seis importes canónicos del resumen siguen presentes y con el mismo
  significado; sólo cambia su jerarquía visual y su agrupación.
- Ninguna fórmula ni regla económica fue tocada: la conciliación
  500.000 + 1.080.000 − 90.000 − 250.000 = 1.240.000 se verifica contra lo que
  la UI muestra en el smoke real.
- El perfil compacto 1366×768 conserva sus métricas validadas
  (`fuente 9`, `fila 27`) y su piso de cabecera.
- La grilla de movimientos conserva su mínimo de cinco filas.
- Privacidad financiera y scrollbars nativas intactas (cubierto por
  `test_ux_1080p_layout.py`).

## Evidencia presente

- `SUMMARY.md`
- `TEST_EVIDENCE.md`
- `VISUAL_REVIEW.md`
- `ARTIFACT_CONSISTENCY.md`
- `WORKFLOW.json`
- `resumen-1920x1080.png`
- `resumen-1366x768.png`

## Consistencia de estado

`WORKFLOW.json` declara `SAFE_CLOSURE_READY` con
`publication: HUMAN_GATE_REQUIRED` y `commit/push/installation = false`, que es
coherente con el estado real del worktree: cambios presentes sin commit, sin
push y sin instalación. Se sigue el mismo precedente canónico de RC17, donde la
publicación requirió autorización humana explícita.
