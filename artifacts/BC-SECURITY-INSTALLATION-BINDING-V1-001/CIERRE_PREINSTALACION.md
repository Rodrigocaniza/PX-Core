# Cierre preinstalacion — que cambio en esta ronda

La ronda anterior dejo la capa escrita y probada **desde Python**. Esta ronda la
puso a prueba **como se va a usar**: empaquetada, en un ejecutable, con las
manos de alguien que no tiene Python instalado. Aparecieron siete defectos que
no se ven de ninguna otra forma.

---

## El que habria arruinado el lunes

El paquete congelado **no llevaba el almacen de confianza**.

PyInstaller termino sin un solo error. El EXE arrancaba. Y
`modulos/seguridad/trusted_issuers.json` no estaba adentro, porque no es codigo
y PyInstaller solo sigue imports. Un BC congelado sin almacen de confianza no
puede verificar **ninguna** licencia: `trust.load()` levanta `TrustStoreError` y
toda instalacion enrolada queda en DENY.

La secuencia real habria sido: instalar en la Optica, enrolar, proteger la base
—que es irreversible sin la frase—, y recien ahi descubrir que BC no abre.

Se encontro listando el contenido de `dist/BC-Caja/_internal`, no confiando en
que el build habia salido bien.

Ahora: el almacen se empaqueta, **el build revienta** si falta el almacen, la
migracion 033 o el binario de `cryptography`, y hay una prueba que lee el script
de build y el registro de recursos de ejecucion y exige que coincidan.

---

## El que habria trabado la instalacion

**La Optica no tiene Python**, y el instructivo mandaba correr
`python tools/bc_security.py`.

Esa PC recibe un paquete congelado. Enrolar, instalar la licencia y proteger los
datos habrian sido imposibles con lo que hay en la maquina.

Ahora el build produce un segundo ejecutable, `Seguridad\BC-Seguridad.exe`,
dentro del mismo paquete. De consola y no `--windowed`, porque su salida —el
`installation_id`, la frase de recuperacion, el veredicto— hay que poder leerla.
El emisor no se empaqueta: sigue viviendo en la maquina de administracion.

Y una cosa mas del mismo tipo: el instructivo pedia
`proteger-datos --confirmar --actor "tu nombre"`, y argparse contestaba
`unrecognized arguments: --actor`. Nadie escribe las opciones globales primero.
Ahora se aceptan en los dos lugares, y hay una prueba que **lee el instructivo**
y verifica que cada comando que aparece ahi realmente parsea.

---

## El que hacia hueca a toda la proteccion

`Reports/cierre-*.pdf` llevaba **nombre, telefono, receta y observaciones** de
cada cliente del dia, en claro, en la misma carpeta que la base cifrada, y se
acumulaba una por cierre.

Cifrar la base y dejar esa carpeta al lado no protege a nadie: quien copia
`%LOCALAPPDATA%\BC` se lleva lo mismo, en un formato mas comodo de leer que el
SQLite.

Ahora se sella con la **misma** DEK y el mismo AES-256-GCM que las columnas — no
hay un segundo sistema criptografico. El nombre del archivo no cambia, para no
romper las filas de `mail_outbox` que ya apuntan ahi. El correo del cierre sigue
llevando el PDF legible, que es para lo que existe; lo que cambia es que en
disco no queda una copia legible. `abrir-informe` devuelve el doble clic a
pedido.

Y en la misma auditoria aparecio `cash_entries.source_reference`, que guarda una
**copia** de las observaciones: el formulario legacy hace
`source_reference or notas`. Proteger `observations` y dejarla afuera era no
proteger nada.

---

## `movimientos.txt`: no era el problema

En la ronda anterior lo declare como riesgo residual **sin haberlo abierto**.
Al auditarlo resulto que publica una sola linea por concepto y por dia:

```
Ingreso|04-03-2026|Externo|PC|250000|Si|BC_CAJA:<dia>:VENTAS
```

Tipo, fecha, origen, destino, importe, conciliado y un marcador de idempotencia.
Ni un nombre, ni un telefono, ni un documento, ni una receta. Cifrarlo habria
roto el puente con Gestion —que lo lee como texto— para no proteger ningun dato
personal.

Se deja como esta, y se agrego una prueba que fija su forma linea por linea y
verifica que el exportador ni siquiera nombra las columnas del paciente. Existe
para que el dia que alguien quiera agregarle "el cliente" a esa linea —que es
una idea razonable y tentadora— la prueba se ponga roja antes de produccion.

**La leccion:** declarar un riesgo sin abrirlo es tan malo como no verlo.
Exagere en `movimientos.txt` y no habia mirado la planilla de cierre, que estaba
al lado y si era grave.

---

## El defecto que estaba en mi propia prueba

El escaneo de PII de la ronda anterior cargaba la venta con las claves
`documento`, `telefono` y `observaciones`. El formulario legacy las llama
`cliente_documento`, `cliente_telefono` y `notas`. Los tres valores se
descartaban en silencio: la prueba buscaba en el disco tres cadenas que nunca se
habian escrito, y pasaba en verde **por vacio**.

Es el modo de fallo mas peligroso que puede tener una prueba de seguridad: la
que tranquiliza sin verificar.

Ahora la prueba **lee lo que guardo** y falla si lo guardado no es lo que quiso
guardar, antes de escanear nada. Y hay un caso que planta un canario a mano para
comprobar que el buscador detecta de verdad: un control que no puede fallar no
es un control.

Al arreglarlo aparecio el canario de observacion en la base y en los respaldos —
que fue como se destapo `source_reference`.

---

## Los dos que solo aparecen al automatizar

* **Un diagnostico abria un dialogo modal.** `--security-check` con la licencia
  manipulada llegaba a DENY y abria un `messagebox`. No hay nadie para cerrarlo:
  el proceso quedaba vivo para siempre. El smoke se colgo dos veces por esto.
* **El diagnostico filtraba lo que vigilaba.** Pasaba su marca de prueba como
  clave idempotente del cierre, y esa clave se guarda en claro. El propio
  diagnostico se reportaba `filtracion=SI`, y tenia razon.

---

## Lo que ahora se puede afirmar y antes no

`SMOKE_PAQUETE_OK pasos=31`, contra los `.exe` y no contra el codigo fuente:

* el ejecutable arranca y corre la migracion 033 adentro del paquete;
* sin enrolar, BC funciona como siempre;
* DPAPI real funciona dentro del paquete congelado;
* el paquete verifica la licencia con el almacen que lleva adentro;
* `proteger-datos` deja la base sin nada en claro y sella las planillas;
* escribe y lee datos protegidos, y en disco quedan cifrados;
* SQLite pelado sobre la base robada no dice el nombre ni el telefono;
* la planilla de cierre queda sellada;
* reiniciar el ejecutable sigue leyendo lo guardado;
* licencia manipulada → DENY, y el ejecutable no abre, y la base sigue estando;
* secreto corrupto → DENY sin destruir;
* rollback: datos y planillas vuelven a texto plano, y se puede volver a
  proteger.

## Lo que sigue sin poder afirmarse

Que el blob sellado con DPAPI **no abra en otra PC**. No hay una segunda
computadora en esta sesion. Es la unica afirmacion de todo el slice que no se
pudo comprobar aca, y por eso no se afirma: es el paso 8 del instructivo, con la
Optica mirando.
