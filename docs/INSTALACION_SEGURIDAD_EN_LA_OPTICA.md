# Instalar BC Seguridad V1 en la Optica

Secuencia operativa. Se ejecuta **en orden**, sin saltear, una PC por vez.

Cada paso tiene tres partes: **hacer**, **tiene que decir** y **si no dice eso**.
Mientras lo que aparece en pantalla no sea exactamente lo que dice "tiene que
decir", **no se pasa al paso siguiente**. Ningun paso se da por bueno "porque
parecio andar".

* Del paso 0 al 6 **no se modifica un solo dato**: se puede abortar en cualquier
  momento cerrando la ventana, y la Optica queda como estaba.
* El paso 7 es el **punto de no retorno**: ahi se cifra. Antes de llegar hay dos
  respaldos hechos y verificados, y el paso 11 comprueba el mismo dia que la
  vuelta atras funciona.

Tiempo: 30 minutos por PC. Si algo sale mal, la regla es una sola:
**parar, no improvisar, ir a "Si algo sale mal" al final.**

---

## Donde se corre cada cosa

| | |
|---|---|
| **En la PC de la Optica** | `BC-Caja.exe` y `Seguridad\BC-Seguridad.exe`, los dos dentro de la carpeta del paquete. **No hace falta Python.** |
| **En la maquina de administracion** | `bc_security_issuer.py`, el unico que tiene la clave privada. **Nunca se copia a la Optica.** |

Todos los comandos se escriben en una consola abierta **dentro de la carpeta del
paquete**: Shift + clic derecho sobre la carpeta > "Abrir ventana de PowerShell
aqui".

---

## Paso 0 — Antes de tocar la PC

- [ ] **Papel y lapicera sobre la mesa.** En el paso 5 aparece una frase que se
      muestra **una sola vez** y no se puede volver a ver.
- [ ] **Un pendrive vacio**, para el respaldo del paso 4.
- [ ] Confirmar que **esta es la PC definitiva**. Enrolar ata BC a esta
      computadora.
- [ ] Confirmar que las migraciones **029, 030, 031 y 032 ya estan aplicadas**.
      La 033 va detras de ellas.
- [ ] Confirmar que **no hay una caja abierta sin cerrar** ni nadie usando BC
      contra esta base desde otra PC.

**Si falta cualquiera de los cinco: no se empieza.** No es una formalidad: el
paso 5 sin papel es una instalacion que no se puede recuperar.

---

## Paso 1 — Instalar el paquete y dejar que migre

**Hacer:** copiar la carpeta del paquete a la PC y abrir `BC-Caja.exe` una vez,
normalmente. Cerrarlo.

La migracion **033** corre sola al abrir. Crea tres tablas vacias y **no cambia
nada mas**: no cifra, no toca ventas, no toca caja, no toca stock. BC funciona
igual que ayer, porque esta PC todavia no esta enrolada.

---

## Paso 2 — Confirmar que la migracion entro

**Hacer:**

```
Seguridad\BC-Seguridad.exe estado
```

**Tiene que decir:** `tablas de seguridad : si` y `enrolada : no`.

**Si no dice eso:**

* si dice `tablas de seguridad : no`, BC no llego a migrar: abrirlo otra vez y
  mirar si dio error. **No seguir.**
* si dice `enrolada : si`, esta PC ya fue enrolada antes. **Parar y avisar**: no
  se re-enrola, porque re-enrolar invalida la clave de datos vigente.

---

## Paso 3 — Confirmar que BC funciona antes de tocar nada

**Hacer:** abrir BC y mirar el historial y un pedido cualquiera.

**Tiene que decir:** todo como siempre — nombres, telefonos y recetas visibles.

**Si no dice eso:** el problema es anterior a la seguridad. **Parar aca**: no se
cifra una base que ya venia funcionando mal.

---

## Paso 4 — Respaldo manual, fuera de esta computadora

**Hacer:** copiar `bc_caja.sqlite3` al pendrive **y** a otra carpeta de red o de
otra maquina. Abrir la copia del pendrive con cualquier visor de SQLite.

**Tiene que decir:** la copia abre y muestra las ventas.

**Si no dice eso:** el respaldo no existe. **No se sigue.** El paso 7 hace su
propio respaldo automatico, pero ese queda **dentro** de la misma PC: si la
maquina se quema, se va con ella.

---

## Paso 5 — Enrolar la PC

**Hacer:**

