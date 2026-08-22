# BC Gestión Central — Sync Receiver V1

Rama apilada sobre el contrato Security ↔ Sync de PR #16. Los snapshots y PR
#14/#15/#16 permanecen intactos.

## Frontera de seguridad

`DurableVerifiedRemoteLicenseProvider` implementa el puerto previsto por Sync.
Guarda únicamente sobres públicos firmados de licencia/revocación y los vuelve
a verificar mediante `NativeBCSecurityDocumentBackend` en cada uso. Valida
organización, capacidad `bc.sync`, expiración y sucursal contra `Unit`.

`BCSecuritySyncAuthProvider` completa el flujo verificando credencial Ed25519,
hash del mensaje, nonce y timestamp antes de entregar una identidad a Central.
Ningún claim del cuerpo se acepta hasta compararlo con esa identidad.

El backend nativo usa imports diferidos porque BC Seguridad aún vive en su rama.
El harness equivalente existe sólo en pruebas y desaparece del despliegue.

## Inbox y proyección

`CentralSyncInbox` usa una transacción `BEGIN IMMEDIATE` para insertar inbox y
proyección como una unidad. `event_id` y `(installation_id,idempotency_key)` son
únicos. Un retry legítimo lleva otro nonce, se autentica otra vez y responde como
duplicado sin producir otro efecto. Un replay del mismo envío se rechaza antes.

SQLite usa WAL y `synchronous=FULL`. Reiniciar no pierde inbox, proyección ni
auditoría. La lectura se ordena por timestamp del evento y `event_id`.

Las proyecciones iniciales incluyen cliente/historial, venta, sobre, receta,
evento y estado FactuFácil. Para FactuFácil se exponen estado, factura, sucursal,
venta y sobre. No se añadió ninguna pantalla ni se volvió canónico al proveedor.

## Integración física pendiente

1. Promover PR #14, #15 y #16 en su orden y componer BC Seguridad.
2. Configurar el trust store oficial y contexto `organization_id` de Central.
3. Cargar por canal administrativo los sobres firmados de ASUNCIÓN/PILAR y la
   lista de revocación vigente; no transportar claves privadas.
4. Instalar almacenamiento Central con ACL, backup, monitorización y reloj NTP.
5. Conectar el endpoint autenticado al `CentralSyncInbox` y definir ACK sólo
   después del commit.
6. Ejecutar piloto bidireccional, conciliación e inspección de auditoría.
7. Diseñar pantallas posteriores consumiendo proyecciones, sin escribir en sedes.
