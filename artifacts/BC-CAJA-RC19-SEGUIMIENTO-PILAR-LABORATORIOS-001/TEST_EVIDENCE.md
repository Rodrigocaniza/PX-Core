# Test Evidence — BC-CAJA-RC19-SEGUIMIENTO-PILAR-LABORATORIOS-001

Base canónica: `fdac03a`. Rama: `feature/bc-caja-rc19-seguimiento-pilar-laboratorios-001`.

## Regresión canónica

```
python -m pytest -q
293 passed, 5 warnings
```

RC18 cerró con 222 PASS / 0 FAIL. RC19 suma 71 pruebas propias.

## Cobertura de los 15 puntos de validación exigidos

| # | Validación | Prueba |
|---|---|---|
| 1 | 15 enviados / 14 recibidos → 1 faltante | `test_sabado_asuncion_recibe_catorce_y_la_pantalla_muestra_uno_faltante`, `test_quince_enviados_y_catorce_recibidos_dejan_uno_pendiente` |
| 2 | Transición Pilar → Asunción | `test_viernes_nidia_registra_quince_trabajos_enviados_desde_pilar`, `test_el_trabajo_nace_enviado_desde_pilar_y_conserva_un_unico_registro` |
| 3 | Varios laboratorios en un mismo lote | `test_el_lote_se_reparte_entre_varios_laboratorios`, `test_un_mismo_lote_se_reparte_entre_varios_laboratorios` |
| 4 | Esperado hoy y recibido a tiempo | `test_recibido_a_tiempo_no_aparece_atrasado`, `test_recibido_a_tiempo_no_queda_atrasado` |
| 5 | Vencimiento → ATRASADO | `test_al_vencer_la_hora_el_trabajo_queda_atrasado`, `test_el_vencimiento_marca_atraso_automaticamente` |
| 6 | Línea y WhatsApp distintos | `test_linea_y_whatsapp_son_independientes`, `test_guarda_y_recupera_laboratorios_con_linea_y_whatsapp_distintos`, `test_agrupa_los_atrasados_por_laboratorio_con_linea_y_whatsapp` |
| 7 | CONFIRMADO_PARA_MAÑANA elimina el atraso | `test_confirmar_para_manana_saca_el_trabajo_de_atrasados`, `test_la_confirmacion_quita_el_atraso_actual` |
| 8 | Vencimiento del nuevo plazo vuelve a ATRASADO | `test_si_el_nuevo_plazo_vence_vuelve_a_atrasados`, `test_si_el_nuevo_plazo_vence_vuelve_a_estar_atrasado` |
| 9 | Historial de contacto | `test_el_historial_de_contacto_evita_la_llamada_duplicada`, `test_acumula_las_novedades_en_orden`, `test_la_ultima_novedad_se_resume_para_la_grilla` |
| 10 | Agrupación de atrasados por laboratorio | `test_agrupa_los_atrasados_por_laboratorio_con_sus_telefonos`, `test_agrupa_los_atrasados_por_laboratorio_con_linea_y_whatsapp` |
| 11 | Recepción desde laboratorio | `test_circuito_completo_hasta_recepcion_final_en_pilar`, `test_recibir_del_laboratorio_libera_el_plazo` |
| 12 | Envío en encomienda a Pilar | `test_la_encomienda_viaja_como_lote_conservando_traza_individual` |
| 13 | Recepción final en Pilar | `test_pilar_confirma_uno_por_uno_al_dia_siguiente`, `test_circuito_completo_hasta_recepcion_final_en_pilar` |
| 14 | Transiciones inválidas rechazadas | `test_rechaza_transiciones_invalidas`, `test_un_trabajo_cerrado_no_admite_mas_transiciones`, `test_rechaza_una_transicion_fuera_de_orden`, `test_la_base_rechaza_un_estado_fuera_del_circuito` |
| 15 | Funcionamiento local sin red | `test_la_operacion_completa_no_abre_ninguna_conexion_de_red` |

## Desglose por slice

```
tests/caja_diaria/test_rc19_tracking_domain.py       33 passed
tests/caja_diaria/test_rc19_tracking_repository.py   13 passed
tests/caja_diaria/test_rc19_tracking_service.py      25 passed
```

La prueba 15 sustituye `socket.socket` por una función que lanza
`AssertionError` y luego recorre el circuito completo más el tablero: cualquier
dependencia de red haría fallar la suite, no es una afirmación documental.

## Smoke GUI real

`tools/capture_caja_rc19.py` siembra el caso operativo sobre un directorio
temporal (15 trabajos del viernes, 14 recibidos, tres laboratorios —uno
inactivo—, cuatro enviados con plazo vencido, uno confirmado para mañana, tres
ya recibidos del laboratorio), abre la ventana real, entra en Seguimiento y
verifica sobre los widgets.

```
BC_CAJA_RC19_VISUAL_SMOKE_OK resolution=1920x1080 filas=15 atrasados=3
  recepcion="Enviados: 15    Recibidos: 14    Falta recibir: 1"
  alerta="⚠  3 trabajos atrasados — contactar laboratorios"
  estados=['ATRASADO','CONFIRMADO_PARA_MAÑANA','ENVIADO_DESDE_PILAR',
           'EN_LABORATORIO','RECIBIDO_DEL_LABORATORIO','RECIBIDO_EN_ASUNCION']
  emails=0 new_closures=0

BC_CAJA_RC19_VISUAL_SMOKE_OK resolution=1366x768 ...idéntico...
```

La sonda falla si: el progreso de recepción no da 15/14/1; falta la alerta; la
agrupación no nombra el laboratorio o no expone línea y WhatsApp distintos;
falta alguna columna; la primera fila no es una excepción; una fila atrasada no
muestra teléfonos; no aparece el estado confirmado; o la última novedad no
llega a la grilla.

Nota: cuatro trabajos tienen plazo vencido pero se muestran 3 atrasados,
porque uno fue confirmado para mañana. Es exactamente el comportamiento
exigido.

## No regresión de RC18

```
BC_CAJA_RC18_VISUAL_SMOKE_OK resolution=1920x1080 kpi_principal=20
  kpi_secundario=13 cabecera_alto=55 emails=0 new_closures=0
```

## Defectos corregidos durante la misión

- La columna Estado truncaba `CONFIRMADO_PARA_MAÑANA` y
  `RECIBIDO_DEL_LABORATORIO`, detectado en la captura real: ancho ajustado al
  literal más largo y `Última novedad` pasa a expandirse.
- La sonda inicial identificaba la grilla por la columna `sobre`, que también
  existe en movimientos e historial; ahora se identifica por columnas propias.
