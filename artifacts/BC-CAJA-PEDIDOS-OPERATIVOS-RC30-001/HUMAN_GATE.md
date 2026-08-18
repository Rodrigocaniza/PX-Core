# HUMAN_GATE-PEDIDOS-RC30-001

> **Estado al 18-08-2026: gate cerrado, PASS 11/11, y rc.31 instalada y validada en
> la PC de la Optica.** Lo que sigue es el checklist tal como se escribio ANTES de
> empaquetar, y por eso habla en presente de cosas que ya ocurrieron. El veredicto vive
> en `GATE_VERDICT.md` y la evidencia de instalacion en `INSTALL_EVIDENCE.md`.

**Nada se empaquetó ni se instaló.** La Óptica sigue con rc.30 y `main` sigue en `291fe40`.
Este gate mira la pantalla nueva de Pedidos; si pasa, recién ahí se arma la RC.

Todo lo automatizable ya está PASS: 682 pruebas y un smoke que falla solo si el contrato se
rompe.

## Cómo levantarlo

Desde el worktree `pedidos30`:

```
python tools/capture_caja_pedidos_rc30.py salida.png 1920x1080
```

O abrir BC Caja e ir a **Pedidos** con los datos reales.

## Puntos a marcar PASS / FAIL

1. **Entrada útil.** Al abrir, Pedidos ya tiene contenido: `ATRASADOS` y `PARA HOY`. Si no
   hay nada urgente, aparece `PRÓXIMOS` — nunca una hoja en blanco.
2. **Qué pidió el cliente.** Cada fila dice cliente, sobre y **trabajo** (armazón,
   cristales, lo que sea) sin abrir otra ventana.
3. **Prometido y atraso.** La fecha prometida y cuánto se pasó (`6 días`, `hoy`). Un pedido
   entregado no muestra atraso.
4. **Laboratorio a mano.** La fila muestra el laboratorio **con su teléfono**; no hay que ir
   al ABM a buscarlo.
5. **Contactar.** Con un pedido marcado, `Contactar` abre WhatsApp del laboratorio; si el
   laboratorio no tiene número, usa el del cliente.
6. **Última novedad.** Se lee de un vistazo y no llena la grilla.
7. **Tres acciones.** `Acción siguiente`, `Contactar` y `Más ▾`. Nada más compite.
8. **Contraste.** Sin nada marcado las acciones se ven **gris apagado**; al marcar un
   pedido `PENDIENTE`, `Marcar listo` pasa a verde sólido. Al pasar el mouse por una gris
   aparece el motivo. **¿Se distingue de un vistazo?**
9. **Corregir estado.** En `Más ▾`: lista desplegable cerrada —**no se puede escribir un
   estado a mano**— y sin observación no guarda nada.
10. **Nada se rompió.** La alerta `⚠ Trabajos N` sigue abriendo exactamente sus pedidos,
    `Ver todos` saca el filtro, y `Seguimiento`, `Arqueo`, `Administrador` e `Historial`
    siguen como estaban.
11. **1366×768.** Repetir 1, 2, 4 y 8: las 8 columnas entran sin scroll horizontal.

## Si pasa

Se arma la RC (rc.31) con backup y rollback, instalación transaccional y, después de
validarla, promoción a `main`.

## Si algo falla

Anotar el número. No hay nada que revertir: no se instaló nada.
