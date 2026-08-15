# Evidencia de pruebas

- Dominio de comisiones: **25/25 PASS**.
- Interacción Tk y Full HD: **4/4 PASS**.
- Regresión completa: **280/280 PASS** en 33.08 s.
- Línea base heredada: 251 pruebas; esta misión suma 29 sin romper ninguna existente.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Escaneo heurístico de secretos: PASS; las únicas coincidencias están dentro del propio test de prohibición.
- Captura 1920×1080: PASS.

## FAIL preservados y corregidos

1. **Explicación del convenio desaparecía tras el cálculo.**
   `test_agreement_deducts_exactly_five_percent_and_creates_no_client_balance` falló porque, al pasar
   a `CALCULADA`, el motivo mostrado dejaba de mencionar el convenio. La misión exige mostrar
   siempre por qué una venta recibió el descuento. Corregido: `breakdown()` antepone el motivo del
   convenio en todos sus estados. Prueba repetida: PASS.

2. **KPI «Cobros parciales» sin formato monetario.**
   La primera captura mostró `700000` en crudo. `partial_payments_amount` faltaba en `AMOUNT_KEYS`.
   Corregido y fijado por aserción en `test_full_hd_layout_keeps_every_control_visible`.

3. **Tabla principal recortada a 1920×1080.**
   La primera captura cortaba «Base comisionable» y ocultaba por completo la columna «Comisión»;
   el resumen por vendedora también se cortaba. Causa: el panel izquierdo tenía `minsize=980`
   frente a 1470 px de columnas. Corregido recalibrando anchos y paneles, y fijado con una guarda
   de regresión que compara la suma de anchos de columna contra el ancho visible de cada tabla.
   Evidencia visual regenerada tras la corrección.

## Reproducción

```
python -m pytest -q
python -m compileall -q modulos tools tests bc_gestion_central.py
git diff --check
python tools/capture_gestion_central_comisiones.py artifacts/BC-GESTION-CENTRAL-COMISIONES-001/screenshots/comisiones-1920x1080.png
```
