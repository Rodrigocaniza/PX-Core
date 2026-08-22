# BC-OPTICA-FACTUFACIL-EN-GESTION-CENTRAL-V1-023

**Estado:** COMPLETADA_EN_CASA · sólo código · no requiere migración · no requiere la PC de la Óptica

Esta misión cierra el `F1` que dejó abierto `BC-OPTICA-DESPLIEGUE-PRODUCTIVO-029-032-V1-022`,
y de paso el `F2` y la mitad del `F4` que habían quedado a medio camino. Los tres eran
trabajo de código puro, que es exactamente lo que se puede terminar desde casa.

## F1 — la marca de FactuFácil ahora viaja

`import_snapshot` escribía el literal `"NO DISPONIBLE PILOTO"` en `factufacil_status`
para **todas** las ventas ([real_sync.py:167](../../modulos/gestion_central/real_sync.py)).
Era de cuando la 029 todavía no existía. En el canary de la misión 022 la venta del
sobre 9001 estaba CARGADA en Caja y llegó a Gestión Central como NO DISPONIBLE PILOTO:
el campo tenía texto y el dato no viajaba. Era el único de los trece datos exigidos
que no se pudo demostrar.

Ahora la marca se lee de `factufacil_loads`, que es donde la 029 la guarda, y se
respeta la misma política que está escrita en `029_factufacil_caja.sql`. Gestión
Central no importa el módulo de Caja: lee el snapshot como el archivo ajeno y de
sólo lectura que es. Lo único que agrega es distinguir los dos casos en que la
pregunta no tiene sentido.

| Lo que se ve | Cuándo |
| --- | --- |
| `PARA CARGAR` | es una venta y nadie la marcó |
| `CARGADA` | alguien la cargó, sobre la revisión que la venta sigue teniendo |
| `CARGADA (VENTA EDITADA)` | se cargó, y después la venta cambió en Caja: lo que está allá ya no coincide |
| `NO APLICA` | un gasto o una entrega a administración: no hay nada que facturar |
| `NO DISPONIBLE` | el snapshot viene de una Caja anterior a la 029 y no tiene dónde guardar la marca |

`NO DISPONIBLE` es deliberado y no un descuido: no tener dónde guardar la marca no
es lo mismo que no tenerla, y decir «PARA CARGAR» ahí sería afirmar algo que el
archivo no dice.

`factufacil_status` ya estaba en `REVIEW_FIELDS`, así que la corrección hereda
gratis lo que Gestión Central ya sabía hacer: si la marca cambia entre dos
importaciones, el campo revisado se invalida y la venta pasa a
`CORRECTED_PENDING_REVALIDATION`. Está probado, no supuesto.

## F2 — una migración es una, no la cola entera

`tools/factufacil_migracion_029_optica.py` y `tools/usuarios_migracion_030_optica.py`
aplicaban su migración construyendo `SQLiteCashDayRepository`, que corre **todas**
las pendientes. Se escribieron cuando su migración era la punta de la cola. Corrida
el 2026-08-20 sobre una copia en 028, la herramienta de la 029 llevó la base hasta
032 de una vez, y sus propios post-checks lo denunciaron (`migraciones 28 -> 32`).

Las dos ahora aplican por `aplicar_una(base, version)`, extraída de
`tools/aplicar_migracion_optica.py` —la genérica que sí se usó para el apply
productivo—. Ejecuta exactamente el archivo pedido, exige la cadena previa completa
y se niega en voz alta en vez de seguir sola. El chequeo de idempotencia, que era
el que construía el repositorio y por eso fallaba, ahora afirma lo que quería decir
desde el principio: volver a correrla no reaplica nada.

Verificado end-to-end sobre una base desechable construida en 028:

```
029:  migraciones: 28 -> 29   ·  no aparecio ninguna otra tabla  ·  volver a correrlo no reaplica
030:  migraciones: 29 -> 30   ·  exactamente cuatro columnas nuevas
```

## F4 — el valor de respaldo se había quedado atrás

La misión 022 subió `pilot/package_docs/VERSION.txt` a `1.0.0-rc.33`, pero
`CajaDiaria.VERSION_APLICACION` se quedó en `1.0.0-rc.32`. La prueba que existe
justamente para eso —`test_el_valor_de_respaldo_sigue_al_paquete`— quedó en rojo en
el commit canónico `38ef01b`. Un binario que no encuentre el `VERSION.txt`
empaquetado se habría autodeclarado rc.32 siendo rc.33. Corregido: el código dice
lo mismo que el paquete, y lo mismo que el binario instalado en la Óptica.

## Lo que esta misión no toca

Ni una migración, ni un importe, ni un dato productivo. No se abrió la base de la
Óptica, no se construyó binario y no se pisó nada de Seguridad BC. La marca de
FactuFácil se **lee**: Gestión Central sigue sin poder escribir en el snapshot, que
se abre en `mode=ro` con `PRAGMA query_only=ON` y cuyo sha256 se compara antes y
después de leerlo.
