# Veredicto — HUMAN_GATE-RC30-CONSOLIDACION-001

**PASS.** Registrado el 2026-08-17, sobre `BC Caja 1.0.0-rc.30` corriendo contra una
**copia verificada** de la base productiva. Nada productivo se tocó durante el gate.

## Cómo se ejecutó

| Paso | Evidencia |
| --- | --- |
| Nada corriendo, instalada rc.15 | verificado antes de abrir |
| Paquete verificado por hash | `zip 29b45e6b…`, `exe a38262a5…` |
| Copia de la base real | sha256 idéntico al original |
| Original tras la corrida | **mismo sha256 `e5de6f40…`: intacto** |
| Migración sobre la copia | 015 → **021**, `integrity_check` ok, 0 FK |
| Datos en la copia | 2 días, 12 movimientos, 8 pedidos, 10 ítems; montos `(6.400.000 / 2.200.000 / 250.000)` |

La copia migrada por el **binario empaquetado** es a la vez el ensayo de migración
rc.15 → rc.30 exigido antes de instalar.

## Alcance del PASS

Los 15 puntos: apertura automática con fecha y hora del sistema, `Caja inicial` destacada,
`Consultar otro día` en sólo lectura, Pedidos con el estado anclado a la fila y la alerta
que abre sus pedidos, Seguimiento Pilar completo con `Acción siguiente`, recepción con
discrepancias, `Más ▸ Queda a confirmar / Corregir estado / Cerrar por excepción`, un
atrasado que no traba el circuito, ABM de laboratorios, vista por sucursal, contraste de
acciones disponibles vs no disponibles con su motivo, historial por jornada, arqueo,
administrador, cierre sin envío de correo, y la regresión a 1366×768.

## Lo que no cubre

- Los pedidos reales están todos vencidos (entregas del 12 y 13 de agosto): es dato viejo.
- Correo sin configurar: el envío real sigue sin ejercitarse.
- Los días 12/08 y 13/08 siguen `OPEN` y el histórico es sólo lectura.

Habilitó la instalación transaccional y, tras validarla, la promoción a `main`.
