# HUMAN_GATE-APERTURA-CAJA-001

**Estado de la misión:** `AWAITING_HUMAN_GATE`.
**No se empaqueta ni se instala hasta que este gate pase.**

Es el único gate humano del slice. Todo lo automatizable ya está PASS: 210 pruebas y
cuatro capturas que fallan solas si el contrato se rompe.

## Qué queda para el ojo humano (y por qué no lo puede hacer la máquina)

Lo automatizado verifica que los controles existen, que la fecha no se tipea, que la hora
aparece y que en consulta todo queda deshabilitado. Lo que no puede verificar:

1. **Legibilidad real** en el ViewSonic 24", desde la posición de trabajo de la chica:
   ¿se lee `Estado: ABIERTO · HH:MM` de un vistazo? ¿`Caja inicial` destaca lo suficiente?
2. **Que el flujo real coincida con la costumbre.** Abrir la caja a primera hora, con la
   plata contada, sin tocar la fecha: ¿sobra o falta algún paso?
3. **Que `Consultar otro día` alcance** para lo que hoy se resuelve escribiendo la fecha
   a mano (revisar el cierre de ayer, buscar una venta vieja).

## Cómo levantarlo

Desde el worktree `apertura001`:

```
python tools/capture_caja_rc15_apertura.py salida.png --width 1920 --height 1080
python tools/capture_caja_rc15_apertura.py consulta.png --width 1920 --height 1080 --consulta
```

O abrir BC Caja con los datos reales de la Óptica y quedarse en `Caja diaria`.

## Puntos a marcar PASS / FAIL

1. Al entrar, la fecha es la de hoy y **no se puede cambiar tipeando**.
2. `ABRIR CAJA DE HOY` abre la caja del día sin preguntar fecha ni hora.
3. Después de abrir, el estado muestra la hora real de apertura.
4. `Caja inicial` se distingue del resto de la cabecera sin esfuerzo.
5. `Consultar otro día` abre el calendario, carga el día elegido y avisa `SÓLO LECTURA`.
6. En modo consulta **no se puede** guardar una venta, registrar una salida ni cerrar caja.
7. `Volver a hoy` devuelve la operación normal.
8. Un día sin caja registrada avisa y no crea nada.
9. Repetir 1 a 7 en 1366×768: los botones de la derecha entran completos.

## Qué NO se está validando acá

- Reglas económicas de Caja: no se tocaron.
- Arqueo, administrador, correo de cierre: fuera de alcance.
- DatePicker compartido en español y FactuFácil: siguen en la cola.
- KPIs tapados a 1366×768: deuda anterior a este slice, ver `SUMMARY.md`.

## Si pasa

Command Center sigue solo: empaqueta, hace backup previo, cierra artifact-consistency con
`zip_sha256`/`exe_sha256`, safe closure y push protegido.

## Si algo falla

Anotar el número del punto y qué se vio. Vuelve como corrección dentro de este mismo
slice.
