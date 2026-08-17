# Veredicto — HUMAN_GATE-APERTURA-CAJA-001

**PASS.** Registrado el 2026-08-17 a partir de la observación humana real.

## Cómo se ejecutó

Command Center abrió BC Caja sobre una base temporal propia (los datos de la Óptica no se
tocaron), con la caja de **ayer** sembrada con tres ventas y la de **hoy sin abrir**, para
que la apertura ocurriera a la vista.

Sesión consolidada junto con `HUMAN_GATE-PEDIDOS-002`: una sola intervención humana, dos
veredictos.

## Alcance del PASS

Los 9 puntos del gate, incluida la regresión a 1366×768:

1. La fecha es la de hoy y no se puede cambiar tipeando.
2. `ABRIR CAJA DE HOY` abre el día sin pedir fecha ni hora (el arqueo de apertura de rc.14
   se conserva tal cual).
3. El estado muestra la hora real de apertura.
4. `Caja inicial` se distingue del resto de la cabecera.
5. `Consultar otro día` carga el día elegido y avisa `SÓLO LECTURA`.
6. En modo consulta no se puede guardar venta, registrar salida ni cerrar caja.
7. `Volver a hoy` devuelve la operación normal.
8. Un día sin caja registrada avisa y no crea nada.
9. Los botones de la derecha entran completos a 1366×768.

## Lo que este PASS no cubre

- Reglas económicas: no se tocaron en el slice.
- KPIs tapados a 1366×768: deuda anterior a rc.14, fuera de alcance.

Habilita la integración. **No habilita instalación por sí solo**: la instalación es de la
RC combinada.
