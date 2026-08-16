# Build Evidence — FASE A

## Precondiciones verificadas antes de construir

| Item | Valor |
|---|---|
| Rama | `release/bc-caja-rc18-rc20-integration-001` |
| HEAD | `b34ada155fd0ac0129a01998f48aa88c8be98e01` |
| Worktree | limpio |
| local == origin | `0/0` |
| Mission Leases | 0 |
| Build script | `pilot/build_pilot.ps1`, canónico vigente |
| PyInstaller | 6.21.0 |

## Corrección necesaria antes de construir

El script cableaba `BC-CAJA-1.0.0-rc.17-win64.zip` y copiaba
`package_docs/VERSION.txt` con `1.0.0-rc.17`. Construir tal cual habría
producido un paquete **mal etiquetado**: contenido RC18–RC20 rotulado RC17.

- `VERSION.txt` e `INSTALACION.txt` pasan a `1.0.0-rc.20`, con la misión de
  integración, el detalle de lo que integra y el rango de migraciones.
- El nombre del ZIP se **deriva** de `VERSION.txt` en vez de estar cableado,
  para que el error no se repita en el próximo release.
- El script emite `BC_CAJA_BUILD_OK version=... zip=...`.

## Resultado del build

```
Build complete! dist/BC-Caja
BC_CAJA_BUILD_OK version=1.0.0-rc.20 zip=releases/BC-CAJA-1.0.0-rc.20-win64.zip
```

Incidencia no bloqueante: la primera compresión falló porque
`_internal/base_library.zip` estaba tomado por otro proceso justo tras la
compilación. El EXE ya estaba construido; el reintento del empaquetado
completó sin cambios en el contenido.

| Artifact | Valor |
|---|---|
| EXE | `dist/BC-Caja/BC-Caja.exe`, 8.453.273 bytes |
| SHA256 EXE | `0594E0A6E5C5A7B87229C5B65368A7BCAF908B3FB7D96E3AA6D7FDA125EE4216` |
| ZIP | `releases/BC-CAJA-1.0.0-rc.20-win64.zip`, 34.042.682 bytes |
| SHA256 ZIP | `C3B6F646E6D035F9FCA6ACA5332B0922BD5CCA279ED942CB47038E3DC16DB577` |
| VERSION.txt en el paquete | `BC Caja 1.0.0-rc.20` |

El ZIP se conserva localmente y no se exporta al remoto, siguiendo la
convención vigente desde RC12 para binarios de release.

## Smoke no destructivo del ejecutable construido

Se ejecutó el **EXE congelado**, no el código fuente, contra una copia de la
base real obtenida con la API de backup de SQLite. El archivo productivo nunca
se abrió en escritura.

```
EXE arrancó y siguió vivo: True
migraciones tras arranque: 001..017 (total 17)
integrity_check: ok
tablas creadas: laboratories, pilar_shipments, tracked_work_contacts,
                tracked_work_transitions, tracked_works
datos existentes accesibles: cash_days=6 cash_entries=8 orders=2 mail_outbox=1
migraciones empaquetadas en el bundle: 17 (incluye 016 y 017)
PROD INTACTA: 270336 bytes
```

Contraste contra producción, para sostener el "cero cierres, cero correos":

```
PROD      cash_days=6  CLOSED=2  mail_outbox=1  SENT=1  migraciones 001..015
SANDBOX   cash_days=6  CLOSED=2  mail_outbox=1  PENDING=0  migraciones 001..017
```

Mismos cierres, mismo outbox, ningún correo nuevo, ningún cierre nuevo.

### Alcance real de esta evidencia

Que RC18, RC19 y RC20 estén disponibles en el binario queda sostenido de forma
**indirecta pero verificable**: `sqlite_repository` importa `domain.tracking` a
nivel de módulo y la construcción de la ventana arma la pestaña Seguimiento
llamando a `controller.tracking.board()`. Si cualquiera de esos módulos
faltara en el bundle, el arranque fallaría; el ejecutable arrancó, sostuvo la
UI y creó las tablas 016/017.

No se condujo la GUI del ejecutable congelado: las sondas de RC18/RC19/RC20
operan sobre el código fuente, y sus seis corridas están en verde sobre este
mismo commit. La verificación interactiva del binario corresponde al
post-install.

## Estado

Build **PASS**. Producción no tocada. RC17 sigue instalada.
