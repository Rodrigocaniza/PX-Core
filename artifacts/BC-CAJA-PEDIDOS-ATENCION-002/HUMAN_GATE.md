# HUMAN_GATE-PEDIDOS-002

**Estado de la misión:** `AWAITING_HUMAN_GATE`.
**No se empaqueta ni se instala hasta que este gate pase.**

Gate **nuevo**. `HUMAN_GATE-RC12-PEDIDOS-001` quedó anulado: validaba una pantalla
construida sobre rc.11. Nada de aquel gate se hereda como PASS.

Todo lo automatizable ya está PASS: 243 pruebas y tres capturas que fallan solas si el
contrato se rompe.

## Cómo levantar la pantalla

Desde el worktree `pedidos002`:

```
python tools/capture_caja_pedidos_atencion.py salida.png --width 1920 --height 1080
python tools/capture_caja_pedidos_atencion.py dialogo.png --width 1920 --height 1080 --dialogo
```

O abrir BC Caja con los datos reales de la Óptica e ir a **Pedidos**.

## Qué hay que observar — ViewSonic 24" (1920×1080)

Marcar cada punto PASS / FAIL. Un solo FAIL frena el empaquetado.

1. **Entrada útil.** Al entrar a Pedidos la grilla ya tiene contenido. Si no hay atrasados
   ni entregas de hoy, se ve el grupo `PRÓXIMOS`; nunca una hoja vacía.
2. **Primer golpe de vista.** La línea de resumen dice por dónde empezar y se lee sin
   esfuerzo desde la posición normal de trabajo.
3. **Agrupación.** `▸ ATRASADOS · n` y `▸ PARA HOY · n` se distinguen de las filas. Los
   atrasados se reconocen como atrasados sin leer la fecha.
4. **Ruido visual.** Sólo 3 filtros y 3 acciones. El color aparece únicamente en estado
   (chip), atrasados y filtro activo.
5. **Contexto suficiente.** Teléfono y `Última novedad` se leen completos, sin cortes.
6. **Corregir estado.** Con un pedido seleccionado, el diálogo abre centrado. *Nuevo estado*
   es una lista desplegable cerrada — **verificar que no se puede escribir a mano**.
   Guardar sin observación muestra *"La observación es obligatoria."* y no guarda nada.
7. **Retroceso auditado.** Llevar un pedido a `LISTO`, después a `ENTREGADO`, y volverlo a
   `PENDIENTE` con `Corregir estado`. La corrección aparece en `Última novedad` con el motivo.
8. **Aviso coherente.** En `Caja diaria`, `⚠ Trabajos N` muestra el mismo N que
   `ATRASADOS + PARA HOY`, y al hacer clic abre exactamente ese conjunto.
9. **WhatsApp.** Doble clic sobre el teléfono abre WhatsApp con ese número.
10. **Lo canónico de rc.14 sigue funcionando** — este es el punto propio del port:
    `Arqueo` abre su modal, `Administrador` pide credencial, el cierre con arqueo y el
    correo de cierre siguen operando como antes.

## Regresión responsive — 1366×768

11. Repetir 1 a 5 en 1366×768. Las 8 columnas entran sin scroll horizontal y los grupos
    siguen siendo legibles.

## Qué NO se está validando acá

- Reglas económicas de Caja: no se tocaron.
- Laboratorio en la grilla de Pedidos: fuera de alcance a propósito.
- Apertura de Caja (`BC-CAJA-APERTURA-CAJA-001`): tiene su propio gate, en paralelo.

## Si pasa

Command Center continúa solo: empaqueta, backup previo, artifact-consistency con
`zip_sha256`/`exe_sha256`, safe closure y push protegido.

## Si algo falla

Anotar el número del punto y qué se vio. Vuelve como corrección dentro de este mismo slice.
