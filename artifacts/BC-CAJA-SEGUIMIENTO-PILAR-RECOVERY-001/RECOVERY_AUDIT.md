# RECOVERY_AUDIT — BC-CAJA-SEGUIMIENTO-PILAR-RECOVERY-001

Búsqueda y evaluación de la implementación existente de Seguimiento / Envíos Pilar.
**No se reprogramó nada.** El código estaba completo, en `origin`.

## 1. Estado canónico verificado

| Ítem | Valor real |
| --- | --- |
| Repo | PX-Core |
| `origin/main` | `65d2df4` — BC Caja **1.0.0-rc.15** (Apertura + Pedidos) |
| Instalada en esta PC | **BC Caja 1.0.0-rc.15**, base con 15 migraciones |
| `main == instalada` | sí |
| Leases activos | ninguno para Caja |

Baseline esperada confirmada. **Pero la baseline no es el estado más avanzado del producto.**

## 2. Dónde estaba Seguimiento

En `origin`, en una **línea completa de 38 commits colgada de rc.14 (`42b8df2`) que nunca
llegó a `main`**:

```
feature/bc-caja-rc15-ux-operativa-001        88e86cb   +2   14/08 23:54
feature/bc-caja-rc16-control-sobres-pdf-001  138d4cb   +4   15/08 10:14
feature/bc-caja-rc17-planilla-continua-pdf   0934471   +6   15/08 11:09
feature/bc-caja-rc18-ux-viewsonic-24-001     fdac03a   +8   16/08 13:39
feature/bc-caja-rc19-seguimiento-pilar-...   c4e5344  +10   16/08 14:06   <- Seguimiento
feature/bc-caja-rc20-alta-lote-pilar-abm-... 7883901  +12   16/08 14:21
release/bc-caja-rc18-rc20-integration-001    8b11c78  +15   16/08 15:10
feature/bc-caja-rc21-tabla-seguimiento-...   491c363  +38   16/08 23:13   <- TOPE
```

Todas son ancestros de la última: **`feature/bc-caja-rc21-tabla-seguimiento-logistica-001`
`491c363` es el tope real de la línea**, y su nombre engaña — su `VERSION.txt` dice:

```
BC Caja 1.0.0-rc.27
Misión: BC-CAJA-RC28-ALERTA-PEDIDOS-001 + BC-CAJA-RC29-HISTORIAL-JORNADAS-001
Integra: RC18 UX · RC19 Seguimiento · RC20 Alta de lote + ABM · RC21 Tabla logística ·
RC22 Vista por sucursal · RC23 Estado anclado a la fila · RC24 Tres acciones y selección
múltiple · RC25 Recepción con discrepancias · RC26 El atraso deja de trabar el circuito ·
RC27 Sucursal automática y queda a confirmar · RC28 La alerta de Pedidos abre sus pedidos ·
RC29 Historial agrupado por jornada
Esquema: migraciones 001-021
```

Los commits incluyen instalaciones reales de rc.21, rc.22, rc.23, rc.24, rc.25, rc.26 y
rc.27, con evidencia humana. **Esa línea se desarrolló e instaló en otra PC**: esta máquina
venía de rc.11 y su base tenía 14 migraciones.

## 3. Qué se recuperó y en qué estado está

**Módulos nuevos**, ninguno de los cuales existe en `main`:

- `modulos/caja_diaria/domain/tracking.py` (731 líneas)
- `modulos/caja_diaria/application/tracking_service.py` (1.098 líneas)
- `modulos/caja_diaria/application/close_report.py`, `continuous_report.py`
- Migraciones **016–021**: `work_tracking`, `pilar_shipments`, `branch_binding`,
  `reception_issues`, `branch_bindings_canonicas`, `queda_a_confirmar`
- 17 archivos de tests nuevos (~4.700 líneas) y 11 herramientas de captura

**El circuito implementado es exactamente el pedido:**
`ENVIADO_DESDE_PILAR → RECIBIDO_EN_ASUNCION → EN_LABORATORIO → RECIBIDO_DEL_LABORATORIO →
ENVIADO_A_PILAR → RECIBIDO_EN_PILAR → CERRADO`, con `ALLOWED_TRANSITIONS` como lista
cerrada, `NextAction` como autoridad única de próxima acción, `ETIQUETA_A_CONFIRMAR =
"QUEDA A CONFIRMAR"` como **rótulo derivado y no etapa**, y el atraso como condición
derivada que ya no traba el circuito (rc.26).

**Verificación ejecutada en esta PC sobre el tope de la línea:**

