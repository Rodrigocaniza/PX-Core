# ADR-0007 — La planilla de cierre se sella; `movimientos.txt` no hacia falta sellarlo

Estado: aceptado — BC-SECURITY-INSTALLATION-BINDING-V1-001

## Contexto

Cifrar la base y dejar al lado una carpeta con la misma informacion en PDF no
protege a nadie. Quien copia `%LOCALAPPDATA%\BC\Caja` se lleva lo mismo, en un
formato mas comodo de leer que el SQLite.

Se auditaron **todos** los archivos que BC Caja deja en disco:

| Archivo | Contenido | PII |
|---|---|---|
| `bc_caja.sqlite3` (+ `-wal`, `-shm`) | la base | ya protegida por columna |
| `Backups/bc-caja-*.sqlite3` | copias hechas con `sqlite3.backup` | heredan el cifrado de la base |
| `Reports/cierre-*.pdf` | planilla diaria de sobres | **si, en claro** |
| `movimientos.txt` | puente al sistema legacy de Gestion | **no** |
| `Logs/startup-error.log` | traceback de arranque | no lleva valores |
| credencial SMTP | ya sellada con DPAPI desde RC.13 | no es PII |

## Decision

**`Reports/cierre-*.pdf` se sella** con la misma DEK, el mismo AES-256-GCM y el
mismo `FieldCipher` que las columnas. No hay un segundo sistema criptografico:
lo unico propio de `file_protection.py` es un encabezado `BCX1FILE\n` que
permite reconocer un archivo sellado, y un dato asociado que ata el criptograma
a su nombre de archivo.

**El nombre no cambia.** `cierre-abc.pdf` se sigue llamando asi. Cambiarlo
habria roto las filas de `mail_outbox` que ya apuntan a esa ruta, convirtiendo
una mejora de seguridad en una migracion de datos.

**`movimientos.txt` se deja como esta**, y se agrega una prueba que fija su
forma.

## Por que `movimientos.txt` no se toca

Publica una linea por concepto y por dia:

```
Ingreso|04-03-2026|Externo|PC|250000|Si|BC_CAJA:<dia>:VENTAS
```

Tipo, fecha, origen, destino, importe, conciliado y un marcador de
idempotencia. No hay nombre, ni telefono, ni documento, ni receta, ni
observacion: hay plata agregada del dia. Cifrarlo habria roto el puente con
Gestion —que lo lee como texto— para no proteger ningun dato personal.

Lo que si se agrego es una prueba que verifica la forma linea por linea y que
el exportador ni siquiera nombra las columnas del paciente. Existe para que el
dia que alguien quiera agregarle "el cliente" a esa linea —que es una idea
razonable y tentadora— la prueba se ponga roja antes de llegar a produccion.

## Lo que se pierde

* **El PDF deja de abrirse con doble clic.** Se abre con
  `bc_security.py abrir-informe`, que escribe una copia legible donde se le
  pida. Es un paso mas para algo que se usa poco: el consumo habitual de la
  planilla es el correo que el cierre manda a la administradora.
* **El PDF en claro existe unos milisegundos en `%TEMP%`.** El generador de
  informes escribe a una ruta, no a un buffer, y reescribirlo para que trabaje
  en memoria habria tocado el informe y sus pruebas de contrato visual por un
  motivo que no es el suyo. Se genera en un directorio temporal propio, que se
  borra en el acto, y solo el resultado sellado llega al destino. Es la misma
  exposicion que produce abrir el PDF con cualquier visor.
* **El adjunto del correo va en claro.** Es deliberado: el informe existe para
  que la administradora lo lea. Lo que cambia es que en disco no queda una
  copia legible.

## Campos que quedan en claro a proposito

Documentado aca porque la mision pide que la excepcion sea explicita:

* **numero de sobre** — es el identificador operativo del trabajo, el que se
  canta en el mostrador y por el que se busca. No es un dato de la persona, y
  cifrarlo romperia las dos busquedas por sobre, que son SQL.
* **importes, fechas, sucursal, vendedora, estados** — son la contabilidad y la
  operacion. Cifrarlos romperia totales, filtros y reportes sin proteger a
  ninguna persona.

## Consecuencias

* `proteger-datos` sella tambien los informes que ya estan en disco, y
  `revertir-datos` los devuelve. El ida y vuelta esta probado.
* Hay una prueba de canarios que carga un dia entero con cadenas que no existen
  en ninguna otra parte del sistema, cierra la Caja por el camino real, y
  recorre **cada byte de cada archivo** bajo la raiz de datos y bajo la carpeta
  de seguridad. Incluye una prueba de que el escaneo detecta de verdad: un
  control que no puede fallar no es un control.
