# BC-CAJA-PEDIDOS-OPERATIVOS-RC30-001

Pedidos se puede atender sin abrir otra ventana. Sobre el diseño del tronco rc.30, sin
resucitar nada de la grilla de rc.15.

## Lo que se conservó como autoridad

Estado anclado a la fila (RC22/RC23, sin chips flotantes), alerta que transporta su filtro
(RC28) con su línea de contexto y `Ver todos`, vista por sucursal, e integración con
Seguimiento y `NextAction` intactas.

## Lo que cambió

| Antes | Ahora |
| --- | --- |
| Lista plana | `ATRASADOS` y `PARA HOY` agrupados, con fallback a `PRÓXIMOS` |
| Se poblaba al tocar un filtro | Se puebla al abrir la ventana |
| 9 columnas con CI/RUC, Origen, Sucursal y Vendedora | 8: `Prometido`, `Cliente`, `Sobre`, `Trabajo`, `Laboratorio`, `Estado`, `Atraso`, `Última novedad` |
| No decía qué pidió el cliente | `Trabajo` sale de los artículos de la venta, o de la venta si no hay artículos |
| El laboratorio había que buscarlo en el ABM | La fila muestra `LAB ALFA · 021 100 100`, cruzando por nombre con el ABM |
| El teléfono ocupaba una columna | El teléfono se usa donde sirve: la acción de contacto |
| Sin novedad visible | `17-08 LISTO · Llegó del laboratorio`, con el motivo recortado a 40 caracteres |
| El atraso había que calcularlo leyendo la fecha | Columna `Atraso`: `6 días`, `hoy`, y vacío si ya se entregó |
| 3 botones de estado, la reversión con motivo libre | 3 acciones: `Acción siguiente`, `Contactar`, `Más ▾` |
| `Corregir estado` no existía para pedidos | En `Más ▾`, lista cerrada del dominio, observación y responsable obligatorios |

`Atraso` es condición derivada de la fecha prometida, no un estado guardado: un pedido
entregado no arrastra atraso.

## Laboratorio y contacto

Los pedidos guardan el laboratorio como texto de la venta; el ABM lo tiene con línea y
WhatsApp. `laboratory_contact()` los cruza por nombre normalizado, así que el número
aparece en la grilla sin entrar al ABM. `Contactar` prioriza al laboratorio —que es a quien
hay que apurar— y cae en el teléfono del cliente si el laboratorio no tiene contacto.

## Corregir estado

`allowed_order_transitions` deriva la lista de `ORDER_TRANSITIONS`, la única fuente de
verdad del dominio. El selector es `readonly`, no acepta texto libre, y sin observación no
guarda nada. Queda auditado en `order_status_revisions` con actor y motivo.

## Validación

| Nivel | Resultado |
| --- | --- |
| Focalizados del slice | 13 passed |
| Suite completa | **682 passed + 4 subtests** (669 de baseline + 13) |
| Visual 1920×1080 y 1366×768 | smoke fail-closed propio del slice |
| Regresión de la alerta (RC28) | verde |
| Regresión de Seguimiento (RC27) | verde |
| Migraciones | 21, sin agregar ninguna |
| Reglas económicas | sin cambios |

El smoke verifica sobre los widgets: agrupación, que cada fila diga qué pidió el cliente,
que el laboratorio traiga su teléfono, que el atraso se vea, que la novedad aparezca, que
haya exactamente tres acciones, que un encabezado de grupo no habilite nada y que el salto
de luminancia entre disponible y no disponible sea de al menos 0,30.

## Contratos que hubo que mover

`test_operator_fixes_003` y `test_rc10_operative_polish` fijaban las columnas viejas;
`test_rc28` y `test_rc25` cortaban el código por marcadores que el slice desplazó. Se
actualizaron preservando su intención, con el porqué escrito. Las funciones nuevas se
llamaron `abrir_opciones_pedido` / `boton_opciones_pedido` justamente para no sombrear el
`abrir_menu_mas` de Seguimiento, que sus contratos localizan por prefijo.

## Preparado, no implementado

La barra de Pedidos ya habla el mismo vocabulario que Seguimiento —`Acción siguiente`,
contacto contextual, `Más ▾`—, que es lo que después permitirá unificarlos bajo
`Caja diaria | Trabajos | FactuFácil | Historial`. **Ese rediseño no se hizo.**
FactuFácil, Composturas y el DatePicker global siguen sin empezar.

## Sobre el Headless Executor

**No existe en BC-Core.** `tools/` no tiene ningún executor headless y no hay un solo
archivo que mencione `headless`. Se continuó con el mecanismo actual, como estaba previsto
para ese caso. No hay métricas de `interactive_prompts` ni `stdin_waits` que reportar: no
se inventan.

---

# Cierre en producción — 18-08-2026, PC de la Óptica

**rc.31 quedó instalada y validada. La misión cierra 100% PASS.**

Lo que faltaba no era código: era llegar a la máquina correcta. El paquete se recuperó del
release privado tal cual se había publicado —**no se reconstruyó**, que era justamente el
punto: PyInstaller no da binarios reproducibles y un rebuild habría roto la verificación
con todo en orden— y se instaló sobre rc.30 con backup y rollback armados antes de mover
nada.

| | |
| --- | --- |
| Versión anterior → instalada | 1.0.0-rc.30 → **1.0.0-rc.31** |
| zip / exe verificados por sha256 | sí, el exe **antes** de tocar la instalación vigente |
| Backup preinstall | con hash idéntico al original |
| Rollback | dos copias independientes de rc.30, ambas verificadas |
| Rollback ejecutado | no hizo falta |
| Base productiva | **sha256 idéntico antes y después** |
| `integrity_check` · `foreign_key_check` | ok · 0 |
| Migraciones | 21, sin agregar ni perder ninguna |
| Suite en la Óptica | 682 passed, 4 subtests, exit 0 |
| Artifact Consistency | PASS, 12 sha256 |
| `main` | promovido por fast-forward, sin force-push |

El punto 10 del gate —el que había quedado observado en la generación 1— se verificó esta
vez **en producción y no sobre fixtures**: al tocar `Pedidos`, la barra de navegación
resalta `Pedidos`.

Y la preservación de datos tiene una comprobación que no depende de los mismos scripts que
hicieron la validación: Historial "Este mes" muestra `2.220.000 + 3.350.000` en ventas más
una venta `ANULADO` de `830.000`, que suman exactamente los `6.400.000` del
`SUM(cash_entries.total)` de la línea base. Los datos reales están enteros y la anulación
histórica sigue siendo una anulación.

## Una cosa que apareció y no se tocó

Al abrir, la app pide `Configuración inicial administrativa`. No es una regresión de rc.31:
`admin_users` está en 0 y ya lo estaba bajo rc.30. Configurar esa credencial es decisión
del dueño, no del instalador, así que quedó registrada como deuda y no se creó ninguna.

Detalle completo y hashes en `INSTALL_EVIDENCE.md`.
