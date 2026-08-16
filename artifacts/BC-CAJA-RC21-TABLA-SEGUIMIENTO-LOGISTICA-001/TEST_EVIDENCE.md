# Test Evidence — BC-CAJA-RC21-TABLA-SEGUIMIENTO-LOGISTICA-001

Base: `8b11c78`. Rama: `feature/bc-caja-rc21-tabla-seguimiento-logistica-001`.

## Regresión canónica

```
python -m pytest -q
370 passed, 5 warnings
```

La integración RC18–RC20 dejó 339. RC21 suma 31.

## Cobertura de los 13 puntos exigidos

| # | Validación | Prueba |
|---|---|---|
| 1 | `Vendedora` ausente | `test_vendedora_ya_no_se_muestra_en_seguimiento`, `test_el_dato_de_vendedora_sigue_existiendo_en_el_dominio` |
| 2 | `Laboratorio` visible | `test_laboratorio_va_inmediatamente_despues_de_tipo_de_trabajo`, `test_una_vez_asignado_muestra_el_nombre` |
| 3 | `SIN ASIGNAR` | `test_sin_laboratorio_asignado_muestra_sin_asignar` + smoke GUI |
| 4 | Los seis estados canónicos | `test_los_seis_estados_canonicos_tienen_rotulo_legible`, `test_recorre_los_seis_estados_mostrando_la_etapa_real` |
| 5 | `RECIBIDO EN PILAR` cierra | `test_recibido_en_pilar_cierra_el_circuito_sin_mostrarse_cerrado`, `test_cerrado_no_es_un_estado_visible_del_circuito` |
| 6 | ATRASADO mantiene estado real | `test_atrasado_antepone_pero_conserva_la_etapa_fisica` |
| 7 | CONFIRMADO mantiene estado real | `test_confirmado_antepone_pero_conserva_la_etapa_fisica` |
| 8 | Contacto del laboratorio accesible | `test_el_contacto_del_laboratorio_sigue_accesible` |
| 9 | 1920×1080 | `test_las_cinco_columnas_entran_sin_scroll_horizontal_en_1920` + smoke real |
| 10 | 1366×768 | `test_tambien_entran_en_el_ancho_compacto_de_1366` + smoke real |
| 11 | RC18 sin regresión | smoke RC18 PASS |
| 12 | RC19 sin regresión | suite RC19 completa + smoke de la tabla |
| 13 | RC20 sin regresión | suite RC20 completa + smoke RC20 PASS |

Extra: `test_ninguna_condicion_derivada_se_persiste` fija que la base nunca
almacena `ATRASADO` ni `CONFIRMADO_PARA_MAÑANA`, sosteniendo la decisión de
RC19 desde la capa de datos.

## Smoke GUI real de la tabla

```
BC_CAJA_RC19_VISUAL_SMOKE_OK resolution=1920x1080 filas=15 atrasados=3
  estados=['ATRASADO · EN LABORATORIO',
           'CONFIRMADO PARA MAÑANA · EN LABORATORIO',
           'EN LABORATORIO', 'ENVIADO DESDE PILAR',
           'RECIBIDO DEL LABORATORIO', 'RECIBIDO EN ASUNCIÓN']
  emails=0 new_closures=0
BC_CAJA_RC19_VISUAL_SMOKE_OK resolution=1366x768 ...idéntico...
```

La sonda falla si las columnas no son exactamente las cinco pedidas, si
aparece `vendedora`, si la alerta borra la etapa física, si la fila atrasada
no muestra su laboratorio, si no aparece `SIN ASIGNAR` o si Tipo de trabajo
llega vacía.

## No regresión

```
BC_CAJA_RC18_VISUAL_SMOKE_OK  kpi_principal=20 kpi_secundario=13 cabecera_alto=55
BC_CAJA_RC20_VISUAL_SMOKE_OK  candidatos=15 seleccion_parcial=3 laboratorios=2
```

## Defectos corregidos durante la misión

- El texto del Treeview asomaba junto al chip: el contenedor pasa a ser opaco
  y a cubrir la celda completa.
- La sonda de RC19 recortaba región de pantalla y a 1366×768 capturó una
  franja de otra aplicación. Detectado al revisar la evidencia antes de
  commitear; la imagen no se versionó y las tres sondas migraron a
  `tools/gui_capture.py` con `PrintWindow`.
