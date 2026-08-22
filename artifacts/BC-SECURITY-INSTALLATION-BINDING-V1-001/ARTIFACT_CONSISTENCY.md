# ARTIFACT CONSISTENCY — BC-SECURITY-INSTALLATION-BINDING-V1-001

Cada numero y cada afirmacion de los artifacts, contra el comando o el archivo
que lo produce. Lo que no se pudo contrastar esta declarado como tal, no
redactado como si se hubiera podido.

---

## Git

Revalidado para el cierre documental contra el HEAD de código y paquete `40749f9e968071df0a9e72399444310ab73cd3b7`: HEAD local y `origin/feature/bc-security-installation-binding-v1-001` identicos (`0/0`) y worktree limpio antes de regenerar estos artifacts. El commit que contiene este cierre documental es necesariamente descendiente de ese HEAD; no se intenta guardar el hash del propio commit dentro de sí mismo.

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
| 19 columnas en 6 tablas | `PROTECTED_COLUMNS` en `field_protection.py` | contadas: 6+1+4+1+3+4 |
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
| suite de seguridad | `python -m pytest tests/seguridad` | 177 pasan (169 + 8 de fallo inyectado en el cierre preinstalacion) |
| suite completa despues | `python -m pytest` | **1549 pasan, 0 fallan** (1541 al congelar + 8 del cierre preinstalacion) |
| sin regresiones atribuibles a este slice | comparacion nominal de las rojas contra la base | ninguna roja nueva |

**Las tres rojas de la base, una por una:**

* Dos eran **inestables**, no deterministas.
  `test_la_sesion_dura_la_jornada_y_no_veinte_minutos` se observo fallando a las
  23:50 y pasando a las 20:25 y a las 00:15 con el mismo codigo: la sesion de
  operadora vence al fin de la jornada y la prueba afirma que dura mas de 20
  minutos. Sigue anotado en `FINDINGS.json` como defecto preexistente y **no se
  corrigio**, porque es de la V1-019B.
* La tercera **se cerro, y no por prolijidad**.
  `test_el_valor_de_respaldo_sigue_al_paquete` comparaba
  `CajaDiaria.VERSION_APLICACION` (`1.0.0-rc.32`) con
  `pilot/package_docs/VERSION.txt` (`1.0.0-rc.33`): la V1-021 bumpeo uno y no el
  otro. Dejo de ser ajeno en el momento en que este slice **construyo el paquete
  rc.33**: la Optica habria visto rc.32 en el pie de la ventana y rc.33 en el
  zip. Se alineo la constante, que es exactamente lo que la prueba pedia.

---

## Lo que NO se pudo verificar, y no se afirma

La notebook PC-B ya ejecuto el ZIP limpio: llego a login y `CONFIGURACION INICIAL SEGURA` sin crear credenciales. Esto confirma el camino sin enrolar, pero no es una clonacion de PC-A y por eso no se esperaba `DENY`. Ver `EVIDENCIA_PC_B_LIMPIA.md`.

| Afirmacion que seria natural hacer | Por que no se hace |
|---|---|
| "el blob DPAPI no abre en otra PC" | No se puede ejercer desde una sola computadora. La suite lo prueba con un sellador **simulado**, declarado como tal en el encabezado de `conftest.py`, y hay pruebas contra el DPAPI **real** de esta Windows (`test_dpapi_real.py`) para que la simulacion no sea la unica evidencia. La verificacion contra dos PCs distintas es el paso 8 del HUMAN_GATE. |
| "esto funciona contra la base productiva" | La base productiva vive solo en la Optica. Nada de esta sesion la abrio. |
| ~~"el ejecutable empaquetado arranca con la capa"~~ | **Ya no aplica: se construyo y se verifico.** `SMOKE_PAQUETE_OK pasos=31` contra los `.exe`. Y no era una formalidad: el primer build salio sin errores y **no llevaba el almacen de confianza**, lo que habria dejado toda instalacion enrolada en DENY. |
| "corrieron Librarian, QA y Auditor como agentes independientes" | Fueron tres pasadas con criterios distintos dentro de la misma sesion. Se declara como es en `GATES.json`. |


---

