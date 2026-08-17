# BC-CAJA-APERTURA-CAJA-001 — Apertura de Caja automática

Slice aislado sobre la línea canónica real: **`origin/main` `098a9fb` = BC Caja 1.0.0-rc.14**.

## Qué cambia

| Antes (rc.14) | Ahora |
| --- | --- |
| `Fecha` era un campo tipeable con hoy precargado | La pone el sistema y no se puede tipear |
| `ABRIR / CONSULTAR`: el mismo botón abría o miraba cualquier fecha | `ABRIR CAJA DE HOY` abre siempre hoy; si estabas en otro día, vuelve a hoy antes de abrir |
| Para ver otro día se escribía la fecha encima | `Consultar otro día` abre un calendario y carga ese día **en sólo lectura** |
| Un día pasado en estado `OPEN` seguía siendo operable | Sólo la caja de hoy es operable |
| `Estado: ABIERTO` | `Estado: ABIERTO · 08:32` — la hora la puso el sistema |
| `Caja inicial` con el mismo peso visual que el resto | Etiqueta azul en negrita y campo con borde azul |

En modo consulta aparece el chip `SÓLO LECTURA` y `Volver a hoy`; `ABRIR CAJA DE HOY` y
`Consultar otro día` se retiran mientras dura.

## Cómo se cumple "hora automática"

`CashDay.opened_at` ya existía, se llena solo (`utc_now`) y se persiste en SQLite. Este
slice no agrega un campo de hora: lo **muestra**. Nunca se pide.

## Invariantes verificados

- **Reglas económicas intactas.** Ni `opening_cash`, ni la sugerencia por arqueo previo,
  ni el carry-forward, ni el arqueo de apertura/cierre cambiaron.
- **Sin cambios de esquema.** 15 migraciones, última `015_admin_counts_notifications.sql`.
- **DatePicker global sin tocar.** `abrir_selector_fecha_entrega` queda igual; el
  calendario de consulta es propio de este slice.
- **FactuFácil sin tocar.**

## Validación

**Automática:** 210 pruebas + 4 subpruebas (200 de baseline + 10 nuevas). Suite completa
`tests/caja_diaria` en verde.

**Visual automatizada:** `tools/capture_caja_rc15_apertura.py` levanta la UI real, siembra
la caja de hoy y una de ayer, y **falla si el contrato no se cumple** antes de capturar:

1. la fecha no se puede tipear (se le manda una tecla y no cambia);
2. no sobrevive el botón ambiguo `ABRIR / CONSULTAR`;
3. tras abrir, el estado coincide con `Estado: ABIERTO · HH:MM`;
4. consultar otro día muestra `SÓLO LECTURA`, cambia la fecha de la cabecera y deja
   `Cerrar caja`, `Guardar venta` y `Guardar salida` deshabilitados;
5. `ABRIR CAJA DE HOY` no está disponible mientras se consulta;
6. regresión responsive: el bloque `Cerrar caja` / `Arqueo` no queda fuera de la ventana.

Cuatro capturas verificadas: apertura y consulta, a 1920×1080 y 1366×768.

**Humana:** pendiente. Ver `HUMAN_GATE.md`. No se inventó ningún PASS.

## Ajuste de contrato previo

`test_rc4_visual_clean_contract.py::test_rc4_never_displays_open_status_in_english` fijaba
el literal `text="Estado: ABIERTO"`. Como ahora el texto lleva la hora concatenada, la
aserción pasa a exigir `"Estado: ABIERTO"` y `"Estado: CERRADO"` y a prohibir
`"Estado: OPEN"`. La intención original (nunca mostrar el estado en inglés) queda intacta.

## Deuda observada, fuera de alcance

A **1366×768 el bloque de KPIs de la cabecera queda tapado por los botones de estado**.
Se verificó con captura A/B contra `origin/main`: **ya pasaba en rc.14**, no lo introdujo
este slice. Merece su propio slice de cabecera responsive.
