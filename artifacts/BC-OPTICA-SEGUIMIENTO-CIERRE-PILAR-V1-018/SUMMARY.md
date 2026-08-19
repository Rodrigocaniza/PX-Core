# BC-OPTICA-SEGUIMIENTO-CIERRE-PILAR-V1-018

El cierre normal **ya existía** en el dominio, bien hecho y bien guardado. Lo que
no existía era la puerta: la pantalla sólo ofrecía «Cerrar por excepción», así
que la única forma de archivar un trabajo terminado era declararlo una anomalía e
inventar un motivo.

## Qué es cada cosa

| | |
|---|---|
| **`RECIBIDO EN PILAR`** | el final normal del circuito. El trabajo volvió. No falta ningún hecho. |
| **`CERRADO`** | archivado. Sacarlo de la vista, nada más. |

Está dicho en el código, no lo deduje: *«Un trabajo está activo mientras no
completó el circuito. `RECIBIDO EN PILAR` lo completa; `CERRADO` es el archivado
posterior»*. Y para la operadora los dos caen en el mismo grupo, **Completados**.

Por eso archivar es opcional: un trabajo que volvió a Pilar ya salió de lo
pendiente sin que nadie haga nada. Nunca hubo un cierre obligatorio disfrazado de
excepción — el circuito no exige cerrar.

## La causa real

`close_by_exception` es, textualmente, *«la salida para lo que no llegó a
completarse: cancelaciones, devoluciones a exhibición, trabajos sin efecto y
correcciones administrativas»*. Exigir motivo ahí es correcto.

Y `close_work` —el cierre normal, sin motivo— **existía desde RC19**, con la
guarda correcta: la matriz sólo admite `CERRADO` desde `RECIBIDO EN PILAR`, así
que no puede usarse para cerrar en silencio un trabajo perdido en el laboratorio.

Pero ningún punto de la pantalla lo llamaba. Sólo lo usaban tests. La operadora
que quería archivar tenía un solo camino visible, y ese camino pedía un motivo.

**No es una transición que falta. Es una acción que existe y no se ofrecía.**

## Una corrección a lo que dije en V1-017

Cerré V1-017 con un finding que decía que el cierre normal exigía motivo. Eso
salió de **mi propia prueba**, que llamaba a `close_by_exception` con
`reason="entregado al cliente"` porque era la única forma que había mirado. No
era el comportamiento del producto. Queda corregido acá, que es donde se
investigó de verdad.

## Flujo Pilar, antes y después

**Antes.** El trabajo vuelve a Pilar → `RECIBIDO EN PILAR` → queda ahí. Para
sacarlo de la lista: *Más ▾ → Cerrar por excepción*, motivo obligatorio.

**Después.** Igual hasta Pilar. Para sacarlo de la lista: *Más ▾ → Archivar
terminados*, sin motivo, con responsable y traza. «Cerrar por excepción» sigue
justo debajo, para lo que no terminó.

Si la selección incluye algo que todavía no volvió a Pilar, archivar no corre y
dice cuál es el camino correcto en vez de fallar con un error de dominio.

## Motivo: cuándo sí y cuándo no

| | motivo | responsable |
|---|---|---|
| **Archivar terminados** | no | **sí** |
| **Cerrar por excepción** | **sí** | sí |

No pedir motivo no es no pedir nada. `close_work` no exigía responsable —se podía
archivar con el actor en blanco— y eso sí era un hueco: cuando alguien pregunte
por qué un trabajo desapareció de la lista, quién lo archivó es la mitad de la
respuesta. Ahora lo exige.

## Lo que se revisó y quedó igual

- **No hay matrices por sucursal.** El circuito es uno solo y la sucursal
  responsable se deriva de la etapa. Pilar no tiene un flujo especial, ni le
  falta uno: comparte la misma máquina que Asunción.
- **La matriz de transiciones: intacta.** No se agregó ni se quitó una arista.
- **`close_by_exception`: intacto.** Sigue pudiendo cerrar desde cualquier etapa,
  que es lo que lo hace útil, y sigue exigiendo motivo.
- **Las transiciones históricas: intactas.** Lo cerrado por excepción antes sigue
  diciendo lo mismo. La regla nueva es hacia adelante.

## Pruebas

21 dirigidas nuevas, verdes. Cubren los 12 casos pedidos, y la que más importa es
`test_el_cierre_normal_NO_puede_cerrar_algo_a_mitad_de_camino`: si el archivado
pudiera correr desde cualquier etapa, un trabajo perdido en el laboratorio
desaparecería sin que nadie explique nada, y ésa es exactamente la diferencia
entre los dos cierres.

Suite de Caja: **746 verdes, ninguna roja**. Repo: 1114 verdes y las 2 rojas de
Gestión Central ya clasificadas `PREEXISTING_OUT_OF_SCOPE` en V1-015, estables en
tres corridas seguidas.

## Migración

**No.** El cambio es lógica y pantalla: un guard de responsable en el servicio y
una entrada de menú. Ninguna tabla, ninguna columna, ningún dato.

## Invariantes

Dos archivos y un test nuevo. No se tocó ventas, stock, inventario, FactuFácil,
Delivery, el catálogo de laboratorios ni la Caja histórica — hay una prueba que
compara las ocho tablas antes y después de archivar.

## Estado

Listo para el próximo empaquetado de BC Caja. **No requiere migración ni apply
productivo sobre la base.**