- `pytest tests` → **616 passed + 4 subtests**.
- 2 archivos no corren: `test_rc16_daily_envelope_report.py` y
  `test_rc17_continuous_daily_report.py` importan `fitz` (PyMuPDF), **dependencia no
  declarada** en `requirements.txt`. Es un hueco real de esa línea, no un fallo funcional.
- `pypdf` sí estaba declarado y faltaba instalado acá: se instaló y los 5 fallos de rc.13
  desaparecieron.

**No se descartó nada todavía.** Nada de esa línea se perdió ni se sobrescribió.

## 4. Diferencias contra rc.15 (lo que hoy es `main`)

Las dos líneas salen del mismo punto (rc.14) y **se pisan en Pedidos**:

| Tema | `main` (rc.15) | Línea recuperada (rc.27) |
| --- | --- | --- |
| Seguimiento Pilar | **no existe** | completo, con dominio, servicio, esquema y UI |
| Apertura automática | **sí** (fecha/hora del sistema, `Consultar otro día`, `Caja inicial` destacada) | **no**: sigue con `ABRIR / CONSULTAR` |
| `Requieren atención` | sí (`ATTENTION_FILTER`) | sí (`FILTRO_REQUIEREN_ATENCION`) — **misma idea, distinto nombre** |
| Alerta de Pedidos | cuenta y abre el mismo conjunto | **mejor**: `orders_alert()` transporta su propio filtro y soporta sucursal |
| Estado del pedido en la grilla | chips flotantes posicionados sobre el frame | **mejor**: tag de fila del Treeview — rc.23 eliminó los chips flotantes **como defecto** |
| Agrupación `ATRASADOS`/`PARA HOY` y `Última novedad` | **sí** | no en la grilla de Pedidos |
| `Corregir estado` de pedidos con lista cerrada | **sí** | no (tiene la suya para Seguimiento) |
| Contraste habilitado/deshabilitado | **sí** (rc.15) | no |
| Versión en el pie | literal `1.0.0-rc.15` | `version_aplicacion()` dinámico |
| Migraciones | 015 | **021** (016–021 son aditivas sobre 015: no chocan) |

## 5. Medición de la integración

`git merge origin/main` sobre el tope de la línea recuperada:

- **8 archivos en conflicto, 17 conflictos, ~400 líneas en disputa.**
- Sustanciales: `CajaDiaria.py` (10 conflictos, 279 líneas), `ui/controller.py`,
  `application/services.py`. El resto es trivial (`.gitignore`, `VERSION.txt`,
  `INSTALACION.txt`, `build_pilot.ps1`, un test de contrato).
- El merge se **abortó a propósito**: los conflictos de `CajaDiaria.py` no son mecánicos.
  Son **dos diseños distintos de la misma grilla de Pedidos**, y resolverlos "por unión"
  reintroduciría los chips flotantes que rc.23 ya eliminó como defecto.

Aplicando **sólo Apertura** (`0f10266`) sobre la línea recuperada:
**2 conflictos en `CajaDiaria.py`, 25 líneas**, más un test de contrato. Es decir: portar lo
mío hacia la línea recuperada cuesta ~40 líneas; portar Seguimiento hacia `main` cuesta
12.590 líneas y 6 migraciones.

## 6. Recomendación

**Adoptar la línea recuperada como tronco y reaplicar encima sólo lo que aporta rc.15.**

1. Tronco: `feature/bc-caja-rc21-tabla-seguimiento-logistica-001` (`491c363`, rc.27).
2. Reaplicar de rc.15: **Apertura automática** (no existe allá) y el **contraste de
   acciones habilitadas/deshabilitadas** (aplicado a los botones de esa línea).
3. Descartar de rc.15: la reescritura de la grilla de Pedidos — la de rc.23/rc.28 es
   posterior y corrige un defecto que la mía tiene.
4. Dejar para un slice propio: llevar `ATRASADOS`/`PARA HOY`, `Última novedad` y el
   `Corregir estado` de lista cerrada de pedidos **al diseño de la línea recuperada**.
5. Declarar `fitz` (PyMuPDF) en `requirements.txt` o quitar esa dependencia de los tests.

Esto **no descarta trabajo validado**: lo de Apertura se conserva; lo de Pedidos se
reemplaza por una versión posterior que resuelve lo mismo y además arregla un defecto.

## 7. Por qué no se ejecutó automáticamente

Reemplazar la grilla de Pedidos que se validó con gate humano y se instaló ayer es una
**decisión de producto**, no una resolución de conflicto. Y la contraria —portar 12.590
líneas ya validadas hacia `main`— rehace trabajo que ya pasó por gates humanos e
instalaciones reales.

`main` quedó intacto en `65d2df4`. La instalación de esta PC sigue en rc.15.
