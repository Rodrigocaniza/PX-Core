# BC-OPTICA-GESTION-CENTRAL-ESCENARIO-DETERMINISTA-V1-025

**Estado:** COMPLETADA_EN_CASA · una costura en producción, sin cambio de comportamiento · no requiere migración ni la PC de la Óptica

Cierra `GESTION-CENTRAL-NO-DETERMINISTA`, el segundo eje que quedaba abierto en
el mismo paquete después de que V1-024 cerrara el del root de Tk. Estaba anotado
en tres misiones —V1-019B, V1-020 y V1-021— siempre con la misma frase: «depende
de `bootstrap_synthetic_pilot()`». Nadie había dicho por qué.

## El porqué, que era la mitad que faltaba

`bootstrap_synthetic_pilot()` sembraba `source_updated_at=utc_now()`. Y
`refresh_alerts` tiene esta regla:

```python
if row and row["status"] == "OPEN" and datetime.fromisoformat(row["source_updated_at"]).hour >= 22:
    desired[(unit, "LATE_OPEN")] = ("WARNING", "Caja aún abierta fuera del horario del piloto.")
```

Las cuatro cajas del piloto quedan `OPEN`. Así que el escenario que arman los
fixtures de UI **depende de la hora en que se corra la suite**: entre las 22:00 y
las 23:59 UTC aparecen cuatro alertas `LATE_OPEN` que a las 21:00 no existen.

Y dos pruebas se caen, porque cuentan con que hay exactamente una alerta:

```
FAILED test_ui_interactions.py::test_refresh_and_filters_have_visible_feedback
FAILED test_ui_interactions.py::test_alert_selection_acknowledgement_and_restart_persistence
```

Las 22:00–23:59 UTC son las 18:00–20:00 en Paraguay. Una hora perfectamente
normal para correr pruebas, y por eso el fallo parecía aleatorio: no lo era, era
vespertino.

## Lo que se hizo

`bootstrap_synthetic_pilot()` acepta ahora `source_updated_at` opcional. Por
omisión sigue siendo `utc_now()` y el piloto se comporta exactamente igual —hay
una prueba que lo fija—. Es una costura, no una opción de producto, y tiene
precedente en la misma clase: `refresh_alerts` ya recibía su propio `now` por
esta misma razón.

Los dos fixtures de UI del paquete siembran su escenario en un instante fijo,
`2099-01-15 14:00 UTC`, del mismo año en que ya vivía su `business_date`.

## Lo que se agregó

Tres pruebas. La primera es la que más faltaba: **`LATE_OPEN` no tenía ni una
prueba**. Ahora está escrita tal como se comporta —salta a las 22 y 23, y en
ninguna otra hora—, así que la regla dejó de ser invisible. Las otras dos fijan
que el escenario de los fixtures es uno solo y que la costura no cambió el
comportamiento por omisión.

## Verificación

| | reloj normal | reloj a las 22:30 UTC |
| --- | --- | --- |
| antes | 32 passed | **2 failed**, 30 passed |
| después | 35 passed | 35 passed |

El reloj se movió parcheando `utc_now` en el módulo desde un plugin temporal, se
corrió el paquete, y el plugin se borró. Es el mismo experimento antes y después.

## Lo que se encontró y NO se arregló

`LATE_OPEN` lee `.hour` del timestamp **sin normalizar el huso**. La línea de al
lado, la de `SYNC_STALE`, sí hace `.astimezone(timezone.utc)` antes de comparar.
Si el snapshot llega en UTC, «las 22» son las 19:00 en Paraguay, y el mensaje
dice «fuera del horario del piloto», que es una frase sobre hora local.

No se tocó, por dos razones: decidir qué significa «el horario del piloto» y en
qué huso se mide es una decisión de negocio, y hoy no afecta a la Óptica —
`ingest_snapshot` no tiene ningún productor real: el camino productivo es
`real_sync.import_snapshot`, que no pasa por acá—. Queda como finding
`LATE-OPEN-LEE-LA-HORA-SIN-HUSO`, con la prueba que lo deja documentado.
