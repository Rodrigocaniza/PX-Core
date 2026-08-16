# Test Evidence — BC-CAJA-RC18-UX-VIEWSONIC-24-001

Base canónica: `0934471` (`feature/bc-caja-rc17-planilla-continua-pdf-001`).
Rama de misión: `feature/bc-caja-rc18-ux-viewsonic-24-001`.

## Regresión canónica

```
python -m pytest -q
222 passed, 5 warnings
```

Línea base en canónico antes de RC18: 217 PASS + 5 FAIL (RC16/RC17 PDF, ver
abajo). RC18 cierra esos 5 y suma 11 pruebas propias → 222 PASS / 0 FAIL.

## Pruebas focalizadas por slice

```
python -m pytest tests/caja_diaria/test_ux_viewsonic_24_kpi.py \
                 tests/caja_diaria/test_ux_1080p_layout.py \
                 tests/caja_diaria/test_ux004_visual_contract.py \
                 tests/caja_diaria/test_ux006_reference_contract.py -q
24 passed
```

- `test_ux_viewsonic_24_kpi.py` (nuevo, 11 pruebas): los seis importes
  canónicos siguen presentes; Venta/Efectivo/Esperado son los principales;
  el principal es mayor que el secundario y que el título; full-hd supera al
  compacto y a los 10 px previos; los pisos de cabecera 52/42 se conservan;
  la cabecera se ajusta al contenido real; las etiquetas declaran altura
  propia; el resumen queda en dos bloques; las métricas económicas del perfil
  no cambian.
- `test_ux_1080p_layout.py`: sin cambios, sigue en PASS.
- `test_ux004_visual_contract.py` / `test_ux006_reference_contract.py`:
  actualizados para verificar los KPI sobre las constantes de módulo, ya que
  RC18 los movió de literal embebido a `KPI_PRINCIPALES` / `KPI_SECUNDARIOS`.
  El contrato verificado es el mismo y ahora es más fuerte que un `assertIn`
  sobre texto fuente.

## Smoke GUI real

`tools/capture_caja_rc18.py` abre la ventana real sobre un directorio de datos
temporal, siembra una jornada (apertura 500.000, ocho ventas, un gasto y una
entrega), consulta y mide la cabecera renderizada. No abre ni cierra caja y no
envía correo.

```
BC_CAJA_RC18_VISUAL_SMOKE_OK resolution=1920x1080 kpi_principal=20 kpi_secundario=13
  cabecera_alto=55 importes={'Venta': '1.440.000', 'Efectivo': '1.080.000',
  'Esperado': '1.240.000', 'Tarj./Transf.': '360.000', 'Gastos': '90.000',
  'Entregado': '250.000'} emails=0 new_closures=0

BC_CAJA_RC18_VISUAL_SMOKE_OK resolution=1366x768 kpi_principal=11 kpi_secundario=9
  cabecera_alto=44 importes={...idénticos...} emails=0 new_closures=0
```

Comprobaciones que la sonda hace fallar si se rompen: los seis importes
presentes, tamaños homogéneos dentro de cada bloque, principal > secundario,
dos bloques disjuntos, importes efectivamente calculados y ningún importe
principal por debajo del borde de la cabecera.

Conciliación aritmética de los importes mostrados: esperado = 500.000 apertura
+ 1.080.000 efectivo − 90.000 gastos − 250.000 entregado = **1.240.000**, que
es lo que la UI muestra.

Capturas: `resumen-1920x1080.png`, `resumen-1366x768.png`.

## Fallas preexistentes cerradas

Las 5 fallas de PDF (`test_rc16_daily_envelope_report.py` ×2,
`test_rc17_continuous_daily_report.py` ×3) ya fallaban en `0934471` antes de
tocar nada, verificado ejecutándolas en el worktree canónico. Causa:
`representative_close()` abre con `utc_now()` y cierra en fecha fija del
15-08-2026, de modo que desde el 16-08-2026 el cierre queda antes de la
apertura y el dominio lo rechaza. Es un defecto del fixture, no del dominio:
la regla `closed_at >= opened_at` es correcta. Corregido fijando la apertura
de la jornada representativa, y la misma corrección en el generador de
evidencia RC17, verificado con `RC17_EVIDENCE_OK pages=2`.
