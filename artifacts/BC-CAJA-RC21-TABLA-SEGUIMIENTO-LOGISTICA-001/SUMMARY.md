# BC Caja RC21 — Tabla de Seguimiento orientada al circuito

Base canónica: `8b11c78c18e3f4f1e7d350cd1f188f0790b3e0ca`
(integración RC18–RC20, instalada como `1.0.0-rc.20`).

## La tabla

Cinco columnas: `Sobre · Cliente · Tipo de trabajo · Laboratorio · Estado`.

- **Vendedora sale de la vista.** Solo deja de mostrarse acá: el campo
  `saleswoman` sigue en el dominio, en la grilla de movimientos y en la de
  pedidos. Ventas y comisiones no se tocan.
- **Tipo de trabajo** sale de la observación del pedido de origen, que el alta
  de lote ya copiaba. No se agrega ningún dato nuevo.
- **Laboratorio** va inmediatamente después de Tipo, y muestra `SIN ASIGNAR`
  mientras el trabajo no salió a ninguno.
- **Estado** es la columna que se expande, dimensionada al caso más largo.

## Diferenciación visual

Cada etapa se dibuja como chip compacto con color propio, no coloreando la
fila. El único rastro a nivel de fila es un fondo rosado muy tenue en los
atrasados, para que la excepción salte sin gritar.

`ATRASADO` usa rojo y tiene prioridad visual. `CONFIRMADO PARA MAÑANA` usa
violeta y es claramente visible. **Ninguna de las dos reemplaza la etapa
física**: se anteponen como segundo chip.

```
[ATRASADO] [EN LABORATORIO]
[CONFIRMADO PARA MAÑANA] [EN LABORATORIO]
[RECIBIDO EN PILAR]
```

Treeview no admite widgets por celda, así que se reutiliza el mecanismo de
chips ya probado en Pedidos. El contenedor del chip es opaco y cubre la celda
entera: transparente, el texto del Treeview asomaba al costado.

## Estados

Los seis del circuito, con rótulo legible en castellano. `CERRADO` queda fuera
de `ESTADOS_VISIBLES`: **`RECIBIDO EN PILAR` completa el circuito** y ningún
trabajo se muestra como cerrado antes de ese punto.

## Modelo RC19 intacto

`ATRASADO` y `CONFIRMADO PARA MAÑANA` siguen siendo condiciones derivadas, no
estados persistidos. No se agregó cron ni reescritura de filas: la tabla
calcula la condición al pintar. Hay una prueba que verifica que la base nunca
almacena esos valores.

## Contacto del laboratorio

Sigue accesible: la fila expone `phone_line` y `whatsapp`, y la franja inferior
agrupa los atrasados por laboratorio con línea y WhatsApp. Salieron de la
grilla como columnas para dejar lugar a las cinco pedidas, no del modelo.

## Captura segura, unificada

La sonda de RC19 recortaba `(0,0,ancho,alto)` de pantalla, y a 1366×768 —donde
la ventana no cubre el monitor— dejaba entrar una franja de otra aplicación.
Se detectó al revisar la evidencia y se aplicó la regla fail-closed.

Las tres sondas pasan a usar `tools/gui_capture.py`, que dibuja la ventana con
`PrintWindow` en un contexto en memoria en vez de leer la pantalla: por
construcción no puede capturar otra aplicación, ni con la ventana tapada o en
segundo plano. Ya no queda ningún `ImageGrab` en las sondas.

## Verificación

- Regresión canónica: **370 PASS, 0 FAIL** (la integración dejó 339).
- Smoke GUI real de la tabla en 1920×1080 y 1366×768.
- RC18 y RC20 verificados sin regresión.
- Las cinco columnas entran sin scroll horizontal en ambos perfiles.

## Pendiente

Este cambio **no es visible en la instalación productiva**, que sigue en
`1.0.0-rc.20`. Requiere una nueva build e instalación, consolidada en el gate
final junto con la comprobación manual pendiente de RC20.
