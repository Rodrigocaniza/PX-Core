# IMPLEMENTATION_PACKET — BC-CAJA-APERTURA-CAJA-001

Slice aislado sobre la línea canónica real. **Baseline: `origin/main` `098a9fb` = BC Caja
1.0.0-rc.14** (200 pruebas + 4 subpruebas verdes, verificado antes de tocar nada).

No reconstruye BC Caja. Toca sólo la apertura del día.

## Contrato funcional

1. **Fecha automática.** La caja se abre siempre con la fecha de hoy. El campo `Fecha` de
   la cabecera deja de ser tipeable.
2. **Hora automática.** La hora de apertura la pone el sistema (`CashDay.opened_at`, ya
   existente y persistido) y se muestra junto al estado. Nunca se pide.
3. **No se puede elegir fecha/hora para abrir.** No hay selector en el flujo de apertura.
   Intentar abrir estando en otro día devuelve primero a hoy.
4. **`Consultar otro día`.** Único acceso al histórico. Abre un calendario, carga el día
   elegido **en sólo lectura** y muestra `Volver a hoy`. Si ese día no tiene caja
   registrada, avisa y no abre nada.
5. **`Caja inicial` destacada.** Etiqueta en negrita con color de acento y campo con borde
   azul. Sigue siendo no tipeable (lo calcula el arqueo previo / carry-forward).

## Invariantes (no negociables)

- **I1.** Sólo la caja de **hoy** es operable. En modo consulta, toda la operación
  (movimientos, salidas, guardar, cerrar caja) queda deshabilitada, incluso si ese día
  quedó en estado `OPEN`.
- **I2.** **Reglas económicas intactas.** No se toca `opening_cash`, `suggested_opening_cash`,
  `OpeningCashSuggestion`, carry-forward, arqueo de apertura ni de cierre.
- **I3.** **Sin cambios de esquema.** 15 migraciones, la última `015_admin_counts_notifications.sql`.
- **I4.** **No se toca el DatePicker global** (`abrir_selector_fecha_entrega` queda igual).
  El calendario de consulta es propio de este slice.
- **I5.** **No se toca FactuFácil.**
- **I6.** `campos_manual["fecha"]` sigue siendo la fuente de verdad que leen todas las
  llamadas existentes a `load_day`; sólo cambia quién lo escribe (el sistema, no el teclado).

## Archivos en alcance

| Archivo | Cambio |
| --- | --- |
| `CajaDiaria.py` | Cabecera, apertura, consulta de otro día, estado con hora |
| `tests/caja_diaria/test_rc15_apertura_caja.py` | Nuevo — contrato del slice |
| `tools/capture_caja_rc15_apertura.py` | Nuevo — evidencia visual automatizada |

Fuera de alcance: dominio, servicios, repositorio, migraciones, Pedidos, Arqueo, Admin,
correo, Gestión Central.

## Tests

Focalizados: `test_rc15_apertura_caja.py`, `test_rc12_cash_count_modal.py`,
`test_rc13_admin_counts_email.py`, `test_session_hours.py`, `test_ui_smoke.py`.
Regresión al cierre: `tests/caja_diaria` completo.

## Definition of Done

- [ ] Focalizados en verde.
- [ ] `tests/caja_diaria` completo en verde, sin perder ninguna de las 200 de baseline.
- [ ] Evidencia visual automatizada 1920×1080 y 1366×768 generada y hasheada.
- [ ] MANIFEST + SUMMARY + ARTIFACT_CONSISTENCY + WORKFLOW.
- [ ] Commit protegido en rama propia y push. `main` intacto.
- [ ] NEXT_ACTION persistido. Instalación en la Óptica: sólo tras HUMAN_GATE.