```
Seguridad\BC-Seguridad.exe enrolar --etiqueta "Optica - Caja 1"
```

Crea la identidad de esta instalacion y su secreto sellado por Windows, crea la
clave de datos de la base, **muestra la frase de recuperacion una sola vez**, y
deja `solicitud-de-enrolamiento.json` en la carpeta de seguridad.

> ### ANOTAR LA FRASE EN PAPEL AHORA, ANTES DE TOCAR NADA MAS.
> Guardarla fuera de esta computadora. Es lo unico que permite recuperar la base
> si esta PC se quema. **No esta guardada en ningun lado**: si se pierde la
> frase y se pierde la PC, los datos no vuelven.
>
> Leerla en voz alta contra el papel antes de cerrar la ventana.

**Tiene que decir:** el `installation_id`, la frase, y la ruta del archivo
`solicitud-de-enrolamiento.json`.

**Si no dice eso:** si el comando fallo, **no escribio nada** — ni identidad, ni
secreto, ni una linea de la base. Se puede volver a correr sin consecuencias.

Despues: copiar `solicitud-de-enrolamiento.json` al pendrive y llevarlo a la
maquina de administracion.

---

## Paso 6 — Emitir e instalar la licencia

**Hacer, en la maquina de administracion** (no en la Optica):

```
python tools/bc_security_issuer.py emitir ^
  --solicitud solicitud-de-enrolamiento.json ^
  --salida licencia.bclic ^
  --negocio "Optica" --organizacion optica --sucursal ASUNCION ^
  --lease-dias 365 --gracia-dias 180
```

Cambiar `--sucursal ASUNCION` por `PILAR` cuando sea esa PC.

Un lease de un ano con medio ano de gracia: la Optica no puede quedarse sin Caja
por una caida de Internet ni porque nadie haya renovado a tiempo.

**Hacer, de vuelta en la PC de la Optica:**

```
Seguridad\BC-Seguridad.exe instalar-licencia licencia.bclic
Seguridad\BC-Seguridad.exe verificar
```

**Tiene que decir:** `ALLOW / OK`.

**Si no dice eso:** `verificar` dice el motivo. Con `MAQUINA_DISTINTA` la
licencia se emitio contra otra solicitud: re-emitir con la solicitud de **esta**
PC. **Hasta que no diga ALLOW / OK no se pasa al paso 7.** Una base cifrada en
una PC que no puede verificar su licencia es una Optica sin Caja.

---

## Paso 7 — Proteger los datos existentes (punto de no retorno)

Primero el **ensayo**, que no escribe nada:

```
Seguridad\BC-Seguridad.exe proteger-datos
```

**Tiene que decir:** una cantidad de valores en claro por columna que tenga
sentido para esta Optica. Si dice cero en todo, algo esta mal: **parar**.

Recien entonces, aplicar:

```
Seguridad\BC-Seguridad.exe proteger-datos --confirmar --actor "tu nombre"
```

Hace su propio respaldo antes de tocar nada y corre **todo en una sola
transaccion**.

**Tiene que decir:** `respaldo previo: ...`, y al final `quedan en claro: nada` e
`informes en claro: ninguno`.

**Si no dice eso:** si el comando fallo a la mitad, **SQLite dejo la base en el
estado exacto anterior** — no queda mitad cifrada, y BC sigue abriendo. Se puede
reintentar. Si al reintentar vuelve a fallar, **parar y avisar**: no forzar.

---

## Paso 8 — Comprobacion automatica

**Hacer:**

```
BC-Caja.exe --security-check
```

Escribe una venta de prueba, la vuelve a leer, y mira la base con SQLite pelado.

**Tiene que decir:** `cifrado_en_disco=si filtracion=no planilla=sellada`.

**Si no dice eso:** con `filtracion=si` hay un dato sensible en claro en disco.
**Parar**: ir al paso 11 (revertir) y avisar antes de seguir operando.

---

## Paso 9 — Comprobacion a mano, con datos reales

Abrir BC y verificar, uno por uno:

- [ ] el historial muestra los nombres y telefonos de siempre;
- [ ] la busqueda de pedidos por cliente encuentra lo que encontraba;
- [ ] FactuFacil filtra por cliente;
- [ ] se carga una venta nueva y se lee bien despues de cerrar y abrir BC;
- [ ] al cerrar la Caja, la planilla se manda por correo como siempre.

**Si alguno falla:** parar aca. El camino de vuelta es el paso 11.

