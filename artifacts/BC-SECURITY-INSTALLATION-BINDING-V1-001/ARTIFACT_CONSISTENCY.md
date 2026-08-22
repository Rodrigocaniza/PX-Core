# ARTIFACT CONSISTENCY — BC-SECURITY-INSTALLATION-BINDING-V1-001

Cada numero y cada afirmacion de los artifacts, contra el comando o el archivo
que lo produce. Lo que no se pudo contrastar esta declarado como tal, no
redactado como si se hubiera podido.

---

## Git

| Afirmado | Fuente | Resultado |
|---|---|---|
| branch `feature/bc-security-installation-binding-v1-001` | `git rev-parse --abbrev-ref HEAD` | coincide |
| base `origin/feature/bc-optica-comision-composturas-v1-021 @ 38ef01b` | `git rev-parse` sobre la rama y sobre HEAD antes del commit | coincide |
| `origin/main @ 628749b` | `git rev-parse origin/main` | coincide |
| **main NO es ancestro de la base** | `git merge-base --is-ancestor origin/main origin/feature/bc-optica-comision-composturas-v1-021` | exit distinto de cero |
| la 021 es la punta real de la cadena | se recorrieron las 22 ramas `origin/feature/bc-optica-*` con `merge-base --is-ancestor`; 21 son ancestro de la 021 | verdadero |
| la unica que no es ancestro es la 009 | mismo comando | `recuento-fisico-pendientes-v1-009` — rama lateral no integrada |
| main no tocado | no se ejecuto checkout, merge ni push sobre main en esta sesion | verdadero |
| worktree propio | `git worktree add -b ... C:/PX/SEC1` | creado en esta sesion |

**Declarado explicitamente:** la mision pedia partir de `origin/main` y **no se
hizo**. El motivo esta en `MANIFEST.json` y en `SUMMARY.md`, con el comando que
lo sostiene. Decir que se partio de main habria sido falso; partir de main
habria producido una capa de seguridad que no conoce la mitad de las tablas que
tiene que proteger.

---

## Migracion 033

| Afirmado | Fuente | Resultado |
|---|---|---|
| la 032 era la ultima antes de este slice | `ls migrations/` | 032 es la mayor; la 033 es la nueva |
| aditiva estricta | `test_no_altera_ni_borra_ni_actualiza_nada`, que busca SENTENCIAS (no palabras) al inicio de linea | verde |
| toda creacion es IF NOT EXISTS | `test_solo_crea_cosas_que_no_existen` | verde |
| no nombra historia economica | `test_no_nombra_ninguna_tabla_de_historia_economica`, sobre el .sql sin comentarios | verde |
| aplicarla deja las tres tablas vacias | `test_aplicarla_no_cambia_ni_una_fila_de_negocio`, que corre la cadena entera | verde |
| es la ultima de la cadena | `test_la_033_es_la_ultima_de_la_cadena` | verde |
| no aplicada en produccion | ningun comando de esta sesion abrio la base de la Optica | verdadero |

Nota sobre la prueba de aditividad: la primera version buscaba la palabra
`UPDATE` y daba rojo por `BEFORE UPDATE ON`, que es la definicion de un
disparador y no reescribe nada. Se corrigio la **prueba**, no la migracion, y
queda dicho: aflojarla habria sido el arreglo facil y el equivocado.

---

## Que informacion queda cifrada

| Afirmado | Fuente | Resultado |
|---|---|---|
| 18 columnas en 6 tablas | `PROTECTED_COLUMNS` en `field_protection.py` | contadas: 5+1+4+1+3+4 |
| todas existen en el esquema real | `test_el_registro_no_incluye_columnas_que_no_existen`, que corre la cadena y compara contra `PRAGMA table_info` | verde |
| la base robada no dice el nombre del paciente | `test_los_datos_del_paciente_no_se_leen_con_sqlite_normal`, que busca los literales en los **bytes crudos** del archivo | verde |
| el respaldo robado tampoco | `test_un_respaldo_robado_tampoco_los_revela`, sobre el respaldo que produce `backup_to` | verde |
| la clave de datos no esta en claro al lado de la base | `test_la_clave_de_datos_no_esta_en_claro_al_lado_de_la_base` | verde |
| BC sigue leyendo igual | `test_bc_los_sigue_leyendo_igual_que_siempre`, por el repositorio de produccion | verde |
| ninguna consulta compara una columna protegida | `test_ninguna_comparacion_en_sql_de_produccion`, barrido estatico sobre todo `modulos/` | verde |
| ninguna ordena ni agrupa por una columna protegida | `test_ninguna_ordena_ni_agrupa_por_columna_protegida` | verde |

