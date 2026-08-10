# BC-CAJA-DISCOVERY-001 — Canonical Discovery & Baseline

Fecha del snapshot: 2026-08-10 (America/Asuncion)

Estado: DISCOVERY_COMPLETADO / IMPLEMENTACION_NO_INICIADA

## 1. CANONICAL_SNAPSHOT

- Repo de producto desde el cual continuar: `C:\Users\Striker\Desktop\Proyecto X\PX-Core`.
- Worktree: checkout principal de PX-Core.
- Branch: `feature/caja-diaria`, siguiendo `origin/feature/caja-diaria`.
- HEAD: `92a15f046ac652fa83d1b81a5411b6bbe363fee8`.
- Estado Git observado: limpio.
- Commits de origen de Caja Diaria: `7a5585486db7d3a6a9e4119291f12eefdcf844e7` y ajuste `fd07cde`.
- BC-Core/Command Center: checkout principal `wip/traslado-optica-20260808@7eedf0b808621bb3e5f17985b102672a0ddbdc84`, con cambios ajenos preexistentes; no debe usarse como writer ni limpiarse. La versión más avanzada disponible está en `main@8364265418b22c682bcb6b60a9fa85257e5dccc6` y en worktrees SOFA asociados.
- BC-Core reconoce PX-Core/BC Gestión y Caja Diaria como producto legacy independiente. No autoriza copiar Caja dentro de BC-Core.
- `BC-CAJA-DISCOVERY-001` no tenía `WORKFLOW.json`, lease ni artifacts previos. No había writer registrado para Caja.
- No se observaron leases activos en `.git/command-center/mission-execution-leases`.
- Command Center main contiene Continuous Session, Auto-Resume, Workflow Engine, Mission Lease, Role/State Binding, Artifact Consistency, handoffs, Librarian → QA → Auditor, Safe Closure y commit/push protegidos.
- Limitación de integración: el Command Center actual no es portable sin cambios a PX-Core; al recibir PX-Core como `repository-root`, su verificación espera allí la suite y `docs/progress` propios de BC-Core. No se creó un `WORKFLOW.json` artificial ni se registraron gates manualmente.

## 2. EXISTING_ASSETS

| Activo | Función/estado comprobado | Clasificación |
|---|---|---|
| `CajaDiaria.py` | Módulo histórico de 678 líneas, integrado; importa XLSX, carga manual, cierre y arqueo. Mezcla UI, dominio, parsing y TXT; sin tests. | ADAPTAR |
| `interfaz.py` | Importa CajaDiaria y expone “Abrir caja diaria”. UI CustomTkinter operativa como patrón existente. | REFERENCIA |
| `Datos/caja_diaria.txt` | Persistencia prevista, actualmente vacía (0 bytes). | DESCARTAR como persistencia; REFERENCIA de formato |
| `Datos/arqueo_caja.txt` | No existe todavía. | DESCARTAR como evidencia operativa |
| `ImportadorExcel.py` | Provee `normalizar`, `celda_vacia`, `parsear_fecha`, `parsear_monto`, `texto_seguro`; archivo completo acoplado a BC Gestión. | ADAPTAR helpers |
| `Movimientos.py` y `Datos/movimientos*.txt` | Destino futuro explícito en TODO de CajaDiaria; no integrado hoy. | REFERENCIA |
| `Informes.py` | Patrones de Excel/PDF e informes del monolito. | REFERENCIA futura |
| `Respaldos/BC_Gestion_2026-08-03.zip` | Incluye solo `Datos/caja_diaria.txt`, sin implementación ni datos. | REFERENCIA |
| `Plantilla_Carga_Mensual_BC_Gestion.xlsx` | Plantilla de Movimientos/Adicionales/etc.; SHA256 `E8D27736D5029DD22DEB3838A25E45BDB13CA8706199751AFE6D5F8164647108`. No es Caja. | REFERENCIA |
| BC-Consultorio | Patrón probado Python/Tkinter + application/services + repository contracts + SQLite + composition root. No contiene Caja. | REFERENCIA ARQUITECTÓNICA |
| BC-Inventario-Control | Patrón Tkinter + SQLite/WAL; su Excel es inventario, no Caja. | REFERENCIA TÉCNICA |
| BC-Finanzas | Conciliación bancaria/tarjetas y cierre de período, bounded context distinto. | REFERENCIA futura |
| BC-Core | Gobierno/Command Center; sin implementación Caja y con prohibición de absorber legacy sin decisión aprobada. | REFERENCIA OPERATIVA |

No existe `modulos/caja_diaria/`, paquete equivalente, otra implementación Caja en los repositorios revisados ni referencias a Puppilent.

## 3. CONTRATO EXCEL OBSERVABLE

`Agosto PC 2026.xlsx` no está dentro de ningún repo/worktree/directorio accesible del workspace. No se afirma que no exista fuera del workspace. Esto impide validar el libro real, pero no bloquea el discovery.

La implementación histórica consume, por posición A:N:

`Descripción/Cliente | Sobre | Arm/Org | COD. | ARMAZON | CRISTAL | Receta Dr. | TOTAL | Efectivo | Tarj./Cheq. | Ordenes | Cuotas | Saldo | Gastos`

Comportamiento comprobado en código:

- una hoja representa un día; busca encabezado en filas 1 a 6 y usa A1 como fecha;
- cada fila relevante se conserva separada, permitiendo varias filas por operación/cliente sin agruparlas;
- `CAJA INICIAL` toma el valor de Efectivo y no se trata como venta;
- TOTAL, Efectivo, Tarj./Cheq. y Gastos se convierten a montos;
- Ordenes, Cuotas y Saldo se conservan como texto; por eso Saldo admite número o `cancelado` sin interpretarlo;
- cierre histórico: `efectivo_final = caja_inicial + sum(Efectivo) - sum(Gastos)`;
- se recalculan total, efectivo, tarjeta/cheque y gastos diarios;
- no existe arrastre automático: el efectivo final no crea la caja inicial del día siguiente;
- duplicidad actual por `(fecha, unidad)` omite el día completo; los avisos no bloquean la importación.

