# Safe Closure — BC-CAJA-RC25-RECEPCION-ALERTA-001

Cierre canónico de la misión. Prueba manual confirmada por el responsable
sobre la instalación productiva `BC Caja 1.0.0-rc.24`.

## Evidencia humana

El responsable confirmó haber ejecutado la prueba manual sobre el binario
instalado y que los puntos funcionales se comportan correctamente. Esa
confirmación **cierra el límite declarado** en `INSTALL_EVIDENCE.md`: la UI del
ejecutable congelado no se puede conducir por automatización, así que los
ítems funcionales estaban verificados por smoke GUI sobre el mismo commit
empaquetado, no sobre el mismo proceso. Con la confirmación humana, quedan
verificados también sobre el proceso instalado.

## Verificación de cierre

### Instalación

| Comprobación | Resultado |
|---|---|
| Versión instalada | `BC Caja 1.0.0-rc.24` |
| SHA256 EXE instalado | `A8960365EC27430E810A08E394145A90FB2F48359427C02139C47EE71102E264` |
| Migraciones en el paquete | 20 |
| Instancias activas | 0 |

### Repositorio

| Comprobación | Resultado |
|---|---|
| Branch | `feature/bc-caja-rc21-tabla-seguimiento-logistica-001` |
| HEAD local | `df06412` |
| HEAD remoto | `df06412` — idénticos |
| Worktree | `.worktrees/caja-rc21-tabla-seguimiento`, limpio |
| Remoto | `origin` → `Rodrigocaniza/PX-Core` |
| `main` | `098a9fb`, **intacto**, no se tocó |
| Historial de push | fast-forward `02e9006 → dfd1514 → 893792c → df06412`, **sin force-push** |
| Mission Leases residuales | **0** |

Commits de la misión, los cuatro presentes y alcanzables:

```
dfd1514  feat(caja): recepcion con discrepancias visibles y alerta de sucursal
ad9cd4e  release(caja): consolidar 1.0.0-rc.24 sin instalar
893792c  fix(caja): el valor de respaldo de version sigue al paquete
df06412  docs(caja): evidencia de instalacion de 1.0.0-rc.24
```

### Base productiva

| Comprobación | Resultado |
|---|---|
| `integrity_check` | ok |
| `foreign_key_check` | ok |
| Esquema | 001–020 |
| Bindings | `P2 → PILAR` · `PC → ASUNCION` · `PILAR → PILAR` |

**Datos económicos, outbox y cierres:** diff contra
`Caja-RC24-preinstall-20260816e` sobre `cash_entries`, `cash_days`,
`cash_entry_revisions`, `sale_items`, `cash_counts`, `cash_count_snapshots`,
`orders`, `order_status_revisions`, `app_settings`, `admin_users`,
`admin_audit_log`, `mail_outbox`, `mail_history` y `laboratories` →
**ninguna diferencia**.

Cierres `3/3`, outbox `1/1`, mail_history `5/5`.

Los únicos cambios respecto del backup son los ya documentados:

| Cambio | Origen |
|---|---|
| `schema_migrations` 18 → 20 | migración canónica autorizada |
| `tracked_works` 15 → 0 | reinicio deliberado del escenario TEST |
| `tracked_work_transitions` 15 → 0 | ídem |
| `pilar_shipments` 1 → 0 | ídem |

Escenario TEST en punto inicial: **15 candidatos, 0 en circuito**.

### Artifact Consistency

| Comprobación | Resultado |
|---|---|
| Referencias a imágenes en los `.md` | todas resuelven, 0 rotas |
| Commits citados en la evidencia | existen |
| `SHA256 ZIP` declarado vs real | coincide |
| `SHA256 EXE` declarado vs instalado | coincide |
| Regresión declarada (497) vs real | coincide |
| Esquema declarado (001–020) vs real | coincide |

14 archivos: 3 documentos y 11 capturas.

### Gates de cierre

| Gate | Resultado |
|---|---|
| Regresión | **497 PASS / 0 FAIL** |
| Focused RC25 + E2E 15 TEST | **58 PASS** |
| Smoke GUI 1920×1080 | PASS |
| Smoke GUI 1366×768 | PASS |
| Smoke GUI RC19 (no regresión) | PASS |
| Correos nuevos | 0 |
| Cierres nuevos | 0 |
| Rollback usado | **NO** |

### Librarian → QA → Auditor

**No disponibles en este repositorio.** No existe tooling de `Librarian`, `QA`
ni `Auditor` (`.claude/agents`, `.claude/skills` y `.claude/commands` no
existen). No se simuló su ejecución. Sus comprobaciones equivalentes se
hicieron de forma directa y quedan arriba: consistencia del artifact
(Librarian), regresión y smokes (QA), y diff de datos, hashes e historial de
push (Auditor).

## Rollback disponible

`BC-Caja-Pilot.rollback-rc23-20260816e` (rc.23), más rc.22, rc.21, rc.20,
rc.17, rc.16 y rc.15. Snapshot de datos `Caja-RC24-preinstall-20260816e`.

## Alcance no tocado

Lógica económica, cierres, arqueos, convenios, correo, FactuFácil,
Comunicaciones, DatePicker y Gestión Central. Ninguna misión siguiente se
inició durante el cierre.

---

**BC CAJA 1.0.0-rc.24: CLOSED**
