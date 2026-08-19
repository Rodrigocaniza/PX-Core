# Verdict — QA, generación 11
Runner: QA-IND-COMISION-POLICY-1PCT-011
Snapshot: 75d7f1b6d0ff090abe9f1c063388c38b3f2f4ab0
Veredicto: PASS

## Escenarios propios ejecutados

Método: diferencial. Extraje el árbol `modulos/` de la generación 10 (`bdc4f53`) y el de la 11 (`75d7f1b`) a dos directorios separados del scratchpad de sesión y corrí los mismos guiones propios contra ambos, comparando salida contra salida. Ningún fichero del repo fue tocado; no hay commits. Los guiones son míos: no reusé ni una prueba del paquete ni un verdict de las generaciones 1 a 10.

Guion 1 — escenarios (E1–E14), 211 líneas de salida por árbol:

- E1 venta común 400.000 cancelada: base 400.000, 1%, 4.000 Gs.; revisa, aprueba y paga.
- E2 convenio 500.000: descuento 25.000, base 475.000, 4.750 Gs.; el 5% antes del 1%; las tres puertas pasan.
- E3 bordes HALF_UP: común con totales 1, 49, 50, 149, 150, 151, 1.050, 2.050, 99.950, 1.000.050 —el medio guaraní exacto del 1% cae en los que terminan en 50— y convenio con 10, 21, 30, 110, 1.010, 2.050, 200.010, 999.990, que activan el medio guaraní del **descuento del 5%** y encadenan los dos redondeos. Las 18 liquidaciones pasan review, approve y mark_paid en ambos árboles con importes idénticos.
- E4 tasa 0: se publica 0 bp con vigencia futura, se comisiona un mes bajo esa tasa (base 777.777, importe 0 Gs.) y las tres puertas aceptan el importe de 0 Gs.
- E5 venta con saldo: no comisiona ni se deja revisar; cobro parcial informativo; al cerrarse el saldo promueve a ELEGIBLE y recorre la cadena.
- E6 bases migradas construidas a mano: 7% pagado vivo (mes fijado al 7% por MIGRACION, importe 70.000 intacto antes y después); venta nueva de ese mismo mes comisiona al 7% y se paga; APROBADA migrada al 7% se paga; **convenio migrado** con base 475.000 al 7% se paga; migrada al 1% coherente recorre las tres puertas; migrada en el **borde de redondeo** (base 1.050 → 11 Gs.) recorre las tres puertas; importe 0 por base 0 pasa; legada `POLITICA_HISTORICA_PREVIA` sigue rechazada por su etiqueta; incoherentes (importe inventado, y off-by-one de 1 Gs. sobre el borde) rechazadas.
- E7 filtro por período: fila con `period` crudo `2026-08-15`; `list_entries` y `recalculate` con argumento `2026-08`, `2026-08-15`, `2026-08-05`, `' 2026-08 '`, `2026-8`, `2026`, `''` y `None`, más un juego de filas normales de 2026-07/08/09.
- E8 secuencia fijar → soltar → refijar: PINNED al aprobar, UNPINNED al observar, y PINNED de nuevo con un hecho posterior; libro completo conservado.
- E9 venta anulada y período anterior a la vigencia (`FUERA_DE_VIGENCIA`, sin porcentaje, rechazado en review).
- E10 recálculo idempotente: cuatro pasadas, historial sin duplicados, APROBADA inalcanzable por `recalculate`.
- E11 corrección de origen sobre venta común y sobre convenio corregido a la baja, con recierre completo de la cadena.
- E12 reporte y export `contract_version` 3 con bloque de política y disclaimer.
- E13 publicar política nueva: vigencia futura aceptada, republicar lo idéntico idempotente, vigencia hacia atrás rechazada; la APROBADA del mes ya fijado no cambia y se paga; el mes nuevo cobra la tasa nueva.
- E14 reapertura: abrir la base migrada cinco veces deja el mismo pin y una sola línea de auditoría.

Guion 2 — barrido de legitimidad (el que más pesa en este veredicto): 253 totales por tipo de venta —todos los restos módulo 200 sobre 1.000 para el 1%, cuarenta múltiplos de 5 sobre 100.000 para el medio guaraní del 5%, más los bordes sueltos—, es decir **506 liquidaciones producidas por el propio sistema**, común y convenio, recalculadas y pasadas por review, approve y mark_paid. Resultado en ambos árboles: 506 pagadas, **0 rechazos**, suma 273.090 Gs. idéntica. Incluye además la reapertura de saldo por reversión de cobro y el recierre posterior.