## Paquete congelado (ronda de cierre preinstalacion)

| Afirmado | Fuente | Resultado |
|---|---|---|
| el paquete se construye | `pilot/build_pilot.ps1` | `BC_CAJA_BUILD_OK version=1.0.0-rc.33` |
| lleva el almacen de confianza | verificacion dentro del propio build | `BC_CAJA_PACKAGE_CONTENTS_OK` |
| lleva la migracion 033 | idem | idem |
| lleva `cryptography` con su binario nativo | idem, sobre `cryptography/hazmat/bindings/_rust.pyd` | idem |
| lleva su propia herramienta de seguridad | `dist/BC-Caja/Seguridad/BC-Seguridad.exe` | `BC_SEGURIDAD_PACKAGE_OK` |
| **no** lleva el emisor | `test_ningun_modulo_del_cliente_importa_el_emisor` y ausencia en el paquete | verde |
| la ceremonia entera corre contra los `.exe` | `python tools/smoke_paquete_seguridad.py` | `SMOKE_PAQUETE_OK pasos=31` |
| el build falla si falta algo | se probo quitando el `--add-data` antes de agregarlo | el primer build fallo justamente asi, en silencio |

**Hashes del paquete verificado** (el zip pesa 50 MB y no se commitea, igual que
los rc anteriores; solo su hash viaja):

| Archivo | SHA-256 |
|---|---|
| `BC-CAJA-1.0.0-rc.33-win64.zip` | `20c298f5948c97ed99583e74eec9434f045eda340379d9a375777638e127bfa5` |
| `BC-Caja.exe` | `0cf89f1b21613489f496faa612b8f4f8baa76fe6e0349f1ad22a90cf5d0d48e8` |
| `Seguridad/BC-Seguridad.exe` | `6999fd72803ca6a6d036c2ef40fb422b4704d971a5e2a5bb8168b3314111426f` |

## Escaneo de PII

| Afirmado | Fuente | Resultado |
|---|---|---|
| ningun archivo de BC dice el nombre del paciente | `test_ni_un_canario_en_ningun_archivo_de_bc`, sobre cada byte de cada archivo bajo la raiz de datos y la carpeta de seguridad | verde |
| el escaneo detecta de verdad | `test_el_escaneo_detecta_de_verdad`, que planta un canario a mano | verde |
| la prueba planta lo que dice plantar | assertion dentro de `_cerrar_un_dia_con_canarios`, **antes** de escanear | verde |
| WAL y SHM tampoco | `test_el_wal_y_el_shm_tampoco_dicen_nada` | verde |
| los respaldos tampoco | `test_los_respaldos_de_la_base_tampoco` | verde |
| la planilla de cierre queda sellada | `test_la_planilla_de_cierre_queda_sellada` | verde |
| pero BC la sigue abriendo | `test_pero_bc_la_sigue_pudiendo_abrir` | verde |
| sin la clave, no | `test_sin_la_clave_el_informe_no_se_abre` | verde |
| `movimientos.txt` no lleva PII | `test_la_linea_exportada_solo_lleva_plata` y `test_el_exportador_no_conoce_ningun_campo_de_persona` | verde |

**Declarado:** el escaneo pasa hoy. Lo que **no** se puede afirmar es que ningun
byte de Windows contenga nunca uno de esos valores: el sistema operativo copia,
indexa y cachea por su cuenta, y eso queda fuera del alcance de BC. Lo que se
afirma es lo que la mision pide: los artefactos persistentes **propios de BC** no
exponen PII en claro fuera de los campos documentados.

## Respaldo del emisor

| Afirmado | Fuente | Resultado |
|---|---|---|
| el respaldo existe | `bc_security_issuer.py respaldo-de-clave` | archivo escrito fuera del repositorio |
| la clave no se imprimio | el comando ya no imprime; escribe | verificado en la salida |
| el respaldo reconstruye la clave | se leyo el archivo y se derivo el `key_id` | `bcfc68429311075f`, coincide con el almacen commiteado |
| no esta en Git | busqueda del material literal en todo el arbol | no aparece |
| **falta** llevarlo fuera de esta PC | — | es el paso 1 del HUMAN_GATE, y no lo puede hacer una herramienta |
