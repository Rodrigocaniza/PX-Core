# BC-CAJA-BEHAVIOR-001 — Legacy + MVP Behavior Contract

Fecha: 2026-08-10

Estado: BEHAVIOR_FROZEN / PENDING_REAL_WORKBOOK_VALIDATION

Baseline: PX-Core `feature/caja-diaria@92a15f046ac652fa83d1b81a5411b6bbe363fee8`.

`CajaDiaria.py` no fue modificado. Esta misión caracteriza su comportamiento y define el contrato futuro sin implementar dominio productivo, UI o SQLite.

## 1. Fuentes y nivel de autoridad

- `OBSERVED_LEGACY`: comportamiento ejecutado directamente contra `CajaDiaria.py`.
- `USER_STATED_CONTRACT`: estructura y flujo operativo informados para la óptica.
- `MVP_DECISION`: boundary técnico mínimo que debe implementar CORE-001.
- `BUSINESS_RULE_UNKNOWN`: no debe codificarse hasta decisión.
- `PENDING_REAL_WORKBOOK_VALIDATION`: requiere comparación con `Agosto PC 2026.xlsx`, hoy inaccesible en el workspace.

El comportamiento legacy es evidencia, no política aprobada.

## 2. Contrato legacy exacto

### Campos y persistencia

El registro TXT contiene 17 campos, en este orden:

`fecha | unidad | descripcion | sobre | arm_org | cod | armazon | cristal | receta_dr | total | efectivo | tarjeta_cheque | ordenes | cuotas | saldo | gastos | origen`

- Ruta: `Datos/caja_diaria.txt`.
- Separador: `|`; cualquier pipe ingresado se reemplaza por `/`.
- Faltantes al leer una línea se completan con texto vacío.
- Campos adicionales en una línea quedan descartados por `zip`.
- No hay IDs, transacciones, locking, versionado ni audit trail.
- Alta agrega líneas reescribiendo el archivo completo.
- No hay edición de una línea. `eliminar_dia` elimina todas las líneas de `(fecha, unidad)`.

### Excel

- Una hoja equivale a un día.
- Encabezado: primera fila entre 1 y 6 que contenga simultáneamente `TOTAL` y `Efectivo`, normalizados.
- Las columnas se consumen por posición A:N, no por el nombre localizado.
- Fecha: A1; si falla, puede usarse el día siguiente a la hoja previa.
- Unidad por defecto: `PC`.
- `CAJA INICIAL`: se toma Efectivo, no se importa como movimiento. Si se repite, gana la última. Si falta, se usa cero.
- Descripción `TOTALES` o vacía: la fila se descarta incluso si contiene montos.
- Fila completamente vacía: se ignora.
- Fila informativa: se ignora si Armazón, Cristal, Ordenes, Cuotas, Saldo y los cuatro montos están vacíos/cero.
- TOTAL, Efectivo, Tarj./Cheq. y Gastos se parsean a entero; vacío se vuelve cero.
- Un monto inválido se vuelve cero y genera aviso no bloqueante.
- Sobre, Arm/Org, COD., Armazón, Cristal, Receta Dr., Ordenes, Cuotas y Saldo son texto.
- `saldo="cancelado"` se preserva sin interpretación.
- Varias filas de una operación permanecen independientes; no existe operation_id.
- Duplicado en archivo o persistencia por fecha/unidad: se omite el día completo.
- Los totales declarados por el workbook no se comparan realmente, pese al comentario del código.

### Alta manual

- Requiere fecha parseable; unidad por defecto `PC`.
- Guarda un registro por acción con `origen="manual"`.
- TOTAL, Efectivo, Tarj./Cheq. y Gastos vacíos se mantienen como texto vacío; si se informan deben parsear correctamente o no se guarda.
- Los demás campos se guardan como texto libre.
- No valida equilibrio de medios contra TOTAL, duplicados, estado de cierre ni valores negativos.

### Cierre y consulta

- `registros_del_dia(fecha, unidad)` permite consulta histórica técnica por igualdad exacta.
- No existe pantalla histórica, estado OPEN/CLOSED, cierre persistido, reapertura ni bloqueo de cambios posteriores.
- Si hay varias cajas iniciales persistidas, gana la última recorrida.
- Fórmulas:

```text
total = sum(TOTAL)
efectivo_ventas = sum(Efectivo)
tarjeta_cheque = sum(Tarj./Cheq.)
gastos = sum(Gastos)
efectivo_esperado = caja_inicial + efectivo_ventas - gastos
```

- Ordenes, Cuotas y Saldo no participan de totales.
- No existe arrastre al siguiente día.

### Arqueo

