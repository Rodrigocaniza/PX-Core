# BC-OPTICA-COMISION-COMPOSTURAS-V1-021

**Comision de composturas: politica, vigencia, compensacion y reporte**

Estado: COMPLETADA_EN_CASA · migracion 032 · sin apply productivo

---

## Que resolvia

La V1-020 dejo el motor funcionando: una compostura que llega a `LISTO` devenga,
`event_id UNIQUE` impide que el mismo hecho pague dos veces, y anular compensa en
vez de borrar. Lo que no dejo fue como se administra eso.

La politica vivia en una tabla con una fila por persona que se sobreescribia con
un UPDATE. Esa forma no puede decir dos cosas que el negocio si necesita:

- **Desde cuando.** El dia que una tarifa pase de 5.000 a 7.000, un UPDATE deja
  la base diciendo que siempre fue 7.000. El importe devengado en agosto no
  cambia -eso ya estaba guardado en el asiento- pero se pierde la razon: por que
  se pagaron 5.000. Un numero economico sin causa verificable es exactamente lo
  que este sistema no quiere tener.
- **Que se apago.** Con una sola fila, dejar de comisionar a alguien solo se
  puede escribir borrando la fila o poniendo cero, y las dos mienten distinto: la
  primera borra que alguna vez cobro, la segunda dice "le corresponde cero" donde
  lo que paso fue "se le dio de baja".

Ademas no habia pantalla, no habia reporte, y desde una compostura no se podia
ver que comision habia generado.

## Que se hizo

**Migracion 032.** La politica pasa a ser un log append-only de versiones
(`service_commission_policy_versions`), con triggers que rechazan UPDATE y
DELETE. Cambiar el importe, activar y desactivar son todos el mismo hecho -una
version nueva- y por eso no hay tres caminos que mantener. Cada version guarda
importe, si esta activa, desde cuando rige, el importe anterior, el motivo, quien
y cuando. El contenido de la tabla vieja se migra como primera version y la tabla
vieja se elimina: dos lugares donde diga cuanto cobra una persona es peor que
uno solo bien hecho.

**El asiento dice que politica lo explico.** `service_job_commissions` gana una
columna `policy_id`. El importe ya estaba guardado, asi que la plata de agosto
nunca estuvo en riesgo; lo que agrega es la causa. Subir una tarifa manana no
cambia lo de hoy porque lo de hoy no se recalcula: se lee.

**Panel de administracion.** Seccion "Comisiones de composturas": la politica
arriba, lo que genero abajo. Estan en la misma pantalla porque son la misma
conversacion. Solo ADMIN, con `require_admin()` en el servicio en cada llamada:
la pestana es por donde se entra, no la cerradura.

**Reporte.** Filtros por rango de fechas, sucursal, responsable y estado. Una
fila por devengo con su compensacion al lado -no dos asientos sueltos que haya
que emparejar a ojo- y totales de bruto, compensado y neto que se suman sobre las
mismas filas que se muestran.

**Lo que no devengo tambien se ve.** Un trabajo terminado sin comision se lista
aparte. Un cero que nadie ve no es una decision, es un olvido; lo que lo
convierte en decision es que ese listado exista y quede vacio a proposito.

**Trazabilidad.** El historial de una compostura termina con un bloque COMISION:
quien, cuanto, con que politica, en que estado, y si hubo compensacion.

## Lo que deliberadamente NO se hizo

- **No hay liquidacion.** Se busco un concepto canonico de LIQUIDADA o PAGADA en
  el esquema y no existe: hoy el negocio no registra el pago de esta comision.
  Inventarle un estado seria escribir un flujo que nadie ejecuta, y despues
  alguien leeria "pagada" donde nunca se pago. Se reporta devengado y neto.
- **No hay movimiento de caja.** Devengar y pagar son hechos distintos. Una
  comision que nace no saca un guarani de la caja.
- **No hay efecto sobre inventario.** Hilo, Tornillo, Plaqueta, Patillas y
  Compostura siguen siendo servicio no stockeable. Probado por conteo, por
  estructura y por imposibilidad de import.
- **No se toca la comision comercial del 1%.** Ni siquiera vive en esta base: se
  calcula en `SobresVenta.py` de BC Gestion, sobre archivos de texto plano. La
  separacion es estructural, no una promesa del comentario.
- **No se sembro nada.** Ni una persona ni un monto en codigo productivo. Los
  5.000 Gs se cargan en la Optica, sobre personas reales, despues de migrar.

## Defectos encontrados y corregidos antes del commit

Cinco, todos con su prueba de regresion. Los tres que importan:

1. **El UNIQUE de vigencia estaba mal pensado.** Prohibir dos versiones con el
   mismo `effective_from` sonaba correcto -no habria desempate- pero convertia
   una correccion legitima en un error de base: corregir una tarifa futura antes
   de que empiece es normal, y las dos versiones arrancan el dia 1. El desempate
   pasa a ser `created_at`.
2. **El reporte filtraba por dia UTC.** Una comision devengada despues de las
   nueve de la noche caia en el dia siguiente y desaparecia del rango pedido. Es
   el mismo defecto que la V1-020 ya habia cerrado en otra consulta, reaparecido
   en una nueva. Se usa `_limites_utc_del_dia`, la funcion canonica.
3. **La bitacora del devengo se escribia fuera de la transaccion.** El caso peor
   es el que mas importa: la linea "este trabajo no devengo porque no hay
   politica" es la unica huella de esa omision, y escribirla despues es no
   escribirla.

## Numeros

| | |
|---|---|
| Pruebas dirigidas | 77 (68 de servicio y persistencia, 9 de UI) |
| Suite completa | 1365 passed, 0 failed |
| Suite antes del slice | 1288 passed |
| Migracion | 032, no aplicada en produccion |
| Tablas nuevas | 1 (`service_commission_policy_versions`) |
| Tablas eliminadas | 1 (`service_commission_policy`, migrada) |
| Lineas tocadas en `CajaDiaria.py` | +8 / -1 |
