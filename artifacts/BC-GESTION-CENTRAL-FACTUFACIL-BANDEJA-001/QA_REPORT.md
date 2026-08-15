# QA Report

**Misión:** `BC-GESTION-CENTRAL-FACTUFACIL-BANDEJA-001`
**Verdict:** **PASS**

## Alcance y resultados

- Dominio FactuFácil dirigido: **8/8 PASS**.
- Suite dirigida completa solicitada: **8 PASS + 2 ERROR de entorno Tk**; los dos errores ocurren en el fixture `tk.Tk()` antes de ejecutar código de producto porque el Python 3.13 disponible no puede cargar un `init.tcl` utilizable.
- Se repitió Tk con `TCL_LIBRARY` y `TK_LIBRARY`, primero desde la instalación del intérprete y luego con copias efímeras aisladas. El mismo error de inicialización persistió; no se observó un fallo funcional de FactuFácil.
- Regresión no-Tk independiente: **238/238 PASS** en 11.19 s.
- Regresión completa: **238 PASS + 13 ERROR de entorno Tk**. Todos los errores son el mismo fallo de fixture previo a las pruebas; abarca las suites visuales heredadas además de FactuFácil.
- Evidencia previa reproducible registrada por implementación: FactuFácil Tk **2/2 PASS** y regresión **251/251 PASS**.
- `compileall`: **PASS**.
- `git diff --check`: **PASS** (sólo advertencias informativas LF/CRLF).

## Comandos QA

```powershell
python -m pytest tests/gestion_central/test_factufacil.py tests/gestion_central/test_factufacil_ui_interactions.py -q --basetemp .test-tmp/qa-directed
$env:TCL_LIBRARY='.../tcl8.6'; $env:TK_LIBRARY='.../tk8.6'; python -m pytest tests/gestion_central/test_factufacil.py tests/gestion_central/test_factufacil_ui_interactions.py -q --basetemp .test-tmp/qa-directed-tcl
python -m pytest -q --basetemp .test-tmp/qa-regression
python -m pytest -q --ignore=tests/gestion_central/test_delivery_ui_interactions.py --ignore=tests/gestion_central/test_factufacil_ui_interactions.py --ignore=tests/gestion_central/test_review_ui_interactions.py --ignore=tests/gestion_central/test_ui_interactions.py --basetemp .test-tmp/qa-regression-headless
python -m compileall -q modulos/gestion_central bc_gestion_central.py tools/capture_gestion_central_factufacil.py
git diff --check
```

## Inspección visual

- Archivo: `screenshots/factufacil-1920x1080.png`.
- Metadatos verificados: **1920×1080**, `Format24bppRgb`.
- SHA-256: `3125c4b359654a057f278170cb9043482510f17df3cc0ea504f6cb6f7ad158a2`.
- Inspección humana: **PASS**. Se ven encabezado y señalización de piloto, filtros, KPIs por estado, grilla, detalle completo, copias individuales/global, historial y controles de transición. No se aprecia recorte material a 1920×1080; existe scroll vertical explícito en el detalle.

## Dictamen

La vertical cumple QA: dominio, regresión headless, compilación, consistencia del diff y evidencia visual pasan. La imposibilidad de repetir Tk en esta sesión queda clasificada como limitación del intérprete/sandbox, no como defecto del producto, porque ocurre al crear la raíz Tk y la evidencia de ejecución 2/2 y la captura final son concordantes.