### BUSINESS_RULE_UNKNOWN

- Disposición/formulación real de hojas, fecha, filas de totales, estilos y arrastre en `Agosto PC 2026.xlsx`.
- Invariante entre TOTAL y Efectivo + Tarj./Cheq. + Ordenes + Cuotas + Saldo.
- Significado contable de `cancelado` y su efecto sobre los totales.
- Regla para agrupar, identificar o editar múltiples filas de una operación.
- Si Ordenes/Cuotas son montos, referencias o ambos.
- Si Tarjeta y Cheque deben separarse.
- Si todo Gasto sale necesariamente de efectivo.
- Tratamiento de filas sin descripción pero con importes.
- Política de corrección/reimportación parcial y duplicados.
- Si falta de caja inicial o monto inválido puede degradarse a cero.
- Regla exacta del arrastre, incluyendo días sin actividad, fines de semana, reapertura y correcciones retroactivas.

## 4. GAP_ANALYSIS

### Existe

- entrada integrada en la UI actual;
- parser Excel muy próximo al contrato informado;
- carga manual básica;
- cálculo básico de totales y efectivo esperado;
- arqueo por denominaciones;
- detección básica de duplicados;
- patrones desktop y SQLite probados en otros productos BC.

### Falta para MVP operativo

- validar el contrato contra el Excel real;
- separar dominio, casos de uso, persistencia e interfaz;
- SQLite local, esquema y migración inicial;
- identificadores estables para día, operación y línea;
- transacciones, edición segura y política de duplicados;
- cierre/reapertura explícitos y arrastre de efectivo;
- reglas de validación que no conviertan silenciosamente errores en cero;
- consultas/totales diarios y trazabilidad de importación;
- tests unitarios, de repositorio y fixtures Excel sintéticos representativos;
- backup/restore y procedimiento de puesta en producción local;
- contrato futuro, sin implementación aún, hacia Movimientos/BC Gestión.

## 5. MVP_BOUNDARY

Alcance mínimo exacto:

1. Una Caja por unidad y fecha, con caja inicial y estado abierto/cerrado.
2. Varias líneas por operación/cliente conservando las 14 columnas del Excel.
3. Alta manual, edición controlada e importación XLSX con preview y errores bloqueantes/no bloqueantes explícitos.
4. SQLite local transaccional.
5. Totales diarios de TOTAL, Efectivo, Tarj./Cheq. y Gastos.
6. Efectivo esperado/final y arqueo con diferencia.
7. Cierre diario y arrastre explícito al próximo día según regla aprobada.
8. Consulta simple del día y evidencia de origen/importación.

Exclusiones: PostgreSQL, API central, sincronización, multiusuario/red, integración automática con Movimientos/BC Gestión, facturación, inventario, reportes avanzados/PDF, conciliación bancaria, desglose futuro de medios, permisos complejos y cambios en otros productos BC.

## 6. PROPOSED_STRUCTURE

Destino recomendado: continuar en PX-Core sobre `feature/caja-diaria`, extrayendo gradualmente el módulo existente; no crear BC Caja dentro de BC-Core ni un repo nuevo durante el MVP.

```text
PX-Core/
  modulos/
    caja_diaria/
      __init__.py
      domain/
        models.py
        calculations.py
        errors.py
      application/
        services.py
        ports.py
      infrastructure/
        sqlite_repository.py
        excel_importer.py
        migrations/001_caja_diaria.sql
      ui/
        caja_window.py
      bootstrap.py
  tests/
    caja_diaria/
      test_calculations.py
      test_excel_importer.py
      test_sqlite_repository.py
      fixtures/
```

`CajaDiaria.py` permanece como referencia y, durante transición, puede convertirse en un adaptador/entry point del paquete. Los helpers útiles se extraen o envuelven; no se importa el monolito `ImportadorExcel.py` desde el dominio.

## 7. MISSION_PLAN

1. `BC-CAJA-BEHAVIOR-001`: fijar contrato observable, fixtures sintéticos y decisiones/unknowns sin UI.
2. `BC-CAJA-DOMAIN-001`: modelos, IDs, cálculos y estados abrir/cerrar; tests puros.
3. `BC-CAJA-SQLITE-001`: schema, repositorio, transacciones y migración desde TXT vacío/legacy.
4. `BC-CAJA-EXCEL-001`: importer/preview idempotente contra fixtures y luego Excel real cuando esté accesible.
5. `BC-CAJA-APP-001`: casos de uso de apertura, líneas, edición, cierre, arqueo y arrastre.
6. `BC-CAJA-UI-001`: adaptar CustomTkinter existente a los servicios; sin lógica de dominio en widgets.
7. `BC-CAJA-PILOT-001`: backup, instalación local, prueba con copia aprobada de datos y checklist de óptica.
8. `BC-CAJA-OPERATIONS-001`: cierre de hallazgos del piloto y declaración `BC CAJA MVP — OPERATIVO EN ÓPTICA`.

## Decisión canónica

El camino mínimo no es construir Caja desde cero: es adaptar `PX-Core/CajaDiaria.py` en el mismo ecosistema y branch, conservar su contrato Excel y UI como evidencia, sustituir TXT por SQLite y aislar reglas/casos de uso antes de ampliar la pantalla. El Excel real debe validar el comportamiento antes de declarar el importer productivo.