**Verificado tambien fuera de las pruebas, con el camino de produccion real**
(DPAPI real, clave de emisor real, almacen de confianza commiteado, huella real
de esta maquina): se enrolo, se emitio, se instalo, `verificar` dio `ALLOW / OK`,
se guardo una venta por el repositorio, BC la leyo entera, SQLite pelado mostro
`bcx1:...`, y la busqueda de los cinco literales del paciente en los bytes del
archivo dio `ninguna`.

---

## Pruebas A a L

| Letra | Que pide la mision | Donde esta | Estado |
|---|---|---|---|
| A | instalacion correcta → ALLOW | `TestA_InstalacionCorrectaPermite` (4) | verde |
| B | carpeta copiada a otra identidad → DENY | `TestB_CarpetaCopiadaAOtraMaquinaDeniega` (7) | verde |
| C | licencia modificada byte a byte → DENY | `TestC_LicenciaModificadaDeniega` (8) | verde |
| D | licencia de otra instalacion → DENY | `TestD_LicenciaDeOtraInstalacionDeniega` (2) | verde |
| E | blob copiado → secreto no recuperable | `TestE_BlobLocalCopiadoNoEntregaElSecreto` (4) | verde |
| F | DB/backup robado → datos no legibles | `TestF_BaseRobadaNoRevelaDatosSensibles` (7) | verde |
| G | lease valido offline → ALLOW | `TestG_LeaseValidoOfflinePermite` (4) | verde |
| H | lease expirado → politica definida y probada | `TestH_LeaseVencidoPoliticaSegura` (5) | verde |
| I | instalacion revocada → DENY | `TestI_InstalacionRevocadaDeniega` (6) | verde |
| J | archivos perdidos/corruptos → fail-safe sin destruir | `TestJ_ArchivosPerdidosOCorruptosFallanSinDestruir` (7) | verde |
| K | rollback restaura el estado previo | `TestK_RollbackRestauraElEstadoPrevio` (6) | verde |
| L | suite completa sin regresiones | `python -m pytest` | ver abajo |

---

## Suite

| Afirmado | Fuente | Resultado |
|---|---|---|
| base antes de tocar nada | `python -m pytest` sobre la 021 sin cambios | 1369 pasan, 3 fallan |
| las 3 rojas de la base | `grep FAILED` de esa corrida | `test_el_valor_de_respaldo_sigue_al_paquete`, y dos de `gestion_central/test_ui_interactions.py` |
| suite de seguridad | `python -m pytest tests/seguridad` | 148 pasan |
| suite completa despues | `python -m pytest` | ver `GATES.json`, medido y no estimado |
| sin regresiones atribuibles a este slice | comparacion nominal de las rojas contra la base | ninguna roja nueva |

**Declarado:** dos de las tres rojas de la base son **inestables**, no
deterministas. `test_la_sesion_dura_la_jornada_y_no_veinte_minutos` se observo
fallando a las 23:50 y pasando a las 20:25 y a las 00:15 con el mismo codigo:
la sesion de operadora vence al fin de la jornada y la prueba afirma que dura
mas de 20 minutos. Esta anotado en `FINDINGS.json` como defecto preexistente y
**no se corrigio**, porque es de la V1-019B y la mision pide no mezclar.

---

## Lo que NO se pudo verificar, y no se afirma

| Afirmacion que seria natural hacer | Por que no se hace |
|---|---|
| "el blob DPAPI no abre en otra PC" | No se puede ejercer desde una sola computadora. La suite lo prueba con un sellador **simulado**, declarado como tal en el encabezado de `conftest.py`, y hay pruebas contra el DPAPI **real** de esta Windows (`test_dpapi_real.py`) para que la simulacion no sea la unica evidencia. La verificacion contra dos PCs distintas es el paso 7 del HUMAN_GATE. |
| "esto funciona contra la base productiva" | La base productiva vive solo en la Optica. Nada de esta sesion la abrio. |
| "el ejecutable empaquetado arranca con la capa" | No se construyo el paquete en esta sesion. `cryptography` tiene rueda para Windows y hook de PyInstaller, pero afirmarlo sin haber corrido el build seria adivinar. Es el paso 1 del HUMAN_GATE. |
| "corrieron Librarian, QA y Auditor como agentes independientes" | Fueron tres pasadas con criterios distintos dentro de la misma sesion. Se declara como es en `GATES.json`. |
