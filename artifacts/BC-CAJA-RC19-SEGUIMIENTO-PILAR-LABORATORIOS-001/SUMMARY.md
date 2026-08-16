# BC Caja RC19 — Seguimiento Pilar / laboratorios

Base canónica: `fdac03a9aff95d74f8131ec5cc1010a7e1f9cecb` (RC18 CLOSED).

Circuito operativo único dentro de BC Caja para seguir los trabajos desde que
salen de Pilar hasta que vuelven a Pilar. No es una aplicación separada: es la
pestaña **Seguimiento**, junto a Caja diaria y Pedidos.

## Decisiones de diseño

**ATRASADO no es un estado almacenado, es una condición derivada.** El trabajo
conserva su etapa real (`EN_LABORATORIO`) y el atraso se calcula contra el
plazo comprometido cada vez que se consulta. Guardarlo como estado obligaría a
un proceso que reescriba filas al pasar la hora, y haría perder la etapa. Así
la detección es automática por construcción: no hay nada que ejecutar.

**CONFIRMADO_PARA_MAÑANA tampoco es una etapa: es un plazo nuevo.** Confirmar
es registrar una novedad de contacto que trae fecha y hora nuevas. Mientras el
plazo no venza el trabajo sale de atrasados; si vence, vuelve solo. Esto
también cumple el requisito de trazabilidad: la confirmación queda en el
historial con quién, cuándo, medio y respuesta, no como un flag suelto.

**Identidad reutilizada, no duplicada.** `tracked_works` enlaza `order_id` y
`cash_entry_id` cuando el trabajo ya existe en Caja, con índice único sobre
`order_id`. `envelope` y `customer_name` sostienen el caso real en que Nidia
registra en Pilar antes de que exista venta en Asunción. No se copian teléfono,
documento ni datos económicos del cliente.

**Laboratorio pasa de texto libre a entidad.** Hoy `laboratory` es una columna
de texto en `cash_entries` y `sale_items`, sin teléfono. RC19 agrega la tabla
`laboratories` con nombre, línea, WhatsApp —columnas distintas— y activo. La
columna de texto existente queda intacta.

## Circuito

`ENVIADO_DESDE_PILAR → RECIBIDO_EN_ASUNCION → EN_LABORATORIO →
RECIBIDO_DEL_LABORATORIO → ENVIADO_A_PILAR → RECIBIDO_EN_PILAR → CERRADO`

`ALLOWED_TRANSITIONS` es la única fuente de verdad y rechaza cualquier salto.
Se admite un único retroceso deliberado: `RECIBIDO_DEL_LABORATORIO →
EN_LABORATORIO`, para el trabajo que volvió mal y hay que reenviar.

## Vista operativa

- Resumen superior con seis indicadores; **Atrasados** con máxima jerarquía
  visual y fondo de alerta cuando es mayor que cero.
- Alerta `N trabajos atrasados — contactar laboratorios` sobre el resumen.
- Grilla: Sobre, Cliente, Estado, Laboratorio, Esperado, Línea, WhatsApp,
  Última novedad. Las excepciones se ordenan primero.
- **Línea y WhatsApp van en la misma fila**: la operadora no pregunta qué
  laboratorio es ni entra a otra pantalla a buscar el número.
- Franja inferior con los atrasados agrupados por laboratorio y sus teléfonos,
  para hacer una sola llamada por varios trabajos.
- Progreso de recepción `Enviados / Recibidos / Falta recibir`.
- Filtros: estado, laboratorio, atrasados.
- Acciones habilitadas solo cuando la transición es válida para la fila.

`Llamar` / `WhatsApp` quedan preparados en arquitectura —el número ya está
resuelto y disponible en la fila— sin introducir ninguna integración externa.

## Datos

Migración `016_work_tracking.sql`: `laboratories`, `tracked_works`,
`tracked_work_transitions`, `tracked_work_contacts`, más la clave
`tracking` en `app_settings` con la hora esperada por defecto configurable
(`15:00`, alternativa `15:30`). No hay ninguna hora cableada en el código de
transición: el default se lee de configuración.

Local-first: todo vive en la misma base SQLite de Caja. Una prueba sustituye
`socket.socket` por una función que falla y recorre el circuito completo, de
modo que cualquier dependencia de red rompería la suite.
`created_at`/`updated_at` quedan listos para sincronización futura con BC
Gestión, sin agregar infraestructura cloud.

## Fuera de alcance, respetado

FactuFácil, entrega final al cliente, WhatsApp API, rediseño de Caja, cambios
económicos, fórmulas, arqueos, correo, convenios y comisiones: sin tocar.

## Ajustes en pruebas existentes

Seis pruebas fijaban la cadena de migraciones en 015. RC19 agrega 016, así que
se extendieron a 016 conservando su intención (cadena completa, versionada e
idempotente). `test_rc13_advances_schema_once_to_015` pasa a
`test_rc19_advances_schema_once_to_016` y ahora verifica las dos últimas.

## Verificación

- Regresión canónica: **293 PASS, 0 FAIL** (RC18 dejó 222; RC19 suma 71).
- Smoke GUI real PASS en 1920×1080 y 1366×768.
- RC18 verificado sin regresión tras los cambios.
