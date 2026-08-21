# Artifact Consistency — V1-016

Cada afirmación, contra lo que realmente corrió.

## Números

| afirmación | dónde | contra qué se comprobó | |
|---|---|---|---|
| migración 029 es la siguiente | todos | `SELECT MAX(version)` sobre base recién migrada: `028` | ✔ |
| 28 → 29 migraciones | MANIFEST | salida real de la corrida | ✔ |
| exactamente 2 tablas nuevas | todos | `sqlite_master` antes vs después | ✔ |
| ninguna tabla existente modificada | SUMMARY | la 029 sólo tiene `CREATE TABLE`/`CREATE INDEX` | ✔ |
| las tablas nuevas nacen vacías | MANIFEST | `COUNT(*) = 0` en las dos | ✔ |
| 43 dirigidas | SUMMARY | `30 passed` + `13 passed` | ✔ |
| Caja 701 verdes, 0 rojas | SUMMARY | `701 passed` | ✔ |
| repo 1069 + 2 | SUMMARY | `1069 passed, 2 failed`, dos corridas idénticas y 0 skips | ✔ |
| las 2 rojas son de V1-015 | SUMMARY | mismos dos ids, ya clasificados con evidencia allí | ✔ |
| la caja del día no cambia | SUMMARY | entradas/total/efectivo/revisiones antes vs después | ✔ |
| `origin/main` intacto | MANIFEST | `7db56a0`, no se tocó | ✔ |

## Sobre el soporte previo que se encontró

Todo lo que se afirma sale del repositorio, no de un recuerdo:

| afirmación | evidencia |
|---|---|
| existe una bandeja FactuFácil previa | `mission/bc-gestion-central-factufacil-bandeja-001` @ `eb6d082` |
| no está en `main` ni en la cadena Óptica | `git merge-base --is-ancestor` → NO en los dos casos |
| excluye al operador local | `raise AccessDenied("operador local sin acceso a FactuFácil")`, línea del propio `factufacil.py` |
| se alimenta de la revisión, no de Caja | `sync_review_sales(actor, review_service)` |
| existe un contrato de orden de campos | `FACTUFACIL_CONTRACT.md` |
| `factufacil_status` viajaba vacío | `real_sync.py`: `"factufacil_status": "NO DISPONIBLE PILOTO"` |

## Lo que la base de prueba NO es

| | copia local | producción |
|---|---|---|
| origen | creada desde cero en el estado 028 | la Óptica, con su historia |
| días de caja | 2 | los del piloto |
| ventas | 4 activas + 1 gasto + 1 anulada | 12 entradas · 6.400.000 |
| artículos / movimientos | 0 / 0 | 3.596 / 4.441 |

Los ceros de artículos y movimientos son ceros **de la copia**. Como invariante
prueban que la 029 no los crea; no prueban que no los altere en una base que sí
los tenga — la 029 no los nombra, y eso lo confirma la corrida en la Óptica.

Lo que sí es representativo: la copia tiene una anulada, un gasto y dos
sucursales, que es exactamente lo que la regla de PARA CARGAR tiene que
distinguir.

## Una prueba que cambió, y por qué

`test_el_datepicker_compartido_y_factufacil_no_se_tocaron` (RC15) afirmaba que la
palabra «FactuFácil» no aparecía en ninguna parte de `CajaDiaria.py`. Era la
forma más fuerte de comprobar que aquel slice no se metía con FactuFácil, y
servía porque entonces FactuFácil no existía en Caja.

V1-016 le da su propia pestaña, así que esa afirmación dejó de ser cierta **a
propósito**. Se dividió en dos:

- `test_el_datepicker_compartido_no_se_toco`: intacta, verifica lo mismo de antes;
- `test_apertura_sigue_sin_meterse_con_factufacil`: comprueba lo que la original
  quería decir —que la apertura del día y FactuFácil no se mezclen— mirando el
  bloque de la apertura en vez de todo el archivo.

No se borró una prueba para que pasara el build: se reemplazó una afirmación que
el producto cambió, y quedó dicho dónde.

## Lo que NO se afirma

- que esto esté validado contra la base de la Óptica. **No lo está.**
- que exista integración con FactuFácil. No existe, y esta misión no la crea.
- que Gestión Central quede conectada. Sigue recibiendo
  `"NO DISPONIBLE PILOTO"`; conectarla es otra misión.
- que los pendientes de V1-015 se hayan tocado. No se tocaron.

## Una flaqueza que apareció y se arregló

Las pruebas de la pestaña creaban un `CTk()` por prueba. En Windows eso agota los
intérpretes Tcl, y bajo la suite completa una o dos se **salteaban** —nunca
fallaban— sin ninguna razón de producto. Un salteo silencioso es peor que un
rojo: parece verde.

Se pasó a un solo root por módulo. Cuatro corridas seguidas de las 13, y dos de
la suite entera, dan lo mismo y sin un solo skip.

## Sorpresa

Esperaba tener que crear el modelo de datos de la venta para FactuFácil. No hizo
falta: `cash_entries` ya tenía los diez campos pedidos, incluidos CI/RUC,
teléfono y observaciones. El puente a Gestión Central los venía mapeando desde
hace misiones. Lo único que faltaba en todo el sistema era el hecho de que
alguien la cargó — y eso son dos tablas chicas.
