# ADR-0005 — Proteccion por columna, con el ambito atado a (base, tabla, columna)

Estado: aceptado — BC-SECURITY-INSTALLATION-BINDING-V1-001

## Contexto

Habia que volver ilegible el dato del paciente en una base robada, sin cambiar
el esquema, sin romper 1365 pruebas existentes y sin reescribir 1800 lineas de
SQL a mano.

Se evaluaron tres caminos:

1. **Cifrar el archivo entero** (SQLCipher o equivalente). Descartado: agrega
   una extension nativa de SQLite al paquete, cambia el formato del archivo
   —con lo cual todo respaldo, toda herramienta de `tools/` y todo dry-run de la
   Optica dejan de abrirlo— y no protege nada cuando BC esta abierto.
2. **Cifrar en cada llamada del repositorio.** Correcto y explicito, pero son
   decenas de sitios y alcanza con olvidarse en uno para filtrar en claro.
3. **Cifrar en la conexion.** Elegido.

## Decision

Cada valor protegido se guarda como `bcx1:<base64url(nonce||ct||tag)>` en la
misma columna TEXT. La proteccion entra por `ProtectedConnection`:

* **Lectura**: un `row_factory` encadenado descifra cualquier valor con el
  prefijo, venga de donde venga. Es agnostico de tabla, de columna y de alias:
  por construccion no se puede olvidar de descifrar un lugar.
* **Escritura**: un registro explicito de columnas, y un mapeo de los `?` de
  cada INSERT y UPDATE contra ese registro. **Lo que el mapeo no entiende y
  toca una tabla protegida, levanta error** en vez de pasar en claro.

El dato asociado del AEAD ata el criptograma a `(dek_id, tabla, columna)`.

## Lo que este diseno NO protege, y por que

* **La fila.** Dos valores de la misma columna son intercambiables a nivel
  criptografico. Atar la fila obligaria a conocer la clave primaria en cada
  UPDATE, y quien puede reordenar filas de un SQLite ya puede reordenarlas sin
  tocar el cifrado. El costo no compraba nada.
* **`suppliers`.** Queda afuera en V1 y es una decision, no un olvido:
  `idx_suppliers_documento_unico` es un UNIQUE sobre `document`, y con un nonce
  por valor dos proveedores con el mismo RUC dejarian de colisionar. Protegerla
  pide un indice ciego con clave, que es otro slice.
* **`Datos/movimientos.txt`.** El exportador legacy escribe texto plano fuera
  de la base. No se toco en este slice. Queda declarado como riesgo residual.

## Consecuencias

* Dos consultas tuvieron que mover su filtro de texto a Python:
  `search_untracked_orders` y el filtro por cliente de FactuFacil. Un LIKE
  contra criptograma no da error: da cero filas, en silencio, para siempre.
  Hay una prueba estatica que recorre todo `modulos/` buscando ese patron.
* `cash_entry_revisions.snapshot_json` entro al registro. Guarda la venta
  entera como JSON; sin el, proteger `cash_entries` habria sido teatro. Lo
  destapo la prueba que busca el nombre del paciente en los bytes crudos.
* La cadena vacia **no** se cifra: varias tablas tienen
  `CHECK(length(trim(columna)) > 0)` y cifrar `''` habria cambiado el negocio.
