# Artifact Consistency — V1-019

## Números

| afirmación | contra qué | |
|---|---|---|
| la 030 es la siguiente | la base recién migrada daba `029` como máximo | ✔ |
| `admin_users` ya tenía credenciales reales | PBKDF2 390.000 iteraciones, sal, `locked_until` en el código | ✔ |
| `role` existía y nadie la leía | `DEFAULT 'ADMIN'` en la 015; cero lecturas en el código | ✔ |
| `authorized_responsibles` está muerta | grep en todo el repo: sólo aparece en la 015 | ✔ |
| la lista de vendedoras estaba cableada | `values=["Seleccionar...", "Ana", "Belén", "Carla", "Diana"]` | ✔ |
| 29 → 30 migraciones | salida real de la corrida | ✔ |
| exactamente 4 columnas nuevas | `PRAGMA table_info` antes vs después | ✔ |
| 38 dirigidas | `38 passed` | ✔ |
| Caja 784 verdes | `784 passed` | ✔ |
| repo 1154 verdes, 0 rojas | `1154 passed`, dos corridas | ✔ |
| la contraseña no se guarda en claro | prueba que vuelca `admin_users` y la bitácora entera | ✔ |

## Una corrección a lo que informé en cuatro misiones

En V1-015, V1-016, V1-017 y V1-018 informé dos rojos en
`tests/gestion_central/test_ui_interactions.py` como `PREEXISTING_OUT_OF_SCOPE`.

**Eran ajenos a esas misiones, y eso sigue siendo cierto.** Lo que estaba mal era
tratarlos como un rojo estable. Hoy pasan.

Lo comprobé en el **mismo commit de V1-018**, con `git stash -u`: esta tarde ese
commit daba `1114 passed, 2 failed`; ahora da `1116 passed, 0 failed`. Mismo
código, distinto resultado.

La causa probable está en la fixture: usa `bootstrap_synthetic_pilot()`, que
siembra alertas en función del momento, y el test afirma que sólo
`OPTICA_ASUNCION` queda con alertas. Eso depende de cuándo se corre.

No son un rojo permanente: son **pruebas no deterministas**, que es peor, porque
a veces mienten en verde. Queda en `FINDINGS.json` con la recomendación de un
slice de Gestión Central que fije el reloj. No se absorbe acá.

## Lo que NO se afirma

- que esto esté validado contra la base de la Óptica. **No.** Base local.
- que exista login de operadora. No existe, y este slice no lo crea: es V1-019B.
- que los cuatro nombres cableados fueran los de la Óptica. No hay forma de
  saberlo desde Casa; lo que sí se sabe es que estaban escritos en el código.
- que la migración 029 esté aplicada allá. Sigue pendiente, y la 030 la exige:
  el pre-guard lo comprueba y para si falta.

## Sorpresa

Esperaba tener que construir autenticación y me encontré con PBKDF2 de 390.000
iteraciones, sal por usuario, bloqueo exponencial y sesiones con vencimiento —
todo ya escrito, y usado para proteger una sola pantalla. Al lado, la decisión de
quién hizo cada venta salía de cuatro nombres de maqueta. El sistema era mucho
más serio en la parte que casi no se usa que en la que se usa todos los días.
