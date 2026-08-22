# ADR-0006 — Lease con gracia: la Optica no se queda sin Caja por Internet

Estado: aceptado — BC-SECURITY-INSTALLATION-BINDING-V1-001

## Contexto

La mision es explicita en las dos direcciones: la autorizacion tiene que poder
caducar, y "no introducir una dependencia absurda que deje la optica sin Caja
por una caida breve de Internet".

Ademas, hoy no existe todavia un servicio de emisor en linea: Gestion Central
esta en construccion. Un diseno que exija renovar contra un servidor cada 30
dias seria un diseno que no se puede operar.

## Decision

Tres plazos, en este orden:

| Situacion | Resultado | Que ve quien opera |
|---|---|---|
| dentro del lease | `ALLOW` | nada |
| lease vencido, dentro de la gracia | `ALLOW_GRACE` | aviso visible al abrir |
| pasada la gracia | `DENY` | mensaje, y **la base intacta** |

`lease_days` y `grace_days` los fija el emisor **por licencia**. Para la
instalacion de la Optica se emiten largos, de modo que la ausencia de un
servidor no pueda cerrar la Caja; renovarlos es dejar caer un archivo firmado.

Contra el reloj: se guarda la marca de agua del instante mas alto que se vio, y
todas las cuentas se hacen contra `max(ahora, marca_de_agua)`. Atrasar el reloj
no devuelve tiempo de lease; el retroceso mayor a 15 minutos queda auditado
como `RELOJ_ATRASADO`.

El estado se guarda **en dos lugares** —la tabla `security_state` de la base y
un archivo sellado con MAC— y se toma el mas avanzado de los dos. Borrar el
archivo no resetea el lease porque esta en la base; restaurar una base vieja no
lo resetea porque esta en el archivo.

## Consecuencias

* Un lease editado a mano no verifica su MAC: se descarta y se arranca uno
  nuevo desde ahora. Se pierde el tiempo ya transcurrido, no se gana nada.
* `DENY` por lease vencido **no toca la base**. Es lo unico que hace que el
  rollback siga siendo posible despues de un DENY, y esta probado.
* La revocacion, una vez conocida, se persiste en el estado del lease. Borrar
  `revocations.bcrl` no desrevoca.
