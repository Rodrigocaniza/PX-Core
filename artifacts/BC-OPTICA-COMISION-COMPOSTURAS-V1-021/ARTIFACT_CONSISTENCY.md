# ARTIFACT CONSISTENCY — BC-OPTICA-COMISION-COMPOSTURAS-V1-021

Cada numero y cada afirmacion de los artifacts, contra el comando o el archivo
que lo produce. Lo que no se pudo contrastar esta declarado como tal.

---

## Git

| Afirmado | Fuente | Resultado |
|---|---|---|
| branch `feature/bc-optica-comision-composturas-v1-021` | `git rev-parse --abbrev-ref HEAD` | coincide |
| base `feature/bc-optica-trabajos-operativos-v1-020 @ d44785f` | `git worktree list` y `git log --oneline -1` | coincide |
| `feature/bc-optica-login-operadora-v1-019b @ de767d9` | `git rev-parse` | coincide |
| 019b es ancestro de 020 | `git merge-base --is-ancestor` | exit 0 |
| `origin/main @ 7db56a0` | `git rev-parse origin/main` | coincide |
| main no tocado | no se ejecuto checkout, merge ni push sobre main | verdadero |
| worktree propio | `git worktree add -b ... .worktrees/optica-comision-021` | creado en esta sesion |

## Migracion

| Afirmado | Fuente | Resultado |
|---|---|---|
| la 031 era la ultima antes de este slice | `ls migrations/` en el worktree de 020 | 031 es la mayor |
| la 032 se aplica y la cadena queda entera | `test_la_032_se_aplica_y_la_cadena_queda_entera` | verde |
| `service_commission_policy` ya no existe | `test_la_politica_vieja_de_una_sola_fila_ya_no_existe` | verde |
| no nombra ventas, stock ni caja | `test_la_032_no_toca_ventas_ni_stock_ni_caja`, que lee el .sql descartando comentarios | verde |
| un solo `ALTER TABLE` | mismo test, `sql.count("ALTER TABLE") == 1` | verde |
| el backfill conserva lo cargado por la 031 | `test_lo_que_la_031_habia_cargado_se_conserva_como_primera_version`, que corta la cadena en la 031, carga una fila con la forma vieja y deja correr la 032 | verde |
| append-only | `test_una_version_de_politica_no_se_reescribe_ni_se_borra` | verde |
| no aplicada en produccion | ningun comando de esta sesion abrio la base de la Optica | verdadero |

**Declarado explicitamente:** la 032 **no** es estrictamente aditiva. La V1-020
pudo afirmarlo de la 031 y aca seria falso. El motivo esta en `MANIFEST.json` y
en el encabezado del propio `.sql`.

## Comportamiento

| Afirmado | Prueba |
|---|---|
| solo ADMIN administra politica | `test_una_operadora_no_puede_definir_una_comision`, `test_sin_sesion_no_se_administra_la_politica` |
| el intento denegado queda auditado | `test_el_intento_denegado_queda_en_la_bitacora` |
| la identidad es el user_id, no el nombre | `test_la_politica_se_guarda_contra_el_identificador_y_no_contra_el_nombre` |
| cero difiere de no tener politica | `test_cero_es_una_politica_valida_y_distinta_de_no_tener_ninguna` |
| una tarifa futura no rige antes de tiempo | `test_una_politica_con_fecha_futura_todavia_no_rige` |
| subir la tarifa no reescribe lo devengado | `test_subir_la_tarifa_no_reescribe_lo_que_ya_se_devengo` |
| se puede reconstruir la politica de un devengo viejo | `test_la_politica_de_un_devengo_viejo_se_puede_reconstruir` |
| sin politica no se inventa comision | `test_sin_politica_no_se_inventa_comision_ni_deuda` |
| la ausencia de politica es visible | `test_la_ausencia_de_politica_queda_visible_en_la_bitacora`, `test_los_trabajos_que_no_devengaron_se_listan_aparte` |
| el doble click no paga dos veces | `test_marcar_listo_dos_veces_no_paga_dos_veces` |
| el retry no duplica | `test_reintentar_el_mismo_hecho_no_duplica_el_asiento` |
| rehacer devenga de nuevo, a proposito | `test_rehacer_un_trabajo_devenga_de_nuevo_porque_se_hizo_de_nuevo` |
| anular compensa y el neto cierra | `test_anular_un_trabajo_compensa_en_vez_de_borrar`, `test_el_neto_despues_de_compensar_es_cero_y_no_desaparece` |
| doble compensacion bloqueada | `test_un_devengo_no_se_puede_compensar_dos_veces` |
| cero inventario y cero caja | `test_administrar_una_comision_no_mueve_inventario_ni_caja`, `test_devengar_y_compensar_no_mueven_inventario_ni_caja`, `test_una_comision_devengada_no_es_un_gasto_ni_una_salida_de_caja` |
| cero contaminacion del 1% | `test_la_comision_de_compostura_no_toca_la_comision_comercial`, `test_el_modulo_de_comision_no_importa_nada_del_nucleo_comercial`, `test_una_venta_normal_no_genera_comision_de_compostura`, `test_crear_una_compostura_no_genera_ninguna_comision` |
| no se invento liquidacion | `test_no_hay_estado_de_liquidacion_porque_todavia_no_hay_pago` |
| los cuatro filtros del reporte | `test_el_reporte_filtra_por_sucursal`, `..._por_responsable`, `..._por_rango_de_fechas`, `..._por_estado` |
| los totales cuadran con las filas | `test_los_totales_cuadran_con_las_filas_que_se_muestran` y su equivalente de UI |
| el panel no autoriza por su cuenta | `test_el_panel_de_comisiones_no_decide_permisos_por_su_cuenta`, `test_el_panel_no_puede_leerse_con_una_sesion_de_operadora` |

## Numeros

| Afirmado | Comando | Resultado |
|---|---|---|
| 68 dirigidas de servicio | `pytest test_v1021_comision_composturas.py --collect-only` | `68 tests collected` |
| 9 dirigidas de UI | `pytest test_v1021_panel_comisiones_ui.py --collect-only` | `9 tests collected` |
| 77 en total | suma de las dos | 77 |
| suite completa 1365 | `pytest -q` | `1365 passed` |
| suite antes del slice 1288 | `pytest -q` sobre el worktree recien creado, antes de tocar codigo | `1288 passed` |
| 1365 = 1288 + 77 | aritmetica | cierra exacto |
| `+8 / -1` en `CajaDiaria.py` | `git diff --numstat CajaDiaria.py` | `8 1 CajaDiaria.py` |
| hashes de `MANIFEST.json` | `sha256` de cada archivo | tomados despues del ultimo cambio de codigo |

## Lo que NO se puede afirmar

- **No corrio un ChainState externo.** No existe un runner en este repo. La
  cadena se ejecuto como revision disciplinada en esta sesion.
- **Librarian, QA y Auditor no son tres identidades independientes.** Fueron tres
  pasadas con criterios distintos, en la misma sesion.
- **No hubo canary ni operacion real.** Estamos en Casa.
- **La politica real no esta cargada.** No hay personas reales en esta base: los
  5.000 Gs del enunciado aparecen solo como constante de prueba, nunca en codigo
  productivo.
