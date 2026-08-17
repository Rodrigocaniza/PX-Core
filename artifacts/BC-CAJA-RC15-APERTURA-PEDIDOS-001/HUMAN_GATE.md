# HUMAN_GATE-RC15-INSTALADA-001

**rc.15 ya está instalada** en `%LOCALAPPDATA%\Programs\BC-Caja-Pilot`, sobre los datos
reales de la Óptica. Este es el **único gate** que queda: mirar que la instalación real se
comporte como corresponde.

Todo lo automatizable ya está PASS: preflight, migración validada sobre un clon de la base
real, 258 pruebas, 9 capturas fail-closed y verificación post-install sobre la base
productiva.

## Antes de empezar, dos cosas que vas a ver

1. **Va a pedir crear el Administrador.** rc.13 trae administrador protegido y la base no
   tiene ninguno todavía. Podés crearlo ahora (usuario y contraseña locales) o cerrar el
   diálogo y seguir; la caja funciona igual.
2. **El correo de cierre está sin configurar** (`enabled: false`, sin destinatario). Eso es
   a propósito: **el cierre no va a intentar enviar nada**. Configurarlo es un paso aparte.

## Puntos a marcar PASS / FAIL

1. **Versión.** El pie de la ventana dice `BC Caja 1.0.0-rc.15`.
2. **Apertura.** La fecha es la de hoy y no se puede tipear. `ABRIR CAJA DE HOY` abre el
   día pidiendo el arqueo de apertura, sin preguntar fecha ni hora.
3. **Caja inicial / hora.** `Caja inicial` se distingue en la cabecera y el estado muestra
   `ABIERTO · HH:MM` con la hora real.
4. **Arqueo.** El botón `Arqueo` abre su modal.
5. **Administrador.** El botón `Administrador` responde (pide credencial o su creación).
6. **Pedidos.** Abre en `Requieren atención` con los pedidos reales agrupados; hoy son
   **7 atrasados** y ninguno para hoy.
7. **Contraste de acciones — lo que se corrigió.** Sin ningún pedido seleccionado, las tres
   acciones se ven **gris apagado**. Al seleccionar un pedido `PENDIENTE`, `Marcar listo`
   pasa a **verde sólido** y `Marcar entregado` queda gris. Pasando el mouse por una acción
   gris aparece el motivo. **¿Se distingue de un vistazo lo que se puede hacer?**
8. **Historial.** La pestaña `Historial` muestra los movimientos existentes.
9. **Consultar otro día.** Cargá el 12-08-2026: se ve, dice `SÓLO LECTURA` y no deja
   guardar nada.
10. **Cierre sin correo.** Si cerrás la caja de hoy, pide el arqueo de cierre y **no
    intenta enviar ningún correo**.

## Regresión responsive

11. Repetir 6 y 7 en 1366×768: las 8 columnas entran sin scroll horizontal y el contraste
    de las acciones se mantiene.

## Decisión operativa que queda pendiente

Los días **12/08 y 13/08 quedaron `OPEN`** desde antes. Con rc.15 el histórico es sólo
lectura, así que **ya no se pueden cerrar desde la pantalla**. No afecta la operación de
hoy, pero hay que decidir qué se hace: dejarlos así, o un slice chico que permita cerrar un
día viejo con arqueo auditado.

## Si pasa

Command Center cierra: Artifact Consistency final, Librarian → QA → Auditor, safe closure,
NEXT_ACTION y queda listo el fast-forward de `main` (el push a `main` está bloqueado por
permisos en esta PC y se pide aparte).

## Si algo falla

Anotar el número del punto. El rollback está listo y verificado: `ROLLBACK.md`, con backup
`bc-caja-preinstall-1.0.0-rc.15-20260817-164711-598414.sqlite3` y la instalación anterior
intacta en `BC-Caja-Pilot.previous-rc11`.
