# HUMAN_GATE-RC12-PEDIDOS-001

**Estado de la misión:** `AWAITING_HUMAN_GATE`.
**No se empaqueta ni se instala rc.12 hasta que este gate pase.**

Es el único gate humano del slice. Todo lo automatizable ya está PASS.

## Cómo levantar la pantalla para observar

Desde el worktree `rc12`:

```
python tools/capture_caja_rc12_pedidos.py salida.png --width 1920 --height 1080
```

O, para verlo con los datos reales de la Óptica, abrir BC Caja e ir a **Pedidos**.

## Qué hay que observar — ViewSonic 24" (1920×1080)

Marcar cada punto PASS / FAIL. Un solo FAIL frena el empaquetado.

1. **Entrada útil.** Al entrar a Pedidos la grilla ya tiene contenido. No aparece una
   hoja vacía en ningún caso: si no hay atrasados ni entregas de hoy, se ve el grupo
   `PRÓXIMOS`.
2. **Primer golpe de vista.** La línea de resumen dice por dónde empezar
   (ej. *"3 atrasado(s) y 2 para hoy. Empezá por los atrasados."*) y se lee sin esfuerzo
   desde la posición normal de trabajo de la chica.
3. **Agrupación.** `▸ ATRASADOS · n` y `▸ PARA HOY · n` se distinguen de las filas de
   pedidos. Los atrasados se reconocen como atrasados sin tener que leer la fecha.
4. **Ruido visual.** Sólo hay 3 filtros y 3 acciones. Nada más compite por la atención.
   El color aparece únicamente en: estado (chip), atrasados y el filtro activo.
5. **Contexto suficiente.** Teléfono y `Última novedad` se leen completos, sin cortes ni
   scroll horizontal. Confirmar que la última novedad dice algo útil
   (fecha · estado · responsable · motivo).
6. **Corregir estado.** Con un pedido seleccionado, `Corregir estado` abre el diálogo
   centrado. El campo *Nuevo estado* es una lista desplegable cerrada — **verificar que
   no se puede escribir un estado a mano**. Guardar sin observación debe mostrar
   *"La observación es obligatoria."* y no guardar nada.
7. **Retroceso auditado.** Llevar un pedido a `LISTO`, después a `ENTREGADO`, y volverlo
   a `PENDIENTE` con `Corregir estado`. La corrección debe aparecer en `Última novedad`
   con el motivo escrito.
8. **Aviso coherente.** En `Caja diaria`, el botón `⚠ Trabajos N` muestra el mismo N que
   la suma de `ATRASADOS + PARA HOY`, y al hacer clic abre exactamente ese conjunto.
9. **WhatsApp.** Doble clic sobre el teléfono de un pedido abre WhatsApp con ese número.

## Regresión responsive — 1366×768

10. Repetir los puntos 1 a 5 en 1366×768. Las 8 columnas deben entrar sin scroll
    horizontal y los grupos deben seguir siendo legibles.

## Qué NO se está validando acá

- Reglas económicas de Caja: no se tocaron en este slice.
- Laboratorio en la grilla de Pedidos: quedó fuera a propósito.
- Apertura de Caja, DatePicker compartido y FactuFácil: son los slices siguientes.

## Si pasa

Command Center continúa solo: empaqueta rc.12, hace backup previo, cierra
artifact-consistency con `zip_sha256`/`exe_sha256`, safe closure y push protegido.

## Si algo falla

Anotar el número del punto y qué se vio. Vuelve como corrección dentro de este mismo
slice, sin abrir el siguiente.
