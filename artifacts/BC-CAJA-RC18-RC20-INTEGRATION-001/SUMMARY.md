# BC Caja — Integración RC18 → RC19 → RC20

Base canónica: `78839013ed28dc7ba4888565886e8b9d838c3c4e` (RC20 CLOSED).
Rama de integración: `release/bc-caja-rc18-rc20-integration-001`.

## Estrategia: reutilizar la linealidad, no fusionar

El grafo real resultó **lineal puro**:

```
0934471 RC17
  └─ 3cda622 → fdac03a  RC18 CLOSED
       └─ 6b96c80 → c4e5344  RC19 CLOSED
            └─ 239e01b → 7883901  RC20 CLOSED
```

`merge-base --is-ancestor` confirma RC18 ⊂ RC19 ⊂ RC20, con 6 commits
exclusivos sobre RC17 y **0 behind**. Las tres ramas estaban `0/0` con origin.

Por eso la integración **no hace merge**: la rama nace en el tip de RC20. No
se duplica ningún commit, no se reescribe ninguna rama CLOSED, no hay
force-push y no se arrastra nada ajeno. La integración aporta un único commit
funcional propio.

## Ajuste funcional autorizado

Ventana por defecto de candidatos de Pilar: de `solo hoy` a **hoy y los dos
días previos**. Si la consulta fue el viernes y Nidia arma el lote el sábado,
los trabajos aparecen sin tocar el selector.

- `TrackingService.DEFAULT_CANDIDATE_DAYS = 3` y `default_candidate_range()`.
- El diálogo precarga Desde/Hasta con esa ventana y **sigue siendo editable**:
  un rango explícito manda siempre sobre el default.
- **El criterio canónico no cambió**: sigue siendo la fecha de creación del
  pedido, no la de entrega. Hay una prueba que lo fija explícitamente.

## Verificación de integración

- Regresión canónica: **336 PASS, 0 FAIL** (RC20 dejó 327; la integración
  suma 9).
- Smoke GUI real en 1920×1080 y 1366×768 para **RC18, RC19 y RC20**, los seis
  en verde sobre la rama integrada.
- Migraciones: cadena completa 001–017, `integrity_check=ok`, `migrate()`
  idempotente.
- **Migración validada contra la base real de producción**: sobre una copia
  hecha con la API de backup de SQLite, 015 → 017 sin pérdida —6 cajas, 8
  movimientos, 2 pedidos, 1 outbox, 1 arqueo idénticos antes y después— y con
  el archivo productivo intacto.

## Áreas sensibles: verificado por diff, no por afirmación

`git diff --name-only 0934471 HEAD` sobre `models.py`, `services.py`,
`admin_ops.py`, `close_report.py`, `continuous_report.py`, `carry_forward.py`,
`backup.py` y `movements_exporter.py` devuelve **vacío**. Ninguna lógica
económica, de correo, cierre, arqueo o convenio fue tocada en toda la cadena.
El filtro por `comunicacion|factufacil` también devuelve vacío.

Lo único modificado fuera de lo nuevo: `sqlite_repository.py` y
`ui/controller.py` (solo agregados), `CajaDiaria.py` (UI) y pruebas de
contrato adaptadas.

## Regla operativa de privacidad en capturas

Queda registrada como regla de la plataforma, aplicada ya en
`tools/capture_caja_rc20.py`:

- para diálogos y ventanas menores, capturar **solo el bounding box** del
  target, nunca el escritorio;
- no versionar contenido de otras aplicaciones;
- ante duda, fail-closed: no publicar la captura.

RC18 y RC19 capturan la ventana principal de Caja, que a 1920×1080 ocupa la
pantalla completa, de modo que sus capturas existentes ya son seguras y **no
se reabren**. No se hizo refactor de tooling: la corrección puntual en RC20
era suficiente para eliminar la exposición real.

## Instalación

Preparada, **no ejecutada**: requiere el gate humano consolidado según la
política canónica de BC Caja establecida en RC17. Instalado actualmente:
`BC Caja 1.0.0-rc.17` en `%LOCALAPPDATA%\Programs\BC-Caja-Pilot`, con
rollbacks RC15 y RC16 íntegros.
