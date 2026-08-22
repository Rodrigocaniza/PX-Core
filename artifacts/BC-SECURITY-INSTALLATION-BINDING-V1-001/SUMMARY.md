# BC SEGURIDAD V1 — resumen

**Rama:** `feature/bc-security-installation-binding-v1-001`
**Base:** `origin/feature/bc-optica-comision-composturas-v1-021 @ 38ef01b`
**Suite:** 1519 verdes, 1 roja preexistente (1369/3 antes de empezar)

---

## La propiedad que se pedia

> Copiar la carpeta, el EXE, `%LOCALAPPDATA%\BC`, la base o un ZIP entero a
> otra PC no debe dar una copia funcional ni legible.

Como se consigue, en cuatro capas independientes. Que sean independientes es el
punto: romper una no alcanza.

1. **El secreto no viaja.** Windows sella el secreto de instalacion con DPAPI.
   La clave maestra no esta en los archivos, asi que en otra computadora el
   sistema operativo simplemente se niega a abrirlo. No hay contrasena que
   adivinar ni archivo que copiar de mas.
2. **La licencia nombra la maquina.** Un documento firmado con Ed25519 dice
   que instalacion y que huella de PC estan autorizadas. Editar un byte —el
   negocio, la sucursal, el plazo, la huella— rompe la firma. Firmarse una
   propia no sirve: la clave privada no esta en el cliente y el cliente no
   acepta claves de confianza nuevas desde el disco.
3. **Los datos estan cifrados.** 18 columnas con la identidad del paciente
   —nombre, telefono, cedula, receta, observaciones— guardan criptograma en la
   misma columna TEXT. Abrir el `.sqlite3` robado con cualquier visor muestra
   `bcx1:...` donde antes decia el nombre.
4. **Cada intento queda escrito.** La bitacora de seguridad es append-only por
   disparador y guarda el motivo con nombre propio: `MAQUINA_DISTINTA`,
   `LICENCIA_DE_OTRA_INSTALACION`, `REVOCADA`, `RELOJ_ATRASADO`.

---

## Lo que se decidio y no se hizo como estaba pedido

**No se partio de `origin/main`.** La mision lo pedia; hacerlo habria producido
una capa de seguridad que no conoce la mitad de las tablas que tiene que
proteger. `git merge-base --is-ancestor origin/main <punta>` devuelve distinto
de cero: main quedo en rc.31 y la cadena de la Optica lleva rc.33 con Commercial
Core, FactuFacil, usuarios y roles, trabajos operativos y comisiones. Se partio
de la punta real, verificada recorriendo las 22 ramas de la cadena.

Esto es una decision tomada sin consultar, y esta declarada en tres lugares
—aca, en `MANIFEST.json` y en `ARTIFACT_CONSISTENCY.md`— justamente para que se
pueda revisar.

---

## Lo que se agrego

| | |
|---|---|
| `modulos/seguridad/` | 22 archivos, la capa transversal. No importa Caja, Comercial ni Gestion Central — hay una prueba que lo verifica |
| `migrations/033_security_v1.sql` | tres tablas nuevas, estrictamente aditiva. Aplicarla no cifra nada |
| `tools/bc_security.py` | lo que se corre en la Optica: enrolar, licencia, verificar, proteger, revertir, recuperar, auditoria |
| `tools/bc_security_issuer.py` | lo que se corre en la maquina de administracion. La clave privada no entra al repositorio |
| `tests/seguridad/` | 148 pruebas, incluidas las A a L y las de contrato |
| `docs/adr/` | seis decisiones, cada una con lo que se pierde al tomarla |
| `docs/INSTALACION_SEGURIDAD_EN_LA_OPTICA.md` | los ocho pasos del lunes |

Lo que se toco de lo que ya existia son 85 lineas en cuatro archivos:
`bc_caja.py` (la puerta antes de abrir la ventana), `sqlite_repository.py` (la
conexion protegida y una busqueda), `factufacil.py` (un filtro) y
`requirements.txt`.

---

## Lo que se rompio y se arreglo antes de commitear

Cuatro defectos graves, todos de la misma forma: **la proteccion parecia
funcionar y no protegia.**

* La bitacora de revisiones guardaba la venta entera en claro. Cifrar las
  columnas era teatro mientras el snapshot estuviera ahi. Lo destapo la prueba
  que busca al paciente en los **bytes crudos** del archivo, no en las columnas
  — las columnas ya daban verde.
* Desactivar una fila del llavero apagaba el cifrado: BC habria abierto
  mostrando criptograma y guardando lo nuevo en claro al lado de lo viejo.
* Copiar solo el `.sqlite3` a una PC sin enrolar producia exactamente lo mismo.
* Un `INSERT` con una funcion adentro no coincidia con el patron del mapeo, y
  no coincidir significaba escribir en claro sin decir una palabra.

Los ocho estan en `FINDINGS.json` con su correccion y su prueba.

---

## Lo que no se puede afirmar desde Casa

* **Que el blob DPAPI no abra en otra PC.** No hay una segunda computadora. La
  suite lo ejerce con un sellador simulado, declarado como simulacion, y hay
  pruebas contra el DPAPI real de esta Windows para que la simulacion no sea la
  unica evidencia. La verificacion real es el paso 7 del instructivo.
* **Que el ejecutable empaquetado arranque.** No se corrio PyInstaller.
* **Nada sobre la base productiva.** Vive solo en la Optica y ningun comando de
  esta sesion la abrio.

---

## Lo que si se verifico contra el camino real

Con DPAPI real, la clave de emisor real, el almacen de confianza commiteado y
la huella real de esta maquina: se enrolo, se emitio, se instalo, `verificar`
dio `ALLOW / OK`, se guardo una venta por el repositorio de produccion, BC la
leyo entera, SQLite pelado mostro `bcx1:...`, y buscar los cinco literales del
paciente en los bytes del archivo dio `ninguna`.
