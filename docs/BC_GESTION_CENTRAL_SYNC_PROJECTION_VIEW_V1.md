# BC Gestión Central — Vista de proyecciones Sync V1

Continúa el punto 7 de la integración pendiente del receptor: diseñar pantallas
que consuman las proyecciones sin escribir en las sedes. Se apila sobre
`feature/bc-gestion-central-sync-receiver-v1-001`; PR #14/#15/#16 y sus HEAD
auditados quedan intactos.

## Frontera de lectura

`SyncProjectionView` abre la base del receptor con `mode=ro`. Si el motor no
puede tomar el índice WAL en ese modo, degrada a una conexión con
`PRAGMA query_only=ON`: ambos caminos rechazan `INSERT`, `UPDATE` y `DELETE`, y
una prueba lo comprueba sobre la conexión real. Los módulos no contienen ninguna
sentencia de escritura ni de esquema; el receptor sigue siendo el único autor.

Si todavía no existe base de recepción, la vista responde vacío y **no** crea el
archivo: abrir la pantalla nunca inicializa almacenamiento.

## Autorización y alcance

`dashboard.read` habilita proyecciones y totales; `audit.read` habilita el
detalle de rechazos y duplicados. Un principal atado a una unidad sólo ve su
propia sucursal, tanto en filas como en totales y auditoría. El branch se traduce
a `Unit` con el catálogo canónico ya existente; un branch fuera del catálogo se
muestra como no catalogado en lugar de ocultar el hecho.

## Lo que muestra

Orden estable por `occurred_at`/`event_id`, igual que el receptor. Categorías
cliente/historial, venta, sobre, receta, evento y FactuFácil, con estado de
factura y estado Sync. Filtros por categoría, sucursal, estado FactuFácil y texto
libre sobre cliente, documento, sobre, venta, factura o `event_id`.

El panel lateral lista intentos `REJECTED` y `DUPLICATE` con el motivo ya
saneado por el receptor; no expone credenciales, firmas ni cuerpos.

## Fuera de alcance

No hay servicio, endpoint, red, credencial ni despliegue: la pantalla lee un
archivo local. Los puntos 1–6 de la integración física siguen pendientes y son
decisión humana; nada aquí los adelanta ni los da por hechos.
