# Install Evidence — BC Caja 1.0.0-rc.20

## Precheck

| Comprobación | Resultado |
|---|---|
| Instancias de BC Caja activas | 0 (`tasklist` y procesos python) — libre para instalar |
| WAL de la base | 0 bytes: sin datos pendientes |
| SHA256 del artifact | `C3B6F646…16DB577` ✓ coincide con el autorizado |
| Versión en el ZIP | `BC Caja 1.0.0-rc.20` ✓ |
| ZIP: entradas / migraciones | 1157 / 17 `.sql` |
| Instalación previa | `BC Caja 1.0.0-rc.17` presente |
| `integrity_check` producción | ok |
| Migraciones producción | 001–015 |
| Mission Leases | 0 |
| Worktree / sync | limpio, `0/0` |

Censo previo (19 tablas): `cash_days=6`, `cash_entries=8`, `orders=2`,
`sale_items=2`, `cash_entry_revisions=11`, `cash_counts=3`,
`cash_count_snapshots=1`, `mail_outbox=1` (SENT=1), `mail_history=5`,
`admin_audit_log=17`, `admin_users=1`, `app_settings=3`.

## Backup y rollback

- Data root completo → `%LOCALAPPDATA%\BC\Caja-INTEGRATION-preinstall-20260816`
  (33 archivos; la copia de la base abre con `integrity_check=ok` y 6 cajas).
- Instalación vigente → `BC-Caja-Pilot.rollback-rc17-20260816`.
- Preservados sin tocar: RC17 original, `rollback-rc16-20260815`,
  `rollback-rc15-20260815`, 8 instalaciones previas y los 27 backups del
  historial.

## Instalación

Reemplazo transaccional: extracción a staging, verificación de versión y hash
antes de tocar nada, y la carpeta vigente se **aparta** en vez de borrarse,
con restauración inmediata si el reemplazo falla. Solo se reemplazó la carpeta
del programa: la base, la configuración y los backups no se tocaron.

| Item | Valor |
|---|---|
| Destino | `%LOCALAPPDATA%\Programs\BC-Caja-Pilot` |
| Versión instalada | `BC Caja 1.0.0-rc.20` |
| SHA256 EXE final | `E2C8081F2200C9491AF0843D2FAFBCC6C9147CFD99291D97B22A1C14BD893228` |
| SHA256 ZIP final | `8FE9F6EC2FEDF93C298255186FCA979F238B05E1F4C13600ED8B4DC198F0C24C` |

## Defecto encontrado por el post-install y corregido

La primera instalación quedó **funcionalmente correcta pero mal
autoidentificada**: el pie de la aplicación seguía mostrando `1.0.0-rc.17`
porque la versión estaba cableada en `CajaDiaria.py`. El paquete decía rc.20 y
el programa decía rc.17.

No se parcheó producción a mano. Se corrigió en origen: el pie ahora lee la
versión del `VERSION.txt` que el propio build empaqueta, con constante de
respaldo verificada por prueba, de modo que programa y paquete no puedan
divergir. Se reconstruyó y se reinstaló con el mismo procedimiento
transaccional.

Una prueba de RC15 fijaba el literal `BC Caja 1.0.0-rc.17`; se actualizó
conservando su intención —que la versión sea visible en el pie— y ahora
verifica el mecanismo en lugar del literal.

Regresión tras la corrección: **339 PASS / 0 FAIL**.

## Post-install sobre la instalación real

| Comprobación | Resultado |
|---|---|
| Arranque | La aplicación abre y sostiene la ventana `Caja diaria - Óptica` |
| Versión en el pie | `BC Caja 1.0.0-rc.20` ✓ |
| Migraciones | 001–017 (17) |
| `integrity_check` | ok |
| Tablas nuevas | `laboratories`, `pilar_shipments`, `tracked_works`, `tracked_work_transitions`, `tracked_work_contacts` |
| Datos preexistentes | Idénticos al precheck en las 19 tablas |
| Único delta | `app_settings` 3 → 4: la clave `tracking` que agrega la migración 016. `branch`, `counting` y `mail` (SMTP) **sin modificar** |
| Cierres | 2, igual que el precheck → **cero cierres nuevos** |
| Correos | `mail_outbox=1`, `SENT=1`, `PENDING=0`, `mail_history=5`, todos iguales al precheck → **cero correos** |
| Cambios económicos | Ninguno |
| RC18 | Jerarquía del resumen visible en la instalación: Venta / Efectivo / Esperado destacados, secundarios agrupados y atenuados |
| RC19 | Pestaña **Seguimiento** presente en la navegación |

Las capturas del post-install se tomaron con `PrintWindow` sobre el DC propio
de la ventana, que por construcción no puede incluir otras aplicaciones.

### Límite de esta validación, declarado

No se pudo **conducir** la interfaz del ejecutable congelado: los controles de
CustomTkinter se dibujan sobre canvas y no responden a clics sintéticos por
mensaje de ventana. En consecuencia:

- RC18 y RC19 están verificados **visualmente sobre la instalación real**
  (jerarquía del resumen y pestaña Seguimiento presentes).
- RC20 —diálogo *Nuevo envío desde Pilar*, ABM de laboratorios, línea y
  WhatsApp distintos y ventana por defecto de tres días— está verificado en
  código y en las sondas GUI del mismo commit, y su presencia en el binario
  queda sostenida porque el arranque falla si esos módulos no están; pero
  **no fue ejercitado interactivamente sobre el binario instalado**.

Queda como comprobación manual de dos minutos: abrir Seguimiento, pulsar
*Nuevo envío desde Pilar* y *Laboratorios*.

## Rollback

**No utilizado.** Disponible y verificado en
`BC-Caja-Pilot.rollback-rc17-20260816`, más `rollback-rc16-20260815`,
`rollback-rc15-20260815`, `replaced-rc17-20260816` y el snapshot de datos
`Caja-INTEGRATION-preinstall-20260816`.

## Privacidad

Durante el post-install, un intento de captura por región de pantalla trajo
contenido ajeno porque Windows impide que un proceso en segundo plano traiga
la ventana al frente. La regla fail-closed se aplicó: la imagen se **eliminó
de inmediato**, nunca fue indexada ni commiteada, y el método se cambió a
`PrintWindow`.
