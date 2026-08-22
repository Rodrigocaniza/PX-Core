# BC SEGURIDAD V1 — resumen

**Rama:** `feature/bc-security-installation-binding-v1-001`
**HEAD de código y paquete verificado:** `40749f9e968071df0a9e72399444310ab73cd3b7` (`origin` idéntico, `0/0`, worktree limpio antes del cierre documental)
**Base:** `origin/feature/bc-optica-comision-composturas-v1-021 @ 38ef01b`
**Suite:** 1549 verdes, **0 rojas** (1369 verdes y 3 rojas antes de empezar; 1541 al congelar el paquete, +8 del cierre preinstalacion)
**Paquete:** `BC-CAJA-1.0.0-rc.33-win64.zip`, verificado con `SMOKE_PAQUETE_OK pasos=31`

**PC-B fisica, ZIP limpio:** arranco hasta login y `CONFIGURACION INICIAL SEGURA`, sin crear credenciales. Es el comportamiento correcto de una instalacion sin enrolar y **no** constituye la prueba de clonacion. La evidencia esta en `EVIDENCIA_PC_B_LIMPIA.md`.

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
3. **Los datos estan cifrados.** 19 columnas con la identidad del paciente
   —nombre, telefono, cedula, receta, observaciones— guardan criptograma en la
   misma columna TEXT. Abrir el `.sqlite3` robado con cualquier visor muestra
   `bcx1:...` donde antes decia el nombre. Y la planilla de cierre, que llevaba
   todo eso en un PDF al lado de la base, ahora se sella con la misma clave.
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
| `tools/bc_security.py` | lo que se corre en la Optica, empaquetado como `BC-Seguridad.exe`: enrolar, licencia, verificar, proteger, revertir, recuperar, abrir-informe, auditoria |
| `tools/bc_security_issuer.py` | lo que se corre en la maquina de administracion. La clave privada no entra al repositorio |
| `tests/seguridad/` | 177 pruebas: A a L, contratos, DPAPI real, escaneo de canarios, verificacion del paquete y fallo inyectado al enrolar y al proteger |
| `docs/adr/` | siete decisiones, cada una con lo que se pierde al tomarla |
| `docs/INSTALACION_SEGURIDAD_EN_LA_OPTICA.md` | los pasos del lunes, con los ejecutables del paquete |
| `tools/smoke_paquete_seguridad.py` | la ceremonia entera contra los `.exe`, repetible |

De lo que ya existia se toco poco y con motivo: `bc_caja.py` (la puerta antes
de abrir la ventana y un diagnostico), `sqlite_repository.py` (la conexion
protegida y una busqueda), `factufacil.py` (un filtro), `admin_ops.py` (sellar
la planilla y abrirla para el correo), `pilot/build_pilot.ps1` (empaquetar el
almacen de confianza y la herramienta, y verificar el paquete), `CajaDiaria.py`
(una linea: la version del paquete) y `requirements.txt`.

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

Los ocho de esa ronda estan en `FINDINGS.json` con su correccion y su prueba.
Los nueve de la segunda, tambien.

---

## Lo que no se puede afirmar desde Casa

* **Que el blob DPAPI no abra en otra PC.** No hay una segunda computadora. La
  suite lo ejerce con un sellador simulado, declarado como simulacion, y hay
  pruebas contra el DPAPI real de esta Windows para que la simulacion no sea la
  unica evidencia. La verificacion real es el paso 8 del instructivo.
* **Nada sobre la base productiva.** Vive solo en la Optica y ningun comando de
  esta sesion la abrio.

*(En la primera ronda esta lista tenia un tercer punto —"que el ejecutable
empaquetado arranque"— que ya no aplica: se construyo y se verifico. Ver la
seccion "Segunda ronda".)*

---

## Lo que si se verifico contra el camino real

Con DPAPI real, la clave de emisor real, el almacen de confianza commiteado y
la huella real de esta maquina: se enrolo, se emitio, se instalo, `verificar`
dio `ALLOW / OK`, se guardo una venta por el repositorio de produccion, BC la
leyo entera, SQLite pelado mostro `bcx1:...`, y buscar los cinco literales del
paciente en los bytes del archivo dio `ninguna`.


---

## Segunda ronda: el paquete

La primera ronda dejo la capa escrita y probada **desde Python**. La segunda la
puso a prueba **como se va a usar**, y ahi aparecio lo que ninguna prueba de
unidad podia ver.

**El paquete congelado no llevaba el almacen de confianza.** PyInstaller termino
sin un error, el EXE arrancaba, y `trusted_issuers.json` no estaba adentro
porque no es codigo. Un BC congelado sin almacen no verifica **ninguna**
licencia: toda instalacion enrolada queda en DENY. La secuencia real habria sido
instalar, enrolar, cifrar la base —irreversible sin la frase— y recien ahi
descubrir que BC no abre.

**La Optica no tiene Python**, y el instructivo mandaba correr
`python tools/bc_security.py`. Ahora el paquete trae su propia herramienta de
consola, `Seguridad\BC-Seguridad.exe`.

**La planilla de cierre guardaba al paciente en claro** en la misma carpeta que
la base cifrada. Ahora se sella con la misma DEK.

Y el mas incomodo: **mi propia prueba de canarios no plantaba tres de los cinco
valores** que decia estar buscando, porque usaba las claves equivocadas del
formulario legacy. Pasaba en verde por vacio. Ahora verifica que planto lo que
quiso plantar antes de escanear nada, y hay un caso que planta un canario a mano
para comprobar que el buscador funciona.

Los nueve defectos de esta ronda estan en `CIERRE_PREINSTALACION.md` con su
correccion y su prueba.

**Lo que ahora se puede afirmar:** la ceremonia entera —arranque, enrolamiento,
emision, instalacion, proteccion, escritura y lectura protegida, base robada,
planilla sellada, reinicio, lease, licencia manipulada, archivos corruptos y
rollback— corre contra los `.exe` y da `SMOKE_PAQUETE_OK pasos=31`.

**Lo que sigue sin poder afirmarse:** que el blob sellado con DPAPI no abra en
otra PC. No hay una segunda computadora. Es la unica afirmacion del slice que no
se pudo comprobar aca, y es el paso 8 del instructivo, con la Optica mirando.
