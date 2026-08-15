# QA report

- Misión: `BC-GESTION-CENTRAL-SUPERVISION-OPERATIVA-001`
- Rol: `QA`
- Fecha: `2026-08-15`
- Alcance: exclusivamente `.worktrees/gc-sol-001`
- Verdict: **PASS**

## Resultado funcional e integración

- Dashboard, selector de fechas, resumen por unidad y detalle diario: PASS.
- Estados de sincronización e integridad, alertas y transiciones: PASS.
- Mensajes por unidad/PC con outbox local idempotente `PENDING`: PASS.
- Revisión campo por campo de `CIERRE`, `VENTAS_SOBRES`, `SALIDAS`, `ARQUEO` y `PDF`, incluida persistencia: PASS.
- Role-State Binding y denegaciones por permisos: PASS.
- Importación de snapshot SQLite de solo lectura e integración con contratos del piloto: PASS.

## Comandos y conteos

1. Suite dirigida final, con Tcl/Tk configurado y temporales internos:

   `$env:TCL_LIBRARY='C:\Users\Usuario\AppData\Local\Programs\Python\Python313\tcl\tcl8.6'; $env:TK_LIBRARY='C:\Users\Usuario\AppData\Local\Programs\Python\Python313\tcl\tk8.6'; python -m pytest tests\gestion_central --basetemp=.test-tmp\qa-directed-final -q`

   Resultado: **30 passed** en 9.79 s. Incluye **21** pruebas de dominio/contrato/integración y **9** pruebas de interacción Tk real.

2. Regresión completa final:

   `$env:TCL_LIBRARY='C:\Users\Usuario\AppData\Local\Programs\Python\Python313\tcl\tcl8.6'; $env:TK_LIBRARY='C:\Users\Usuario\AppData\Local\Programs\Python\Python313\tcl\tk8.6'; python -m pytest --basetemp=.test-tmp\qa-regression -q`

   Resultado: **230 passed** en 20.96 s.

3. Compilación:

   `python -m compileall -q bc_gestion_central.py modulos\gestion_central`

   Resultado: **PASS**.

Las primeras corridas restringidas produjeron 21 PASS y 9 errores de setup porque el sandbox impedía a Python cargar `init.tcl`. No fueron fallos de producto. Al repetir con las rutas Tcl/Tk indicadas y permiso de lectura efectivo, las 30 pruebas pasaron. El único warning final fue que pytest no pudo actualizar `.pytest_cache`; `--basetemp` permaneció dentro del worktree y todas las pruebas terminaron correctamente.

## Interacción UI y evidencia visual

- Las 9 pruebas Tk validan apertura desde tarjetas, navegación y regreso, filtros y feedback visible, selección y persistencia de alertas, mensajes seguros, revisión individual y masiva, persistencia tras reinicio, teclado, cancelación y errores.
- `screenshots/supervision-1920x1080.png` mide realmente **1920 × 1080**, modo RGB.
- Inspección visual: PASS. Cabecera, identificación inequívoca de piloto sintético, KPIs, movimientos, sincronización/integridad, controles de revisión, alertas y mensajería son legibles y permanecen visibles sin scroll primario a 1920×1080.
- Adaptación menor: PASS por contratos automatizados de geometría mínima y layout responsivo incluidos en la suite.

## Conclusión

No hay defectos bloqueantes ni regresiones observadas. La candidata queda aprobada para el gate Auditor.

No se modificó código. Solo se creó este reporte y datos temporales de prueba dentro del worktree. No se modificó ninguna ruta `C:\PX\GDR-*`, BC-Core ni BC-Finanzas.
