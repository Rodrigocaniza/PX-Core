# BC Caja 1.0.0-rc.15 — Apertura + Pedidos

RC candidata única. Integra dos misiones con gate humano PASS, sobre la línea canónica
real `origin/main` `098a9fb` (rc.14).

## Qué trae

**Apertura de Caja** (`BC-CAJA-APERTURA-CAJA-001`)
- La fecha la pone el sistema y no se tipea; la caja se abre siempre con hoy.
- La hora de apertura la registra el dominio (`CashDay.opened_at`) y se muestra:
  `Estado: ABIERTO · 08:32`. Nunca se pide.
- `Consultar otro día` es el único acceso al histórico y carga en **sólo lectura**:
  sólo la caja de hoy es operable, aunque un día pasado haya quedado `OPEN`.
- `Caja inicial` destacada en la cabecera.

**Pedidos, qué requiere atención ahora** (`BC-CAJA-PEDIDOS-ATENCION-002`)
- `Requieren atención` = no entregados con entrega `<=` hoy; es la vista por defecto y la
  grilla se puebla al abrir.
- Agrupado `ATRASADOS` / `PARA HOY`, con fallback a `PRÓXIMOS`; nunca una hoja vacía.
- `⚠ Trabajos N` cuenta y abre exactamente el mismo conjunto.
- 8 columnas con `Última novedad`; 3 acciones; `Corregir estado` con lista cerrada
  derivada de `ORDER_TRANSITIONS` y observación obligatoria.
- WhatsApp por doble clic en el teléfono, sin botón nuevo.

## Cómo se integró

1. Apertura aplicada primero sobre `origin/main`.
2. Pedidos **reaplicado** encima del nuevo estado (cherry-pick, no merge de la rama vieja).
3. Único conflicto real: `.bc-command-center/verification.json` — ambas misiones agregaban
   su entrada en el mismo punto. Resuelto conservando las dos y agregando la de la RC.
   `CajaDiaria.py` auto-mergeó limpio: tocan zonas distintas (cabecera vs pestaña Pedidos).
4. Nada de código de rc.11 entró: el port ya se había reescrito sobre rc.14.

**Corrección UX de rc.15** — las acciones de Pedidos se distinguían demasiado poco entre
habilitadas y deshabilitadas. Ahora:
- disponible: color sólido y oscuro con texto blanco (`#12855A` listo, `#A85408` corregir,
  azul entregado), sin borde;
- no disponible: gris apagado real `#DDE3EB` con texto `#7C8899` y borde `#BCC7D6`;
- al pasar el mouse por una acción no disponible, un aviso dice **por qué**
  («Elegí un pedido PENDIENTE para marcarlo listo.»), dibujado dentro de la ventana para
  no romper el marco nativo;
- la captura verifica, pedido por pedido, que el salto de luminancia entre disponible y no
  disponible sea de al menos 0,30 y que la próxima acción válida esté siempre habilitada.

## Verificación post-integración

| Nivel | Resultado |
| --- | --- |
| Focalizados Apertura | 13 passed |
| Focalizados Pedidos | 21 passed |
| Adyacente (arqueo, admin, correo, sesión, rc.10/rc.11/rc.5, operator fixes) | 31 passed |
| Regresión completa `tests` | **258 passed + 4 subtests** (225 baseline + 10 + 18 + 5 de contraste) |
| Visual automatizada 1920×1080 | 5 capturas fail-closed |
| Regresión visual 1366×768 | 4 capturas fail-closed |
| Preflight sobre producción | PASS (`PREFLIGHT.md`) |
| Migración rc.11 → rc.15 sobre clon de la base real | PASS (`PREFLIGHT.md`) |
| Binario empaquetado | arranca y aplica las 15 migraciones sobre base temporal |

Lo verificado explícitamente sobre la RC combinada: apertura con fecha/hora actuales,
histórico en sólo lectura, `Caja inicial` destacada, Pedidos abriendo en
`Requieren atención`, contador y navegación coincidentes, `Corregir estado` cerrado al
dominio, y `Arqueo` / `Administrador` / correo de cierre presentes y en verde.
**Reglas económicas sin cambios. Sin migraciones nuevas respecto de rc.14.**

## Paquete

| | |
| --- | --- |
| ZIP | `releases/BC-CAJA-1.0.0-rc.15-win64.zip` (24.148.167 bytes) |
| zip_sha256 | `c82f89b9461faf7a6f15bc36a7df46653565d21cdb56271a404f97b796618aef` |
| exe_sha256 | `44bf7225f0edc2befcf57ba37b5faed47ceee62c73b1518c2f611775b316b80d` |
| Backup previo | `bc-caja-pre-1.0.0-rc.15-20260817-161651-884812.sqlite3`, sha256 idéntico al original |
| Rollback | `ROLLBACK.md` |

## No instalado

La instalación quedó frenada por `INSTALL_GATE-RC15-001`: **la versión instalada en esta
PC es rc.11**, no rc.14. Instalar rc.15 promovería también rc.12, rc.13 y rc.14 —
incluyendo la migración 015, que no tiene inversa, y el administrador con correo de cierre.
Eso excede lo que validaron los dos gates. Ver `INSTALL_GATE.md`.

## Fuera de alcance

DatePicker global, FactuFácil y Composturas siguen sin empezar. Laboratorio en la grilla de
Pedidos y la cabecera responsive a 1366×768 (deuda anterior) siguen en la cola.
