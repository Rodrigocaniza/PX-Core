# Test Evidence — BC-CAJA-RC20-ALTA-LOTE-PILAR-ABM-LABORATORIOS-001

Base canónica: `c4e5344`. Rama: `feature/bc-caja-rc20-alta-lote-pilar-abm-laboratorios-001`.

## Regresión canónica

```
python -m pytest -q
327 passed, 5 warnings
```

RC19 cerró con 293 PASS / 0 FAIL. RC20 suma 34 pruebas propias.

## Cobertura de los 18 puntos de validación exigidos

| # | Validación | Prueba |
|---|---|---|
| 1 | Encontrar trabajos de Pilar por fecha/consulta | `test_encuentra_los_trabajos_de_la_consulta_de_pilar`, `test_encuentra_los_trabajos_de_pilar_por_fecha`, `test_fuera_del_rango_no_hay_candidatos`, `test_no_mezcla_otras_sucursales` |
| 2 | Seleccionar todos | `test_seleccionar_todos_crea_el_lote_completo` + smoke GUI (`Seleccionar todos` → 15/15) |
| 3 | Selección parcial | `test_seleccion_parcial_crea_solo_lo_elegido` + smoke GUI (3 clics reales → 3 marcadas) |
| 4 | Crear lote con N trabajos | `test_el_lote_registra_origen_destino_operadora_y_cantidad` |
| 5 | No duplicar trabajos ya enviados | `test_no_permite_enviar_dos_veces_el_mismo_trabajo`, `test_un_trabajo_ya_enviado_deja_de_ser_candidato` |
| 6 | Conservar relación con `orders` | `test_conserva_la_relacion_con_orders_y_con_la_venta`, `test_el_trabajo_conserva_su_enlace_al_lote_y_al_pedido`, `test_no_crea_otra_fuente_de_verdad_del_cliente` |
| 7 | Recepción uno por uno sigue funcionando | `test_la_recepcion_uno_por_uno_de_rc19_sigue_funcionando`, `test_cada_trabajo_sigue_siendo_trazable_individualmente` |
| 8 | Faltantes correctos | `test_la_recepcion_uno_por_uno_de_rc19_sigue_funcionando` (15/14/1), `test_al_recibir_todo_el_lote_queda_completo`, `test_la_condicion_del_lote_se_deriva_de_sus_trabajos` |
| 9 | Alta laboratorio | `test_alta_de_laboratorio` + smoke GUI |
| 10 | Edición nombre | `test_edicion_de_nombre` + smoke GUI |
| 11 | Edición línea | `test_edicion_de_linea_no_toca_el_whatsapp` |
| 12 | Edición WhatsApp | `test_edicion_de_whatsapp_no_toca_la_linea` |
| 13 | Línea != WhatsApp | `test_linea_y_whatsapp_pueden_ser_numeros_distintos` + smoke GUI |
| 14 | Desactivar laboratorio | `test_desactivar_un_laboratorio`, `test_reactivar_devuelve_el_laboratorio_a_las_opciones` + smoke GUI |
| 15 | Histórico conserva laboratorio inactivo | `test_el_historico_conserva_el_laboratorio_inactivo` |
| 16 | Inactivo no elegible para nuevo trabajo | `test_un_laboratorio_inactivo_no_es_elegible_para_un_envio_nuevo` |
| 17 | Operación local-first | `test_alta_de_lote_y_abm_no_requieren_red` |
| 18 | RC19 sin regresión | suite RC19 completa en verde + smoke RC19 reejecutado |

## Desglose por slice

```
tests/caja_diaria/test_rc20_shipment_repository.py   11 passed
tests/caja_diaria/test_rc20_shipment_service.py      23 passed
```

La prueba 17 inutiliza `socket.socket` y luego ejecuta ABM completo, búsqueda
de candidatos, creación del lote y recepción: cualquier dependencia de red
rompería la suite.

## Smoke GUI real

`tools/capture_caja_rc20.py` siembra una consulta de Pilar con 15 ventas ya
cargadas en Caja, abre la ventana real, entra en Seguimiento y **ejercita los
dos diálogos contra los widgets**, no contra el servicio.

Envío desde Pilar, comprobado: aparecen los 15 candidatos; el resumen dice
`15 trabajos encontrados · 0 seleccionados`; `Crear envío` nace deshabilitado;
`Seleccionar todos` marca las 15 y el botón pasa a `Crear envío (15)`;
`Quitar selección` limpia las marcas; tres clics reales sobre filas dejan
exactamente 3 marcadas.

ABM de laboratorios, comprobado: alta desde el formulario reflejada en la
grilla, con línea y WhatsApp distintos y estado `ACTIVO`; edición de nombre
reflejada sin perder el teléfono de línea; desactivación que cambia el estado
a `INACTIVO` **sin borrar la fila**.

```
BC_CAJA_RC20_VISUAL_SMOKE_OK resolution=1920x1080 candidatos=15
  seleccion_parcial=3 laboratorios=2 emails=0 new_closures=0
BC_CAJA_RC20_VISUAL_SMOKE_OK resolution=1366x768 ...idéntico...
```

Capturas: `envio-1920x1080.png`, `laboratorios-1920x1080.png`,
`envio-1366x768.png`, `laboratorios-1366x768.png`. Recortadas al rectángulo del
diálogo.

## No regresión

```
BC_CAJA_RC19_VISUAL_SMOKE_OK resolution=1920x1080 filas=15 atrasados=3
  recepcion="Enviados: 15    Recibidos: 14    Falta recibir: 1"
BC_CAJA_RC18_VISUAL_SMOKE_OK resolution=1920x1080 kpi_principal=20
  kpi_secundario=13 cabecera_alto=55
```
