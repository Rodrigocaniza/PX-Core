# BC — Piloto E2E simulado ASUNCIÓN ↔ PILAR

Piloto enteramente temporal. No usa bases, licencias, endpoints ni secretos de
producción. Compone los snapshots de Historial, Sync, Security ↔ Sync, Receiver
y `modulos/seguridad` del HEAD `19ee0477a36b639115e2b495fdffe5db225a5fe6`.

## Composición

- Seguridad real: enrolamiento, licencia firmada, trust store temporal,
  autorización, firma Ed25519, verificación, nonce y revocación.
- El único límite simulado de Seguridad es DPAPI: un `PilotSealer` de memoria,
  confinado al test, representa dos máquinas distintas.
- Sync real: outbox SQLite durable, reanudación, firma vigente y ACK.
- Receiver real: licencias/revocaciones verificadas, inbox/proyección atómicos.
- Historial real: `GlobalHistoryService` consume `CentralHistoryReader` read-only.
- FactuFácil real: cola y adapter asistido/desactivado, sin scraping ni API falsa.

## Evidencia de escenarios

1. ASUNCIÓN y PILAR: cuatro tipos de hechos por instalación, autenticados y
   proyectados una sola vez, conservando sucursal.
2. Cliente global: CI fuerte une ambas sedes; homónimos sin documento quedan
   ambiguos y separados.
3. Offline/reinicio: el evento sigue en outbox y se confirma al reconectar.
4. ACK perdido: Central aplica una vez; retry recibe respuesta idempotente.
5. Seguridad A–G: válida ALLOW; licencia alterada, revocación, payload alterado,
   replay, branch e instalación falsa se rechazan sin segundo efecto.
6. FactuFácil: pendiente, asistido, cargada/factura, error, reintento y
   recuperación llegan a Central sin duplicarse.
7. Reinicio completo: outbox, inbox y proyección reaparecen desde disco.
8. Permisos: consulta global y Admin permitidos; operador no escribe otra sede;
   lectura Central abre SQLite con `mode=ro` y `query_only`.

## Defectos encontrados

- Faltaba un `HistoryReader` sobre la proyección de Gestión Central. Se añadió
  `CentralHistoryReader`, estrictamente read-only.
- La primera ejecución tuvo una aserción de test demasiado literal sobre
  `?mode=ro`; se corrigió el test. No era defecto de producto.

## Piloto físico pendiente

Promover la cadena de PRs, ejecutar con DPAPI real en dos PCs, trust store y
licencias oficiales, red/endpoint autorizados, NTP, backups/ACL/monitorización,
prueba de cortes reales, conciliación operativa y aprobación humana antes de
habilitar cualquier servicio.
