# Artifact Consistency — V1-017

Cada afirmación, contra lo que realmente se ejecutó o se leyó del repositorio.

## La afirmación más fuerte de este informe

«El bloqueo ya estaba corregido» no se dedujo leyendo el código. Se comprobó
así, y en este orden:

| paso | evidencia |
|---|---|
| se escribieron los 13 escenarios desde el reporte, sin mirar la suite existente | `test_v1017_atrasado_no_traba.py` |
| se corrieron contra SQLite real, no contra mocks | fixture `SQLiteCashDayRepository(tmp_path)` |
| el caso central pasa | `test_en_laboratorio_atrasado_TAMBIEN_puede_avanzar` verde |
| existe el commit del fix | `551f68c`, 2026-08-16 |
| existe su regresión | `test_rc26_flujo_no_se_traba.py`, 26 casos verdes |
| está en rc.31 | `git merge-base --is-ancestor 551f68c 7db56a0` → SI |
| está en rc.32, la instalada | `git merge-base --is-ancestor 551f68c 0906ffc` → SI |

De ahí sale la conclusión: lo observado es anterior al 16/08.

## Números

| afirmación | contra qué | |
|---|---|---|
| `ATRASADO` no está persistido | `PRAGMA table_info(tracked_works)`: ninguna columna overdue/atras | ✔ |
| 24 dirigidas nuevas | `24 passed` | ✔ |
| Caja 723 verdes, 0 rojas | `723 passed` | ✔ |
| repo 1093 + 2 | `1093 passed, 2 failed` | ✔ |
| las 2 rojas son las de V1-015 | mismos dos ids | ✔ |
| sin migración | no se agregó ningún `.sql`; `note` ya existía en `tracked_work_transitions` | ✔ |
| el slice toca un archivo | `git diff --stat`: `tracking.py`, 48+/1- | ✔ |

## Lo que se creyó defecto y no lo era

Dos expectativas mías fallaron al principio, y las dos estaban mal **yo**, no el
producto. Queda dicho porque explican por qué el diff es más chico de lo que
parecía que iba a ser:

- **`RECIBIDO EN PILAR` no ofrece acción siguiente.** Parece un flujo cortado.
  No lo es: ahí termina el circuito físico, y `CERRADO` es archivado posterior
  con motivo y responsable. Está documentado en `ESTADOS_COMPLETADOS`.
- **`expected_date` se borra al salir del laboratorio.** Parece pérdida de dato.
  Es deliberado y correcto — si quedara, el trabajo seguiría figurando atrasado
  después de llegar. Lo que sí faltaba era dejar constancia antes de borrarlo, y
  eso es lo que agrega esta misión.

## Lo que NO se afirma

- que esto se haya probado contra la base de la Óptica. **No.** Todo corrió
  sobre bases temporales creadas por la propia suite.
- que el reporte de operación fuera equivocado. Fue correcto; describe una
  versión anterior.
- que los adyacentes se hayan tocado. No se tocaron: se verificó que ya estaban
  resueltos, y está en `FINDINGS.json`.

## Sorpresa

Esperaba escribir un fix de transiciones. La matriz no necesitaba una línea: el
modelo ya separaba etapa física de condición temporal, y hasta el comentario de
`next_action` explicaba el bug en pasado. Lo que apareció buscando la evidencia
del defecto viejo fue uno nuevo y más silencioso — que el atraso, una vez
resuelto, no dejaba rastro. Ese sí era invisible: no rompe nada, sólo hace que
después nadie pueda demostrar lo que pasó.
