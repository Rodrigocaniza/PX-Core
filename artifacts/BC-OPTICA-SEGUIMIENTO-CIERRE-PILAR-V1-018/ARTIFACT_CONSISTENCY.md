# Artifact Consistency — V1-018

Cada afirmación, contra lo que se leyó del repositorio o se ejecutó.

## La afirmación central

«El cierre normal ya existía, sólo que la pantalla no lo ofrecía» no es una
lectura: se probó contra una base real antes de escribir una línea de UI.

| prueba | resultado |
|---|---|
| `close_work` desde `EN_LABORATORIO` | **BLOQUEADO** — `transicion invalida` |
| `close_work` desde `RECIBIDO_EN_PILAR` | `CERRADO`, nota vacía, actor registrado |
| `close_work` dos veces | **BLOQUEADO** |
| referencias a `close_work` en producción | **ninguna**; sólo cuatro tests |

De ahí sale la conclusión: no faltaba una transición, faltaba la puerta.

## Números

| afirmación | contra qué | |
|---|---|---|
| `RECIBIDO EN PILAR` es el final normal | comentario de `ESTADOS_COMPLETADOS` | ✔ |
| `CERRADO` es archivado | `GRUPO_DE_ETAPA[CLOSED] == "completados"` | ✔ |
| la excepción es para lo que no completó | comentario de `close_by_exception` | ✔ |
| no hay matrices por sucursal | `ALLOWED_TRANSITIONS` es una sola; la sucursal sale de `RESPONSABLE_POR_ETAPA` | ✔ |
| 21 dirigidas | `21 passed` | ✔ |
| Caja 746 verdes, 0 rojas | `746 passed` | ✔ |
| repo 1114 + 2 | `1114 passed, 2 failed`, tres corridas | ✔ |
| sin migración | no se agregó ningún `.sql` | ✔ |
| dos archivos tocados | `git diff --stat`: `CajaDiaria.py` +49, `tracking_service.py` +17 | ✔ |

## Lo que se corrigió de un artifact anterior

El `FINDINGS.json` de V1-017 dice que el cierre normal exigía motivo. **Es
incorrecto**, y sale de que la prueba de aquella misión llamaba a
`close_by_exception` con `reason="entregado al cliente"` — el único camino que se
había mirado entonces. No se reescribe V1-017: la corrección queda acá, que es
donde se investigó, y en `MANIFEST.json` bajo `correccion_de_v1_017`.

## Lo que se creyó defecto y no lo era

- **«Pilar tiene una ruta incompleta».** No la tiene. No hay rutas por sucursal:
  el circuito es uno y la responsabilidad se deriva de la etapa. Asunción y
  Pilar comparten la misma máquina de estados.
- **«Cerrar es obligatorio y por eso se abusa de la excepción».** No es
  obligatorio: `RECIBIDO EN PILAR` ya cuenta como completado y sale de lo
  pendiente sin que nadie haga nada. Archivar es housekeeping.

## Un rojo transitorio, dicho de frente

En una de siete corridas completas apareció un tercer fallo. No se reprodujo en
las tres corridas siguientes ni en cuatro corridas dirigidas del conjunto que
construye Tk. Encaja con el patrón que V1-016 ya diagnosticó y corrigió del lado
de Caja: un root de Tk por prueba agota los intérpretes Tcl en Windows. Los tests
de Gestión Central todavía lo hacen así.

No se arregló acá —es otra misión y otro módulo— pero queda en `FINDINGS.json`
con la recomendación. Un flake que nadie anota vuelve como misterio.

## Lo que NO se afirma

- que esto se haya probado contra la base de la Óptica. **No.** Bases temporales.
- que la excepción esté mal usada hoy en producción. No hay forma de saberlo
  desde Casa: haría falta mirar el historial real.
- que los adyacentes de V1-017 se hayan tocado. No se tocaron.

## Sorpresa

El método del cierre normal llevaba desde RC19 en el servicio, completo y bien
guardado, y en todo ese tiempo sólo lo llamaron los tests. Es la forma más
silenciosa de un defecto: no falla, no rompe nada, y empuja a la gente al camino
equivocado porque es el único que se ve.
