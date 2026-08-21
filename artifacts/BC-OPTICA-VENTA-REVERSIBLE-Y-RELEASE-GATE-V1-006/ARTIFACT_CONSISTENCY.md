# Artifact Consistency — BC-OPTICA-VENTA-REVERSIBLE-Y-RELEASE-GATE-V1-006

Cada afirmación de los artefactos contra lo que el repositorio y las corridas
realmente dicen. Lo que no se pudo verificar está marcado como tal en vez de
darse por bueno.

## Cadena y estado canónico

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `origin/main` = `7db56a0` | `git rev-parse origin/main` | ✔ |
| Slice 1 `ed0dbba` (022) | `git log -1 origin/feature/bc-optica-commercial-core-foundation-v1-001` | ✔ |
| Slice 2 `54f5f06` (023) | ídem 002 | ✔ |
| Slice 3 `ecc0c7b` (024) | ídem 003 | ✔ |
| Slice 4 `b580e50` (025) | ídem 004 | ✔ |
| Slice 5 `a8443a3` (026) | ídem 005 | ✔ |
| La cadena es lineal | `git merge-base --is-ancestor` en los cuatro tramos | ✔ |
| Ningún slice en `main` | `git merge-base --is-ancestor 005 origin/main` | ✔ no está |
| El slice 6 sale del tip del 5 | `git log -1` del worktree = `a8443a3` | ✔ |

El handoff del slice 5 anota el tip del slice 5 como `91071c5`. El tip real es
`a8443a3`, que es el commit del propio Safe Pause y contiene a `91071c5`. No es
una discrepancia: es el handoff nombrando el commit de código en vez del commit
de documentación que él mismo agregó.

## Mecanismo de reversión

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `SALE_COMPLETED` no se toca | prueba compara la fila completa antes y después | ✔ |
| Movimientos `VENTA` no se tocan | id, cantidad y momento comparados | ✔ |
| Líneas históricas quedan | `sale_items` intacta tras anular | ✔ |
| Compensación append-only | `UPDATE` y `DELETE` sobre `sale_void_compensations` rechazados | ✔ |
| Doble anulación no duplica | tres guardados seguidos, un solo movimiento | ✔ |
| Retry tras crash no duplica | fallo inyectado después de compensar, rollback total, reintento correcto | ✔ |
| Venta sólo servicio no inventa movimientos | `stock_movements` en cero, `movement_count` 0 | ✔ |
| Venta mixta compensa sólo stock | cristal y compostura sin movimiento | ✔ |
| Sucursal correcta | venta en Pilar vuelve a Pilar, Asunción queda en 0 | ✔ |
| Actor obligatorio | `AnulacionSinResponsable` sin nadie que firme | ✔ |
| Motivo obligatorio | `InvalidCashDayError` desde el dominio | ✔ |
| Rollback completo ante fallo | ni anulación ni devolución quedan a medias | ✔ |
| Caja no se duplica | totales a 0, sin columnas de dinero en `stock_movements` | ✔ |
| No hay reversión parcial | trigger rechaza el registro si falta compensar uno | ✔ |
| Una venta anulada no revive | trigger rechaza volver a `ACTIVE` | ✔ |
| `VENTA_ANULADA` es reservado | trigger rechaza usarlo fuera de una compensación | ✔ |

## Release gate

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Cadena 21 → 27 | `schema_migrations` sobre la copia | ✔ |
| `integrity_check` ok | `PRAGMA integrity_check` | ✔ |
| Sin violaciones de FK | `PRAGMA foreign_key_check` | ✔ 0 |
| Ninguna tabla perdida | conjunto anterior ⊆ posterior | ✔ |
| Ninguna fila cambiada | huella por tabla sobre las columnas preexistentes | ✔ |
| Datos preservados | 8 entradas, 2 líneas, suma 2.115.000 sin cambios | ✔ |
| Rollback | restaurar el backup da el mismo sha256 y vuelve a 021 | ✔ |
| Base de origen intacta | sha256 idéntico antes y después | ✔ |

## Packaging y smoke

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Paquete rc.32 construido | `BC_CAJA_BUILD_OK version=1.0.0-rc.32` | ✔ |
| Las 27 migraciones viajan adentro | conteo en `_internal/.../migrations` | ✔ |
| El módulo comercial viaja adentro | 18 módulos leídos del PYZ del `.exe` | ✔ |
| El ejecutable arranca | proceso vivo tras el arranque | ✔ |
| Migra por su cuenta | la copia llega a 027 sin intervención | ✔ |
| No pierde datos | entradas, líneas y suma sin cambios | ✔ |
| UI Comercial abre | tres pestañas y el buscador, contra base migrada | ✔ |
| El zip no va al remoto | gitignored, igual que rc.12, rc.13, rc.14 y rc.30 | ✔ |

## Lo que NO se verificó, y hay que decirlo

- **El gate no corrió sobre la base productiva de la Óptica.** Esa base no está
  en PC Casa. Corrió sobre la base local del piloto de esta máquina, que tiene la
  misma forma y la misma cadena pero otros datos. Antes de instalar en la Óptica
  hay que correr el mismo script allá.
- **No hubo instalación**, ni acá ni allá. El paquete existe y quedó local.
- **La UI Comercial se abrió desde el árbol de código**, no desde el ejecutable
  congelado. Lo que sí se verificó del ejecutable es que lleva esos módulos
  adentro.
- **Anular exige que el día esté abierto** (`CashDay._require_open`). Una venta
  de un día ya cerrado no se puede anular hoy. Es preexistente al slice; queda
  anotado como deuda.

## Suite

- Dirigidas primero: 31 casos nuevos, verdes.
- Completa, una vez al cierre: **934 passed, 2 failed**.
- Las 2 son `BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001`. Verificado sobre el commit
  base `a8443a3`: 903 passed y **las mismas 2 fallas**. No las introduce este
  slice.
- En una corrida intermedia apareció además
  `test_sync_is_idempotent_and_rejects_event_mutation`; no reprodujo en dos
  corridas completas posteriores, ni aislado, ni en su directorio. Se registra
  como flake observado de la misma familia, no como regresión.
