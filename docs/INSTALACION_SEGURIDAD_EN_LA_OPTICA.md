# Instalar BC Seguridad V1 en la Optica

Todo lo que se podia automatizar desde Casa esta hecho. Lo que sigue es lo que
**tiene** que pasar delante de la computadora real, porque depende del hardware
de esa PC y de la base productiva, que no viaja.

Tiempo estimado: 25 minutos por PC. Se puede abortar en cualquier paso: hasta
el paso 5 no se toca un solo dato.

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
python tools/bc_security.py estado
```

Tiene que decir `tablas de seguridad : si` y `enrolada : no`.

---

## 2. Respaldo manual, aparte del automatico

Copiar `bc_caja.sqlite3` a un pendrive y a otra carpeta. El paso 5 hace su
propio respaldo, pero este es el que queda **fuera** de la computadora.

---

## 3. Enrolar la PC

```
python tools/bc_security.py enrolar --etiqueta "Optica - Caja 1"
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
python tools/bc_security.py instalar-licencia licencia.bclic
python tools/bc_security.py verificar
```

`verificar` tiene que decir `ALLOW / OK`.

---

## 5. Proteger los datos existentes

Primero el ensayo, que no escribe nada:

```
python tools/bc_security.py proteger-datos
```

Muestra cuantos valores hay en claro por columna. Si el numero tiene sentido,
aplicar:

```
python tools/bc_security.py proteger-datos --confirmar --actor "tu nombre"
```

Hace su propio respaldo antes de tocar nada, corre todo en una sola
transaccion, y al final dice `quedan en claro: nada`.

---

## 6. Validar que la Optica trabaja igual

Abrir BC y comprobar, con datos reales:

- [ ] el historial muestra los nombres y telefonos de siempre;
- [ ] la busqueda de pedidos por cliente encuentra lo que encontraba;
- [ ] FactuFacil filtra por cliente;
- [ ] se puede cargar una venta nueva y se lee bien despues de cerrar y abrir.

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
python tools/bc_security.py auditoria
```

El intento tiene que estar ahi, con `MAQUINA_DISTINTA`.

---

## 8. Probar la vuelta atras

Antes de dar el dia por cerrado, comprobar que el camino de regreso existe:

```
python tools/bc_security.py revertir-datos --confirmar --actor "tu nombre"
python tools/bc_security.py estado          # todo en claro otra vez
python tools/bc_security.py proteger-datos --confirmar --actor "tu nombre"
```

Si el rollback no funcionara, se sabe hoy y no dentro de tres meses.

---

## Si algo sale mal

| Sintoma | Que hacer |
|---|---|
| BC no abre y dice que pertenece a otra computadora | `bc_security.py verificar` y mirar el motivo. Si cambio hardware, re-emitir la licencia con una solicitud nueva. |
| BC no abre y la base esta cifrada | `bc_security.py recuperar --frase "..."` con la frase del paso 3. |
| Hay que volver al estado anterior | `revertir-datos --confirmar`, y si hace falta restaurar el respaldo del paso 2. |
| La frase se perdio y la PC funciona | `keyring.reset_recovery_passphrase` emite una nueva. **Hacerlo el mismo dia.** |

---

## Lo que queda pendiente despues de esta instalacion

* Respaldar la clave privada del emisor fuera de linea
  (`bc_security_issuer.py respaldo-de-clave`). Sin ese respaldo, perder la
  maquina de administracion es perder la capacidad de emitir y de revocar.
* Repetir del paso 1 al 8 en cada PC de la Optica. Cada una se enrola aparte y
  tiene su propia identidad, su propia licencia y su propia frase.
