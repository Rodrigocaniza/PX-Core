# BC Historial

Estado: aplicación de consulta separada visualmente de BC Caja, conectada a
la base canónica de Caja y estrictamente de solo lectura.

## Uso

El botón **Ver historial** de **CLIENTE Y COMPROBANTE** abre otro proceso y
prefiltra CI/RUC y nombre. La ventana también permite buscar por nombre,
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
modulos/historial_externo/sqlite_reader.py  adaptador canónico read-only
modulos/historial_externo/launcher.py       proceso separado desde Caja
```

Seguridad puede reemplazar el adaptador (credenciales, DB o sincronización)
sin reescribir la UI ni el punto de lanzamiento.

## Lanzamiento

El launcher mantiene compatibilidad con la instalación dedicada indicada por
`BC_HISTORIAL_EXE` o por la ruta histórica. Si no existe, utiliza el
`bc_historial.py` incluido en PX-Core:

```
python bc_historial.py --ci 1203712 --name "Fernando González"
python bc_historial.py --ruc 1203712-5
python bc_historial.py --phone 0981 --envelope S-102
```

Caja usa `subprocess.Popen`; no espera el cierre de Historial y no guarda ni
modifica el formulario al abrirlo. Si ningún launcher está disponible, muestra
un mensaje legible y Caja continúa funcionando.

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
`tests/caja_diaria/test_historial_reader.py`.
