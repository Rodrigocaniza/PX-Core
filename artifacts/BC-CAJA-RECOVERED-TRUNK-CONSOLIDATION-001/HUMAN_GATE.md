# HUMAN_GATE-RC30-CONSOLIDACION-001

**rc.30 está empaquetada, no instalada.** La Óptica sigue con rc.15 y `main` sigue en
`65d2df4`. Este gate se corre **sin instalar y sin migrar la base real**: el binario nuevo
se abre contra una **copia** de la base productiva.

Todo lo automatizable ya está PASS: 639 pruebas, 7 capturas, paquete construido y binario
probado.

## Antes de empezar

- Se va a abrir `BC Caja 1.0.0-rc.30` contra una **copia** de
  `%LOCALAPPDATA%\BC\Caja\bc_caja.sqlite3`. Sobre la copia se aplican las migraciones
  **016–021**; **la base real no se toca**.
- Va a pedir crear el **Administrador**: la copia no tiene uno.
- El **correo está sin configurar**, así que cerrar la caja no envía nada.
- Ojo con lo que se ve al abrir: los pedidos reales de la Óptica están **todos vencidos**
  (las entregas eran del 12 y 13 de agosto), así que la alerta va a mostrar varios
  atrasados. Es correcto: son datos viejos, no un error del programa.

## Puntos a marcar PASS / FAIL

**Apertura**
1. El pie dice `BC Caja 1.0.0-rc.30`.
2. La fecha es la de hoy y **no se puede tipear**; `ABRIR CAJA DE HOY` abre sin preguntar
   fecha ni hora (pide el arqueo de apertura, que es lo canónico).
3. El estado muestra `ABIERTO` con la hora real; `Caja inicial` se distingue.
4. `Consultar otro día` carga un día viejo en **sólo lectura** y no deja guardar nada.

**Pedidos**
5. Abre en `Requieren atención`, el estado se ve **dentro de la fila** (no como etiqueta
   flotante) y la alerta de la cabecera abre exactamente esos pedidos.

**Seguimiento Pilar** — el corazón de esta consolidación
6. La pestaña `Seguimiento` muestra el circuito con sus grupos y contadores.
7. `Acción siguiente` propone **la acción correcta** para lo que está marcado, y cambia de
   nombre según el estado.
8. Recepción con discrepancias: `No llegó` y `No estaba en lista` se registran y quedan
   visibles en la conciliación (`Declarados · Recibidos · No llegó · Extra`).
9. `Más ▾` ofrece `Queda a confirmar`, `Corregir estado` y `Cerrar por excepción`, y
   `Corregir estado` **no deja escribir un estado a mano** y exige motivo.
10. Un trabajo atrasado **no traba** el circuito: sigue ofreciendo su próxima acción.

**Laboratorios y sucursal**
11. `Laboratorios` permite ver/administrar; el filtro por laboratorio responde.
12. La sucursal sale de la caja instalada y `Ver todas las sucursales` funciona.

**Acciones y contraste — lo que se agregó en esta consolidación**
13. Sin nada marcado, `Acción siguiente` y `Novedad` se ven **gris apagado**; al marcar un
    trabajo pasan a color sólido. Pasando el mouse por una gris, aparece el motivo.
    **¿Se distingue de un vistazo lo que se puede hacer?**

**No regresión**
14. `Arqueo` abre; `Administrador` responde; `Historial` muestra las jornadas agrupadas;
    cerrar la caja pide arqueo y **no intenta enviar correo**.

**Responsive**
15. Repetir 5, 6 y 13 en 1366×768.

## Si pasa

Command Center genera la RC definitiva: backup previo de la base real, rollback verificado
desde rc.15, instalación transaccional y, recién después, promoción de esta línea a `main`
por flujo protegido.

## Si algo falla

Anotar el número. No hay nada que revertir: no se instaló ni se migró la base real.