> La planilla de cierre queda **sellada** en `Reports\`: ya no se abre con doble
> clic, porque llevaba nombre, telefono y receta de cada cliente en claro. El
> correo sigue llegando igual. Para abrirla en la PC:
>
> ```
> Seguridad\BC-Seguridad.exe abrir-informe Reports\cierre-XXXX.pdf
> ```

---

## Paso 10 — La prueba de copia, delante del cliente

Es el punto de todo esto, y **es lo unico que no se pudo verificar desde Casa**.
Se hace con la Optica mirando.

1. Copiar a un pendrive: la carpeta de instalacion, `%LOCALAPPDATA%\BC` entera y
   `bc_caja.sqlite3`.
2. Llevarlo a **otra** computadora y ejecutar BC desde ahi.

**Tiene que decir:** que esa copia **no esta autorizada**, y **no abrir**.

3. Abrir el `bc_caja.sqlite3` copiado con cualquier visor de SQLite.

O comprobar automaticamente, sin instalar Python ni SQLite:

```
Seguridad\BC-Seguridad.exe verificar-bcx1 --base C:\ruta\bc_caja.sqlite3
```

**Tiene que decir:** `BCX1_OK valores=<numero mayor que cero> en_claro=0 integrity_check=ok`.

**Tiene que decir:** donde antes decia el nombre del paciente, ahora dice
`bcx1:...`.

**Si la copia abre en la otra PC: PARAR TODO Y AVISAR.** Es el unico resultado
de toda la instalacion que invalida la premisa. No se instala la segunda Optica
hasta entender por que.

De vuelta en la PC de la Optica:

```
Seguridad\BC-Seguridad.exe auditoria
```

**Tiene que decir:** el intento, con `MAQUINA_DISTINTA`.

---

## Paso 11 — Ensayo de la vuelta atras

Se hace **el mismo dia**. Si el rollback no funcionara, hay que saberlo hoy y no
dentro de tres meses.

```
Seguridad\BC-Seguridad.exe revertir-datos --confirmar --actor "tu nombre"
Seguridad\BC-Seguridad.exe estado
```

**Tiene que decir:** que los datos volvieron a texto plano.

Y volver a proteger, que es como queda la PC:

```
Seguridad\BC-Seguridad.exe proteger-datos --confirmar --actor "tu nombre"
Seguridad\BC-Seguridad.exe verificar
```

**Tiene que decir:** `ALLOW / OK`, y nada en claro.

**Si el revertir falla:** los datos siguen cifrados y BC los sigue leyendo — el
fallo no destruye nada. Restaurar el respaldo del paso 4 solo si ademas BC no
abre.

---

## Paso 12 — Cerrar la instalacion

- [ ] Borrar `licencia.bclic` y `solicitud-de-enrolamiento.json` del pendrive.
- [ ] Guardar el papel con la frase **fuera de la Optica**.
- [ ] Completar la hoja de la instalacion: fecha, `installation_id`, quien
      enrolo, y el resultado del paso 10.
- [ ] Guardar el pendrive del paso 4 en otro lugar fisico.

---

## Si algo sale mal

| Sintoma | Que hacer |
|---|---|
| BC no abre y dice que pertenece a otra computadora | `Seguridad\BC-Seguridad.exe verificar` y mirar el motivo. Si cambio hardware, re-emitir la licencia con una solicitud nueva. |
| BC no abre y la base esta cifrada | `Seguridad\BC-Seguridad.exe recuperar --frase "la frase del paso 5"` |
| Hay que volver al estado anterior | `revertir-datos --confirmar`; si eso no alcanza, restaurar el respaldo del paso 4. |
| La frase se perdio y la PC todavia funciona | `keyring.reset_recovery_passphrase` emite una nueva. **Hacerlo el mismo dia.** |
| Un comando fallo a la mitad | No queda nada a medio hacer: el enrolamiento no escribe si el sellado no reabre, y la proteccion corre en una sola transaccion. Reintentar; si vuelve a fallar, parar. |

---

## Despues de esta PC

Repetir del paso 0 al 12 en cada PC. **Cada una se enrola aparte** y tiene su
propia identidad, su propia licencia y su propia frase. Una frase no sirve para
otra PC.

Las dos instalaciones previstas y sus hojas de evidencia estan en
`artifacts/BC-SECURITY-INSTALLATION-BINDING-V1-001/INSTALACIONES/`.
