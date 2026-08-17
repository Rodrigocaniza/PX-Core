# BC Caja RC29 — Historial: cada jornada, una unidad visual

Ajuste **exclusivamente visual**. No se tocó el dominio, ni las fórmulas, ni
qué registros aparecen, ni su orden.

## El problema

La cabecera del día y sus movimientos eran **widgets hermanos** dentro del
scroll: nada los agrupaba salvo el padding. Y todo el encabezado —fecha,
estado, seis cifras, apertura, cierre, duración y hora extra— iba en **una
sola etiqueta**, con el mismo peso tipográfico:

```python
text=f"{cash_day.business_date.strftime('%d-%m-%Y')} · {texto_estado(cash_day)}"
```

Por eso costaba ver dónde terminaba una jornada y empezaba la siguiente.

## La corrección

Cada jornada pasa a ser una **tarjeta** de la que cuelga todo lo del día:
cabecera, resumen, detalle de sesión, movimientos y acciones. Separación de
10 px entre jornadas, fondo neutro y borde suave — sin un color por día.

Jerarquía dentro de la tarjeta:

| Nivel | Qué | Cómo |
|---|---|---|
| 1 | **Fecha** | `fuente + 3`, negrita |
| 2 | **Estado** | chip compacto: ámbar `ABIERTO` · verde `CERRADO` |
| 3 | Resumen económico | tamaño normal, contenido idéntico |
| 4 | Apertura · cierre · duración · hora extra | secundario, tenue, en una línea |
| — | `Editar caja` | alineado a la derecha, como estaba |

### Ninguna cifra cambia

`texto_estado` se partió en `estado_dia`, `resumen_economico_dia` y
`detalle_sesion_dia`, y **vuelve a componerlas exactamente igual**:

```python
texto = f"{estado_dia(cash_day)}   ·   {resumen_economico_dia(cash_day)}"
return f"{texto}\n\n{detalle}" if detalle else texto
```

Así el aviso de "Caja cerrada" no cambia una coma, las cifras siguen saliendo
de `cash_day.totals()` en un solo lugar, y Historial puede darle a cada parte
el peso visual que corresponde. Hay prueba de que el resumen conserva sus seis
rótulos y de que no se recalcula nada.

Los movimientos conservan nombre, Total, Efectivo, Tarj./Cheq., Gastos,
estado, `Editar` y `Anular`, con la misma regla de habilitación. Los anulados
mantienen su rojo y su motivo, ahora claramente dentro del día que les
corresponde.

## Validación

| # | Punto | Resultado |
|---|---|---|
| 1 | Cabecera reconocible por jornada | PASS |
| 2 | Movimientos dentro de su jornada | PASS · 0 movimientos huérfanos |
| 3 | Jornadas consecutivas se distinguen | PASS · tarjeta + 10 px |
| 4 | Jornada ABIERTA clara | PASS · chip ámbar, 1 de 3 |
| 5 | Jornada CERRADA clara | PASS · chip verde, 2 de 3 |
| 6 | Anulados visibles y agrupados | PASS · el anulado queda en `15-08` y en ninguna otra |
| 7 | `Editar caja` / `Editar` / `Anular` | PASS · presentes y alineados |
| 8 | Ninguna cifra cambia | PASS · `700.000`, `450.000`, `980.000`, `120.000` se leen tal cual |
| 9 | Mismo orden cronológico | PASS · sin `sorted`/`reversed` nuevos |
| 10 | Scroll correcto | PASS · sigue en un único `CTkScrollableFrame`, sin paginación |
| 11 | 1920×1080 | PASS |
| 12 | 1366×768 | PASS |

Los filtros superiores (Desde, Hasta, Caja, Consultar, Este mes, 7 días, Hoy)
quedaron intactos; hay prueba de que no se coló ningún DatePicker.

## Gates

| Gate | Resultado |
|---|---|
| Regresión completa | **622 PASS / 0 FAIL** |
| Focused RC28 + RC29 | 43 PASS |
| Smoke GUI RC29 1920×1080 y 1366×768 | PASS |
| Smoke GUI RC28 (Pedidos) 1920×1080 y 1366×768 | PASS · `abre=['2999','0239']` |
| Smoke GUI RC27 · RC19 (Seguimiento) | PASS |
| Reuso de filas | `0 destruidos / 0 creados` |
| Correos / cierres nuevos | 0 / 0 |

Un test ajustado a propósito: `test_rc4_never_displays_open_status_in_english`
buscaba la traducción con comillas simples en su ubicación anterior. La regla
—nunca mostrar `OPEN`/`CLOSED`— no cambia; ahora se verifica en `estado_dia`,
que es la única que decide el rótulo.

## Build consolidada

**`BC Caja 1.0.0-rc.27`** — un solo paquete con `fix Pedidos (RC28)` +
`Historial por jornada (RC29)`. `rc.27` verificado libre antes de construir.

| Item | Valor |
|---|---|
| ZIP | `releases/BC-CAJA-1.0.0-rc.27-win64.zip` · 34.681.629 B · 1161 entradas |
| SHA256 ZIP | `AB2F19AAE6DDD193DB4892E33B8164B34EC583C7CC14AE0AFADB39ADC336D03B` |
| SHA256 EXE | `A6A494C27685B33501B4823156D459E581A21EAFC27B6430C890FAB4554592F9` |
| Migraciones | 21 — **sin migración nueva**, el esquema sigue en 021 |
| Smoke del EXE | arranca · `integrity_check=ok` · `foreign_key_check=ok` · esquema 001–021 |

### Rollback previsto

Producción está en **`rc.26`**; se preserva como rollback
(`BC-Caja-Pilot.rollback-rc26-<stamp>`), junto a rc.25, rc.24, rc.23, rc.22,
rc.21, rc.20, rc.17, rc.16 y rc.15. Backup del data root con la API de backup
de SQLite —la base está en WAL— antes de reemplazar.

**No instalada**: la política vigente exige HUMAN_GATE. Queda lista.

## No tocado

Lógica económica, Seguimiento, circuito Pilar, FactuFácil, DatePicker global,
correo, cierres, arqueos, convenios y Comunicaciones.
