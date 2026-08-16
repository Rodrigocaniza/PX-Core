# Test Evidence — BC-CAJA-RC18-RC20-INTEGRATION-001

## Grafo verificado antes de tocar nada

```
git merge-base --is-ancestor RC18 RC19  -> 0
git merge-base --is-ancestor RC19 RC20  -> 0
git rev-list --left-right --count RC17...RC20 -> 0  6
```

Ramas y sincronización con origin al momento de integrar:

| Rama | HEAD | Upstream |
|---|---|---|
| RC18 | `fdac03a` | `0/0` |
| RC19 | `c4e5344` | `0/0` |
| RC20 | `7883901` | `0/0` |

RC20 HEAD coincide con el esperado `78839013ed28dc7ba4888565886e8b9d838c3c4e`.

## Regresión canónica sobre la rama integrada

```
python -m pytest -q
336 passed, 5 warnings
```

RC20 cerró con 327. La integración suma 9 pruebas del nuevo default.

## Focused tests del cambio de rango

`tests/caja_diaria/test_rc18_rc20_integration.py` — 9 PASS:

- el rango por defecto cubre hoy y los dos días previos;
- la consulta del viernes aparece el sábado sin tocar el selector;
- incluye hoy y el límite de tres días;
- deja fuera lo anterior a la ventana;
- un rango explícito manda sobre el default;
- una sola fecha explícita sigue siendo un único día;
- **el criterio sigue siendo la fecha de creación, no la de entrega** (el
  pedido tiene entrega fuera de la ventana y aun así aparece);
- el default no mezcla otras sucursales;
- el diálogo precarga la ventana por defecto.

## Smoke GUI real sobre la rama integrada

Las tres misiones, en las dos resoluciones, todas con `emails=0` y
`new_closures=0`:

```
RC18  1920x1080  kpi_principal=20 kpi_secundario=13 cabecera_alto=55
RC18  1366x768   kpi_principal=11 kpi_secundario=9  cabecera_alto=44
RC19  1920x1080  filas=15 atrasados=3 "Enviados: 15 Recibidos: 14 Falta recibir: 1"
RC19  1366x768   idéntico
RC20  1920x1080  candidatos=15 seleccion_parcial=3 laboratorios=2
RC20  1366x768   idéntico
```

## SQLite y migraciones

```
migraciones: 001..017 | total: 17
integrity_check: ok
tablas del seguimiento: laboratories, pilar_shipments,
  tracked_work_contacts, tracked_work_transitions, tracked_works
migrate() idempotente: ok
```

### Migración contra la base real de producción

Sobre una copia obtenida con la API de backup de SQLite, sin abrir en
escritura el archivo productivo:

```
ANTES   migraciones 001..015
ANTES   cash_days=6 cash_entries=8 orders=2 mail_outbox=1 cash_count_snapshots=1
DESPUES migraciones 001..017
DESPUES cash_days=6 cash_entries=8 orders=2 mail_outbox=1 cash_count_snapshots=1
DATOS PRESERVADOS: True
MIGRACIONES NUEVAS: ['016', '017']
PROD INTACTA: True (270336 bytes)
```

## Áreas que no debían tocarse

`git diff --name-only 0934471 HEAD` restringido a lógica económica, correo,
cierres, arqueos y convenios devuelve **vacío**:

```
models.py, services.py, admin_ops.py, close_report.py,
continuous_report.py, carry_forward.py, backup.py, movements_exporter.py
  -> sin cambios en toda la cadena RC17→integración
```

Filtro `comunicacion|factufacil` sobre el diff completo: **vacío**.
