# Veredicto — HUMAN_GATE-PEDIDOS-002

**PASS.** Registrado el 2026-08-17 a partir de la observación humana real.

Gate nuevo. `HUMAN_GATE-RC12-PEDIDOS-001` sigue anulado: **nada de aquel gate se usó como
PASS**.

## Cómo se ejecutó

Command Center abrió BC Caja sobre una base temporal propia (los datos de la Óptica no se
tocaron), directamente en la pestaña Pedidos, con 3 atrasados, 2 entregas de hoy, 1 próxima
y dos novedades ya auditadas.

Sesión consolidada junto con `HUMAN_GATE-APERTURA-CAJA-001`: una sola intervención humana,
dos veredictos.

## Alcance del PASS

Los 11 puntos del gate, incluida la regresión a 1366×768:

1. Entrada útil: la grilla ya tiene contenido, nunca una hoja vacía.
2. La línea de resumen dice por dónde empezar y se lee sin esfuerzo.
3. `ATRASADOS` y `PARA HOY` se distinguen de las filas de pedidos.
4. Sólo 3 filtros y 3 acciones; el color aparece únicamente donde significa algo.
5. Teléfono y `Última novedad` se leen completos.
6. `Corregir estado` con lista cerrada: no se puede escribir un estado a mano, y sin
   observación no guarda nada.
7. Retroceso auditado visible en `Última novedad` con su motivo.
8. `⚠ Trabajos N` cuenta y abre exactamente el mismo conjunto.
9. Doble clic en el teléfono abre WhatsApp.
10. **Punto propio del port:** `Arqueo`, `Administrador` y el cierre con correo de rc.14
    siguen funcionando.
11. Las 8 columnas entran sin scroll horizontal a 1366×768.

## Lo que este PASS no cubre

- Laboratorio en la grilla: fuera de alcance, requiere join contra `sale_items`.
- Reglas económicas: no se tocaron.

Habilita la integración. **No habilita instalación por sí solo**: la instalación es de la
RC combinada.