Guion 3 — argumento del período: `list_entries`, `recalculate`, `report` y `export_summary` con diez formas del argumento sobre las mismas filas.

`python -m pytest -q` en el snapshot: **456 passed**, sin fallos ni avisos.

Diferencial entre los dos árboles: sobre 211 + 12 + 40 líneas comparadas, las únicas diferencias son (a) los identificadores UUID de pagos, que son aleatorios por construcción, (b) el rechazo nuevo sobre las filas incoherentes de procedencia externa, y (c) el alcance del argumento con fecha completa. Todo lo demás —importes, estados, pins, eventos, historial, disclaimer— es carácter por carácter igual.

## Bloqueantes

Ninguno.

El rechazo nuevo no alcanza a nada legítimo. En 506 liquidaciones producidas por el sistema, más los convenios, los bordes HALF_UP incluido el medio guaraní exacto en el 5% y en el 1%, los importes de 0 Gs. por tasa cero y por base cero, y las migradas coherentes al 1%, al 3%, al 7% y en convenio, no hubo un solo rechazo. La razón estructural que lo respalda: los tres únicos sitios que escriben `commission_amount` —`recalculate`, `_apply_source_update` y el alta— lo escriben siempre con `commission_for` sobre la misma `commissionable_base` que graban en la misma sentencia, o lo dejan en `NULL`; el cuarto sitio que toca la base sin tocar el importe, `_promote_to_eligible`, sólo actúa sobre filas `PENDIENTE_SALDO`, que por construcción llevan tasa e importe nulos.

La semántica de la generación 9 sigue en pie: el mes con pago vivo al 7% queda fijado al 7% y no al 1% vigente (E6, E14), su importe no se toca ni al operar ni al reabrir, el 1% gobierna los meses sin tasa histórica viva (E1, E13), y la secuencia fijar/soltar/refijar produce exactamente los mismos eventos que en la generación 10 (E8).

## Observaciones no bloqueantes

1. **O1-g11 — la normalización del argumento sí cambia el alcance, pero sólo para un argumento malformado.** Con un período bien formado `AAAA-MM` las filas alcanzadas son idénticas en las dos generaciones. La diferencia aparece cuando el **argumento** es una fecha completa: en la generación 10 `list_entries(period="2026-08-15")` devolvía `[]`; en la 11 alcanza el mes entero. Es un ensanchamiento, no un desvío, y `recalculate` reportó `changed: 0`. Efecto derivado que sí conviene mirar: con ese argumento, `report` y `export_summary` muestran el dinero de todo el mes bajo un rótulo `period` que no es un período, y el KPI queda internamente descuadrado —`sales_in_period: 0` junto a `commission_amount: 8000`—, porque ese contador se calcula por una consulta que no comparte la normalización. Normalizar el argumento en la cabecera del informe cerraría el hueco.

2. **O2-g11 — el rechazo nuevo se evalúa antes que la comprobación de etiqueta y le roba el diagnóstico.** Una liquidación legada `POLITICA_HISTORICA_PREVIA` cuyo importe además no cuadra ahora se rechaza con «el importe no es el que produce la tasa aplicada», donde la generación 10 decía «no lleva la política oficial vigente». Ambas rechazan y ningún dinero cambia; lo que cambia es qué le dice el sistema a quien tiene que arreglarla. Comprobar la etiqueta antes que el importe restauraría el mensaje más informativo.

3. Mis observaciones 3 y 4 de la generación 9 sobre el vocabulario del contrato siguen abiertas a propósito. No las reevalué y no cuentan en este veredicto.

## Superficie que mi revisión NO cubrió

- La capa Tk: no se ejercitó con interacción real ni a 1920x1080. Sólo leí el punto donde el campo de período llega a `recalculate`.
- La prueba estructural del árbol sintáctico: la vi pasar dentro de los 456 tests, pero no la ataqué con una función nueva que se la saltara. Doy esa garantía por buena sobre evidencia ajena.
- Concurrencia: todo mi trabajo fue de un solo hilo.
- Roles y permisos: operé siempre como `ADMIN_CENTRAL`.
- Los módulos vecinos sólo quedaron cubiertos por la corrida de `pytest`.
- El esquema completo del export `contract_version` 3, campo por campo.
- El fichero incoherente que motiva la guarda lo construí yo con `INSERT` directo. No verifiqué que exista una base real del piloto con esa forma.
- Rendimiento sobre volúmenes de producción.
