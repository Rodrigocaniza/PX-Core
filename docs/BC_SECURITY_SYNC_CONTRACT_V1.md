# BC Seguridad ↔ BC Sync — contrato V1

Esta rama se apila sobre `feature/bc-sync-opticas-v1-001`. No incorpora ni
duplica los módulos de Seguridad porque su PR todavía no fue promovido.

## Autoridad

BC Seguridad es la única autoridad de `installation_id`, `branch_id`, licencia,
revocación, firma, timestamp y nonce. Sync no genera identidad, no guarda clave
privada y no decide revocaciones.

- `SecurityIdentityProvider` entrega sólo una identidad ya autorizada.
- `SyncSignerAuthProvider` firma y verifica mensajes sin revelar material secreto.
- `BCSecurityIdentityProvider` llama a `verifier.authorize`, carga la licencia
  verificada y abre el secreto sellado mediante `enrollment`.
- `BCSecuritySyncAuthProvider` usa `SyncRequest`, `issue_credential`,
  `SyncCredential`, `verify_credential` y `NonceLedger` de Seguridad.
- `VerifiedRemoteLicenseProvider` es el puerto de Gestión Central para resolver
  una licencia remota cuya firma, vigencia y revocación ya validó Seguridad.

El import de `modulos.seguridad` es diferido: permite revisar el contrato sobre
la rama de Sync hoy y falla cerrado con un mensaje explícito hasta que Seguridad
sea promovida. El harness temporal está exclusivamente en tests.

## Flujo

Antes de publicar, Sync pide identidad vigente. Antes de cada reintento vuelve a
pedirla, por lo que una renovación o rotación firma el outbox existente sin
reescribir el evento. El receptor verifica credencial y licencia antes de tocar
el inbox. Toda la metadata del evento (`installation_id`, `branch_id`,
`event_id`, timestamps, nonce y versiones) queda dentro del cuerpo o credencial
firmados. Después se aplican las claves idempotentes de Sync.

Los rechazos se registran como fallos de envío/recepción con motivo sanitario;
nunca se serializan secretos, claves privadas ni contenido de licencia sellado.

## Composición pendiente

Después de promover Seguridad y Sync se debe ejecutar un merge de integración,
construir el `VerificationContext` real de cada sede e implementar en Gestión
Central `VerifiedRemoteLicenseProvider` usando su registro autorizado de
licencias/revocaciones. Hasta entonces no hay despliegue productivo.
