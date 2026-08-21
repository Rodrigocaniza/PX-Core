# BC-OPTICA-SEGUIMIENTO-ATRASADO-TRANSICION-V1-017

El bloqueo reportado —un trabajo `EN LABORATORIO` y `ATRASADO` que sólo ofrecía
«Contactar»— **ya estaba corregido**. Lo que no estaba corregido, y sí lo está
ahora, es la otra mitad: después de que ese trabajo llegaba, no había forma de
demostrar que había estado atrasado.

## Lo primero, porque cambia el resto del informe

El defecto existió y fue exactamente como se describe. Se encontró en la prueba
manual de **rc.24**, y se corrigió el **16/08** en `551f68c`, con su regresión en
`test_rc26_flujo_no_se_traba.py`. El mensaje de ese commit lo dice con las mismas
palabras del reporte: *«la operadora podía registrar llamadas para siempre sin
poder avanzar, y la única salida era comprometer un plazo futuro que el
laboratorio no había dado»*.

`551f68c` es ancestro de `7db56a0` (rc.31) y de `0906ffc` (rc.32, la que está
instalada en la Óptica desde el 19/08). **La versión instalada ya lo tiene.** Lo
que se observó corresponde a una versión anterior al 16/08.

No lo di por bueno leyendo el código. Escribí los trece escenarios pedidos desde
cero, sin mirar la suite existente, y los corrí contra una base SQLite real: el
caso central —`EN LABORATORIO` + `ATRASADO` → puede recibirse— pasa.

## La causa raíz, y por qué era esa

`next_action` decidía mirando el atraso, y devolvía `CONTACT_LABORATORY` en vez
de `RECEIVE_FROM_LABORATORY`. Contactar no transiciona, así que el trabajo
quedaba sin salida.

El arreglo fue conceptual, no un parche: la etapa física y la condición temporal
son dimensiones distintas. `next_action` devuelve siempre la transición física y
acepta `overdue` sin usarlo; `complementary_action` responde qué conviene hacer
**además**. La pantalla muestra esa sugerencia renombrando el botón de *Novedad*
a «Contactar laboratorio», y nunca toca el botón que avanza.

## Qué es `ATRASADO`

**Condición derivada, no estado.** No hay columna que lo guarde —lo verifiqué
contra el esquema— y se calcula comparando el plazo comprometido con el reloj:

```
is_overdue = status ∈ LATENESS_APPLIES_TO  ∧  ahora ≥ deadline
```

Por eso un trabajo puede estar `EN LABORATORIO` **y** atrasado sin duplicar
registros ni perder su etapa. Y por eso se apaga solo cuando el trabajo sale del
laboratorio: el plazo pertenece a esa estadía.

## El defecto que sí quedaba

Al salir del laboratorio se borran `expected_date` y `expected_time`. Eso es
correcto —si quedaran, un trabajo que ya llegó seguiría figurando atrasado— pero
borraba la única evidencia de que había habido un plazo.

Consecuencia real: un trabajo que llegó cuatro días tarde, media hora después de
recibirlo era indistinguible de uno que llegó puntual. La transición sólo decía
la hora de llegada. Reclamarle al laboratorio, o entender por qué un cliente
esperó, se volvía imposible.

Y la misión pedía exactamente lo contrario: *«si un trabajo estuvo atrasado y
luego llegó, la historia debe poder demostrar ambas cosas»*.

## Qué se cambió

Un solo archivo de dominio, `modulos/caja_diaria/domain/tracking.py`:

1. **La transición que termina el plazo lo sella.** Al salir de `EN LABORATORIO`,
   la nota de esa transición —inmutable y ya persistida— queda con
   `Plazo comprometido 18/08 17:00 · llegó 1 día tarde`, o
   `· llegó dentro del plazo` cuando corresponde. Si la operadora escribió su
   propia nota, el sello se agrega detrás y no la pisa.

2. **La ficha del trabajo lo muestra.** «Última novedad» incluye la nota de la
   última transición. Una evidencia que nadie puede mirar no demuestra nada.

**Sin migración.** `tracked_work_transitions.note` ya existía y ya se guardaba:
lo que faltaba era escribir ahí lo que se estaba perdiendo. Sellar el plazo en la
transición que lo cierra es además más honesto que conservarlo en el trabajo —
dice cuándo dejó de correr, no sólo cuál era.

Una novedad registrada a mano sigue teniendo prioridad sobre el sello: si alguien
llamó al laboratorio, eso es lo último que pasó. Esa prioridad no se tocó.

## Lo que se revisó y quedó como estaba

- La matriz de transiciones: intacta. El único retroceso admitido —volver al
  laboratorio si el trabajo vino mal— sigue admitido, y sigue siendo el único.
- `RECIBIDO EN PILAR` no ofrece «acción siguiente», y **es correcto**: ahí
  termina el circuito físico. `CERRADO` es el archivado posterior y tiene su
  propio camino, con motivo y responsable. Lo verifiqué antes de tocarlo, porque
  a primera vista parece un flujo incompleto y no lo es.
- La barra de acciones de la pantalla: ya decidía por la acción y no por el
  atraso. No se tocó una línea de `CajaDiaria.py`.

## Pruebas

24 dirigidas nuevas, verdes. Cubren los trece casos pedidos y cuatro más sobre el
sello: que no aparezca donde no hay plazo, que no pise la nota de la operadora,
que sobreviva al reinicio, y que el que llegó a tiempo también quede documentado.

Suite de Caja: **723 verdes, ninguna roja**. Repo: 1093 verdes y las 2 rojas de
Gestión Central ya clasificadas `PREEXISTING_OUT_OF_SCOPE` en V1-015.

Las nuevas se solapan a propósito con `test_rc26_flujo_no_se_traba.py`: aquélla
fija la regla desde el dominio, ésta desde el lado de la operadora. Que las dos
digan lo mismo era parte de lo que había que averiguar.

## Invariantes

El slice toca un archivo de dominio y agrega un test. No hay migración, y no se
tocó ventas, stock, movimientos de inventario, arqueos, FactuFácil, Delivery, el
catálogo de laboratorios ni la Caja histórica.

## Estado

**No requiere migración ni aplicación productiva sobre la base.** Es código: se
instala con la próxima versión de BC Caja. El bloqueo operativo ya está resuelto
en la versión que la Óptica corre hoy; lo que agrega este slice es la evidencia
del atraso, que entrará con el próximo empaquetado.