- Denominaciones: 100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 100 y 50 PYG.
- `diferencia = total_contado - efectivo_esperado`.
- Estado: `OK` si cero, `SOBRA` si positivo, `FALTA` si negativo.
- Persistencia prevista: `Datos/arqueo_caja.txt`.
- Un nuevo arqueo reemplaza el anterior de la misma fecha/unidad.
- No valida cantidades negativas.

## 3. Clasificación

### Conservar

- vocabulario y orden mental de las 14 columnas;
- fecha/unidad, caja inicial y múltiples filas;
- preservación literal de información óptica y `cancelado` hasta decidir semántica;
- totales básicos y fórmula histórica de efectivo esperado;
- preview/avisos de importación y arqueo OK/SOBRA/FALTA;
- compatibilidad desktop con CustomTkinter.

### Accidental/legacy

- TXT delimitado por pipes;
- columnas por posición aun después de localizar encabezados;
- unidad `PC` embebida;
- fecha por posición de hojas;
- eliminación de todo el día como sustituto de edición;
- strings vacíos y ceros mezclados para montos.

### Claramente defectuoso para MVP

- monto inválido convertido silenciosamente a cero;
- fila sin descripción descartada aun con importes;
- avisos permiten importar datos dañados;
- falta de IDs e idempotencia por operación/fila;
- omisión completa del día ante duplicado;
- ausencia de estado de cierre y posibilidad de modificar después del arqueo;
- ausencia de arrastre y trazabilidad;
- persistencia no transaccional.

## 4. Contrato mínimo del dominio MVP

### CashDay

- Identidad estable propia.
- Clave de negocio candidata: `(business_date, unit)`; su unicidad queda en CORE-001.
- Atributos mínimos: `id`, `business_date`, `unit`, `opening_cash`, `status`, `entries`, `opened_at`, `closed_at`.
- Estado: `OPEN` o `CLOSED`.
- Solo `OPEN` acepta altas/ediciones/eliminaciones.
- `close()` congela sus totales y genera evidencia de cierre.
- Reapertura es `BUSINESS_RULE_UNKNOWN`; no se presupone.

### CashEntry

- Identidad estable y `cash_day_id`.
- Campos de las 14 columnas, más `origin`, `source_reference`, timestamps y versión/audit metadata mínima.
- Montos: enteros PYG o ausencia explícita según campo; nunca float.
- TOTAL/Efectivo/Tarj.-Cheq./Gastos inválidos producen error, nunca cero implícito.
- Varias líneas similares no se fusionan automáticamente.
- Un futuro `operation_id` puede agruparlas; su regla es desconocida.

### Totals

- Debe reproducir inicialmente los cuatro acumulados y el efectivo esperado legacy.
- Ordenes, Cuotas y Saldo se conservan, pero su efecto contable queda pendiente.
- Los totales se calculan desde entries; al cierre se guarda un snapshot verificable.

### Servicios y repositorio

- abrir/obtener Caja por fecha y unidad;
- agregar/editar/eliminar entrada solo en OPEN;
- previsualizar e importar un conjunto atómicamente;
- calcular totales y registrar arqueo;
- cerrar y consultar histórico;
- contrato de repositorio independiente de SQLite;
- boundary futuro de publicación hacia BC Gestión, sin implementación.

### Arrastre

El MVP necesita una política explícita que proponga la caja inicial siguiente desde el efectivo final cerrado. No se define todavía si es automática, confirmada, cómo salta días sin actividad ni cómo reacciona a reaperturas. Estado: `BUSINESS_RULE_UNKNOWN` y `PENDING_REAL_WORKBOOK_VALIDATION`.

## 5. Fixtures y tests

- `tests/caja_diaria/fixtures/legacy_cases.json`: día vacío, apertura, efectivo, tarjeta/cheque, mixto, gasto, múltiples filas, saldo, orden/cuotas, valores opcionales y cierre.
- `tests/caja_diaria/fixtures/invalid_cases.json`: catálogo ejecutable/documental de bordes legacy.
- `test_legacy_excel_contract.py`: parser, columnas, filas, textos, totales y errores.
- `test_legacy_calculations.py`: TXT, cierre, arqueo y eliminación por día.
- `test_desired_mvp_behavior.py`: cinco contratos futuros como `expectedFailure`; se vuelven tests verdes durante CORE-001, uno por comportamiento realmente implementado.

Resultado fresco: 17 tests ejecutados; 12 PASS; 5 expected failures; 0 fallos inesperados.

## 6. Condición del workbook

`PENDING_REAL_WORKBOOK_VALIDATION` permanece activo. Ningún fixture afirma reproducir fórmulas, estilos, filas o arrastre del archivo real; solo combina comportamiento legacy observado y estructura informada.
