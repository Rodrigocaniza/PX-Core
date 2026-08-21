# Artifact Consistency — V1-019B

## Números

| afirmación | contra qué | |
|---|---|---|
| sin migración nueva | `max(schema_migrations)` sigue en `030`; hay prueba | ✔ |
| la sesión de caja dura más que 20 min | `expires_at - started_at`, y vence a las 00:00 | ✔ |
| entrar a atender no deja sesión admin | el set de `_sessions` no crece | ✔ |
| el token de caja no autoriza lo sensible | cinco operaciones administrativas, todas denegadas | ✔ |
| el bloqueo exponencial sigue vigente | tres intentos fallidos y la buena tampoco entra | ✔ |
| el relevo no toca la caja | `totals()` idéntico antes y después | ✔ |
| desactivar saca de la caja | `require_operator` consulta la base en cada uso | ✔ |
| la vendedora no es FK | `PRAGMA foreign_key_list(cash_entries)` | ✔ |
| 46 dirigidas | `46 passed` | ✔ |
| Caja 828 verdes | `828 passed` | ✔ |
| repo 1200 verdes, 0 rojas | `1200 passed`, dos corridas | ✔ |
| dos archivos tocados | `git diff --stat` | ✔ |

## Un defecto que encontró la revisión, y se corrigió

La primera versión abría el diálogo de login con `after(150, ...)` y seguía. El
comentario decía «no hay operación anónima»; el comportamiento decía otra cosa:
cancelando el diálogo, la caja quedaba usable y `responsable_actual()` devolvía
la cadena literal «Sin sesión», que se habría registrado como si fuera un nombre.

Un comentario que promete lo que el código no hace es peor que no tenerlo. Ahora
cancelar cierra la ventana, y hay prueba —vale igual al cerrar sesión.

## Decisiones que conviene ver escritas

- **`CASH_LOGIN_FAILED` no se agregó.** El login fallido ya se registra como
  `ADMIN_LOGIN`/`FAIL` por el camino que valida credenciales, que es el mismo.
  Agregar un evento equivalente sería tener el mismo hecho contado dos veces.
- **La sesión no se persiste.** Cerrar y reabrir BC Caja pide identificarse otra
  vez. Es lo correcto para una caja; queda como finding por si en la Óptica
  reinician la app varias veces al día.
- **Manda la sucursal de la caja**, no la de la persona. `cash_register_branches`
  ya era la fuente canónica y no se le agregó una segunda verdad.

## El finding de Gestión Central

Se preserva como estaba: `bootstrap_synthetic_pilot()` siembra alertas según el
momento, y por eso `test_ui_interactions.py` no es determinista. **No se
reclasifica como rojo estable** — en esta misión pasó en las dos corridas, y eso
es precisamente el síntoma. No se absorbió porque no impidió verificar nada.

## Lo que NO se afirma

- que esto se haya probado contra la base de la Óptica. **No.** Bases temporales.
- que la 030 esté aplicada allá. Sigue pendiente, y sin ella esto no tiene con
  quién funcionar.
- que se haya corrido un runner externo de ChainState. No existe en este repo:
  la cadena se ejecutó como revisión disciplinada dentro de la sesión, y decir
  otra cosa sería falso. El detalle está en `GATES.json`.

## Sorpresa

Esperaba tener que diseñar una política de expiración y terminé encontrándola
dicha por el problema: una caja se abre a la mañana y se cierra a la noche. Lo
difícil no era cuánto dura la sesión, sino aceptar que hacen falta dos —y que la
corta, la que ya existía, era la respuesta a la reautenticación de las acciones
sensibles sin que hubiera que construir nada.
