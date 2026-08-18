# HUMAN_GATE-PEDIDOS-RC30-001 — PASS

Generacion 2 del gate. Los 11 puntos aprobados por veredicto humano.

## Sobre que se dio el veredicto

Evidencia visual regenerada tras corregir el harness: `pedidos-operativos-1920x1080.png`
y `pedidos-operativos-1366x768.png`, con `Pedidos` efectivamente resaltado en la barra de
navegacion.

La generacion 1 quedo observada en el punto 10: la grilla mostraba Pedidos pero la barra
resaltaba `Caja diaria`. Se determino por codigo que era defecto del harness y no del
producto —la app oculta el segmented button del CTkTabview (`CajaDiaria.py:1017`) y toda
navegacion real pasa por `seleccionar_pestana()`, que mueve las dos mitades— y se corrigio
solo el harness, con control negativo que demuestra que ahora falla cerrado.

## Condiciones de la ejecucion

Fixtures sinteticas, 0 correos, 0 cierres, sin base de datos productiva y sin instalar
nada. La via de captura es la que el propio `HUMAN_GATE.md` ofrece, asi que el estandar no
se degrado por ejecutarlo fuera de la Optica.

## Que habilita

Empaquetar `1.0.0-rc.31`. La instalacion y la validacion post-install siguen pendientes:
no pueden hacerse en este equipo, ver `INSTALL_READINESS.md`.
