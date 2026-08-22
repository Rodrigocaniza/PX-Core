# Instalar BC Seguridad V1 en la Optica

Todo lo que se podia automatizar desde Casa esta hecho. Lo que sigue es lo que
**tiene** que pasar delante de la computadora real, porque depende del hardware
de esa PC y de la base productiva, que no viaja.

Tiempo estimado: 25 minutos por PC. Se puede abortar en cualquier paso: hasta
el paso 5 no se toca un solo dato.

---

## Donde se corre cada cosa

| | |
|---|---|
| **En la PC de la Optica** | `BC-Caja.exe` y `Seguridad\BC-Seguridad.exe`, los dos dentro de la carpeta del paquete. **No hace falta Python.** |
| **En la maquina de administracion** | `bc_security_issuer.py`, que es el unico que tiene la clave privada. Nunca se copia a la Optica. |

Todos los comandos de abajo se escriben en una consola abierta **dentro de la
carpeta del paquete** (Shift + clic derecho sobre la carpeta > "Abrir ventana de
PowerShell aqui").

---

## Antes de empezar

- [ ] Tener a mano **papel y lapicera**. En el paso 3 aparece una frase que se
      muestra una sola vez y no se puede volver a ver.
- [ ] Confirmar que la PC es la definitiva. Enrolar ata BC a esta computadora.
- [ ] Confirmar que las migraciones 029 a 032 ya estan aplicadas. La 033 va
      detras de ellas.

---

## 1. Actualizar BC y dejar que migre

Instalar el paquete nuevo y abrir BC una vez, normalmente.

La migracion **033** corre sola al abrir. Crea tres tablas vacias y **no cambia
nada mas**: no cifra, no toca ventas, no toca caja, no toca stock. BC funciona
igual que ayer porque esta PC todavia no esta enrolada.

Verificar:

```
Seguridad\BC-Seguridad.exe estado
```

Tiene que decir `tablas de seguridad : si` y `enrolada : no`.

---

## 2. Respaldo manual, aparte del automatico

Copiar `bc_caja.sqlite3` a un pendrive y a otra carpeta. El paso 5 hace su
propio respaldo, pero este es el que queda **fuera** de la computadora.

---

## 3. Enrolar la PC

```
Seguridad\BC-Seguridad.exe enrolar --etiqueta "Optica - Caja 1"
```

Esto:

* crea la identidad de instalacion y su secreto, sellado por Windows;
* crea la clave de datos de la base;
* **muestra la frase de recuperacion, una sola vez**;
* deja `solicitud-de-enrolamiento.json` en la carpeta de seguridad.

> **ANOTAR LA FRASE EN PAPEL AHORA.** Guardarla fuera de esta computadora.
> Es lo unico que permite recuperar la base si esta PC se quema. No esta
> guardada en ningun lado: si se pierde y la PC se pierde, los datos no vuelven.

Copiar `solicitud-de-enrolamiento.json` a la maquina de administracion.

---

## 4. Emitir la licencia (en la maquina de administracion, no en la Optica)

```
python tools/bc_security_issuer.py emitir ^
  --solicitud solicitud-de-enrolamiento.json ^
  --salida licencia.bclic ^
  --negocio "Optica" --organizacion optica --sucursal ASUNCION ^
  --lease-dias 365 --gracia-dias 180
```

Un lease de un ano con medio ano de gracia: la Optica no puede quedarse sin
Caja por una caida de Internet ni por que nadie haya renovado a tiempo.

Llevar `licencia.bclic` a la PC de la Optica e instalarla:

```
Seguridad\BC-Seguridad.exe instalar-licencia licencia.bclic
Seguridad\BC-Seguridad.exe verificar
```

`verificar` tiene que decir `ALLOW / OK`.

---

## 5. Proteger los datos existentes

Primero el ensayo, que no escribe nada:

```
Seguridad\BC-Seguridad.exe proteger-datos
```

Muestra cuantos valores hay en claro por columna. Si el numero tiene sentido,
aplicar:

```
Seguridad\BC-Seguridad.exe proteger-datos --confirmar --actor "tu nombre"
```

Hace su propio respaldo antes de tocar nada, corre todo en una sola
transaccion, y al final dice `quedan en claro: nada`.

---

## 6. Validar que la Optica trabaja igual

Primero la comprobacion automatica, que escribe una venta de prueba, la vuelve
a leer y mira la base con SQLite pelado:

```
BC-Caja.exe --security-check
```

Tiene que decir `cifrado_en_disco=si filtracion=no`.

Despues, a mano:

Abrir BC y comprobar, con datos reales:

- [ ] el historial muestra los nombres y telefonos de siempre;
- [ ] la busqueda de pedidos por cliente encuentra lo que encontraba;
- [ ] FactuFacil filtra por cliente;
- [ ] se puede cargar una venta nueva y se lee bien despues de cerrar y abrir;
- [ ] al cerrar la Caja, la planilla se manda por correo como siempre.

> La planilla de cierre queda **sellada** en `Reports\`: ya no se abre con
> doble clic, porque llevaba nombre, telefono y receta de cada cliente en claro.
> El correo sigue llegando igual. Si hace falta abrirla en la PC:
> `Seguridad\BC-Seguridad.exe abrir-informe Reports\cierre-XXXX.pdf`

---

## 7. La prueba de copia — el punto de todo esto

Con la Optica mirando, para que quede claro que no es una promesa:

1. Copiar a un pendrive la carpeta de instalacion, `%LOCALAPPDATA%\BC` entera y
   `bc_caja.sqlite3`.
2. Llevarlo a **otra** computadora y ejecutar BC desde ahi.
3. **Tiene que decir que esa copia no esta autorizada y no abrir.**
4. Abrir el `bc_caja.sqlite3` copiado con cualquier visor de SQLite.
   **Donde antes decia el nombre del paciente ahora dice `bcx1:...`.**

Volver a la PC de la Optica y mirar la bitacora:

```
Seguridad\BC-Seguridad.exe auditoria
```

El intento tiene que estar ahi, con `MAQUINA_DISTINTA`.

---

## 8. Probar la vuelta atras

Antes de dar el dia por cerrado, comprobar que el camino de regreso existe:

```
Seguridad\BC-Seguridad.exe revertir-datos --confirmar --actor "tu nombre"
Seguridad\BC-Seguridad.exe estado          # todo en claro otra vez
Seguridad\BC-Seguridad.exe proteger-datos --confirmar --actor "tu nombre"
```

Si el rollback no funcionara, se sabe hoy y no dentro de tres meses.

---

## Si algo sale mal

| Sintoma | Que hacer |
|---|---|
| BC no abre y dice que pertenece a otra computadora | `Seguridad\BC-Seguridad.exe verificar` y mirar el motivo. Si cambio hardware, re-emitir la licencia con una solicitud nueva. |
| BC no abre y la base esta cifrada | `Seguridad\BC-Seguridad.exe recuperar --frase "..."` con la frase del paso 3. |
| Hay que volver al estado anterior | `revertir-datos --confirmar`, y si hace falta restaurar el respaldo del paso 2. |
| La frase se perdio y la PC funciona | `keyring.reset_recovery_passphrase` emite una nueva. **Hacerlo el mismo dia.** |

---

## Lo que queda pendiente despues de esta instalacion

* Repetir del paso 1 al 8 en cada PC de la Optica. Cada una se enrola aparte y
  tiene su propia identidad, su propia licencia y su propia frase.
