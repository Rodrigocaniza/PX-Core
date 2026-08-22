# BC Historial

Estado: aplicación de consulta separada visualmente de BC Caja, conectada a
la base canónica de Caja y estrictamente de solo lectura.

## Cliente global multisucursal

Historial trata al cliente como persona del negocio. `GlobalHistoryService`
puede federar una o varias fuentes canónicas ya autorizadas: hoy la base local
puede contener hechos de Asunción y Pilar; mañana BC Sync podrá entregar una
fuente autenticada por instalación con los hechos sincronizados. La UI y las
reglas de identidad no dependen del transporte.

Cada evento conserva `branch`, fecha, tipo y sobre. La cronología reúne ambas
sucursales y se ordena de más reciente a más antiguo.

### Identidad

- CI/RUC normalizado y exacto es identidad fuerte y permite unir hechos de
  distintas sucursales.
- Nombre y teléfono sirven para buscar, no para fusionar automáticamente.
- Si una búsqueda débil devuelve más de un registro, la UI no construye una
  ficha mezclada: pide refinar con CI/RUC. No hay merge ni escritura oculta.
- La futura resolución manual/auditable de identidades pertenece al servicio
  canónico de personas; Historial no crea una tabla propia para resolverla.

### Permisos

`HistoryPrincipal` representa claims que entrega una sesión autenticada de BC;
no valida contraseñas ni guarda credenciales. Caja revalida su `CashSession`
con `require_operator` inmediatamente antes de abrir la ventana y la entrega
en memoria. La CLI falla cerrada: no acepta sujeto, rol o permisos libres.
La apertura exige además un verificador de token: Caja entrega su
`require_operator`; BC Seguridad podrá entregar el verificador de su installation
binding. Historial consume ese contrato y no crea ni duplica el binding.

- Operadora: consulta y opera únicamente su sucursal verificada, incluso si
  recibe por error un claim global.
- Admin/Dirección: consulta ambas sucursales y puede operarlas según su rol.
- Visor federado: consulta ambas sucursales, pero `can_modify_branch` siempre
  rechaza escritura, aun ante un claim de escritura accidental.
- Roles desconocidos, operadora sin sucursal y búsquedas vacías fallan cerrados.
- Hechos sin sucursal se descartan para todos los roles. Para operadora, el
  filtro local baja al lector SQLite antes del `LIMIT`; datos ajenos no se
  materializan ni desplazan coincidencias locales.
- Historial no ofrece comandos de escritura, aun cuando el principal sea Admin.

La proyección operativa contiene cliente, contacto, ventas, pagos, cristales,
profesional de receta, observaciones y trazabilidad relevante. No consulta ni
expone costo, margen, comisiones, cierres, configuración, credenciales ni la
auditoría administrativa completa.

## Uso

El botón **Ver historial** de **CLIENTE Y COMPROBANTE** abre una ventana
independiente usando la sesión ya revalidada y prefiltra CI/RUC y nombre. La ventana también permite buscar por nombre,
teléfono y número de sobre/trabajo. Los movimientos se muestran del más
reciente al más antiguo.

La ficha consolida, cuando existen en el estado real:

- ventas, fecha, sucursal, sobre, vendedora y estado;
- total, efectivo, tarjeta/cheque, convenio y saldo;
- ítems, cristales, laboratorio y profesional de la receta;
- composturas/trabajos operativos;
- observaciones, anulaciones y revisiones con su trazabilidad.

## Fuente de verdad y seguridad

`SQLiteHistoryReader` abre `bc_caja.sqlite3` con URI `mode=ro` y activa
`PRAGMA query_only`. No construye `SQLiteCashDayRepository`, porque ese
repositorio ejecuta migraciones al inicializarse. Historial no crea tablas,
índices, archivos, migraciones ni copias de datos.

La ruta se resuelve con el mismo `BC_CAJA_DATA_DIR` que Caja. La capa queda
separada así:

```
bc_historial.py                              UI y argumentos
modulos/historial_externo/history.py        contrato/modelos de consulta
modulos/historial_externo/global_history.py identidad, federación y permisos
modulos/historial_externo/sqlite_reader.py  adaptador canónico read-only
modulos/historial_externo/launcher.py       compatibilidad V1 externa heredada
```

Seguridad puede reemplazar el adaptador (credenciales, DB o sincronización)
sin reescribir la UI ni el punto de lanzamiento.

## Lanzamiento

El flujo global no se abre directamente por CLI: ese entrypoint falla cerrado
porque no puede verificar una sesión de Caja. Se abre desde Caja, que entrega
la sesión revalidada en memoria y puede prefiltrar CI/RUC y nombre.

El launcher externo heredado conserva únicamente compatibilidad V1. El flujo
global nuevo no confía en esa CLI: abre la ventana en el proceso de
Caja con su sesión revalidada. El launcher queda como compatibilidad V1 y no
otorga por sí mismo el permiso global.

## Alcance deliberado

- No modifica datos ni incorpora una base paralela.
- No hardcodea personas o vendedoras.
- No infiere recetas clínicas: el esquema canónico actual expone el profesional
  asociado, pero no graduación estructurada completa. Si esa estructura se
  incorpora canónicamente, el contrato permite mostrarla sin base paralela.
- La coincidencia usa los campos canónicos presentes. Una futura identidad
  maestra podrá implementarse detrás del contrato `HistoryReader`.

Las garantías están cubiertas por
`tests/caja_diaria/test_historial_externo.py` y
`tests/caja_diaria/test_historial_reader.py`, más la aceptación multisucursal
A–K en `tests/caja_diaria/test_historial_multisucursal.py`.
