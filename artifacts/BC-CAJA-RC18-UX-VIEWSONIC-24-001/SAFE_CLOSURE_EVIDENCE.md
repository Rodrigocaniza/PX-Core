# Safe Closure Evidence — BC-CAJA-RC18-UX-VIEWSONIC-24-001

- Visual Gate humano: **PASS** en ViewSonic 24" físico. Aceptados jerarquía,
  legibilidad, distribución y altura de cabecera.
- Cadena final: regresión canónica → smoke GUI real → Artifact Consistency →
  commit protegido → push verificado.
- Pruebas finales inmediatamente antes de publicar: **222 PASS / 0 FAIL**.
- Smoke GUI real inmediatamente antes de publicar: PASS en 1920×1080
  (`kpi_principal=20`, `kpi_secundario=13`, `cabecera_alto=55`) y en 1366×768
  (`kpi_principal=11`, `kpi_secundario=9`, `cabecera_alto=44`), con
  `emails=0` y `new_closures=0` en ambas corridas.
- Allowlist de publicación: `CajaDiaria.py`; `tests/caja_diaria/
  test_ux_viewsonic_24_kpi.py`; `test_ux004_visual_contract.py`;
  `test_ux006_reference_contract.py`; `test_rc16_daily_envelope_report.py`;
  `tools/capture_caja_rc18.py`; `tools/generate_caja_rc17_pdf_evidence.py`;
  artifacts finales RC18.
- Exclusiones obligatorias verificadas como vacías: `.test-tmp/**`,
  `.pytest_cache/**`, `build/**`, `dist/**` y **todo cambio de
  Comunicaciones**, que permanece intacto y sin tocar en el directorio
  principal de PX-Core.
- Staging: rutas explícitas solamente, seguido por `git diff --cached
  --name-status`, control temporal vacío y `git diff --cached --check` limpio.
- Publicación: commit funcional `3cda622` y commit de cierre documental, push
  **sin force**.
- Instalación: **no ejecutada**. Fuera del alcance autorizado en esta
  intervención; RC17 permanece como versión instalada y disponible.
