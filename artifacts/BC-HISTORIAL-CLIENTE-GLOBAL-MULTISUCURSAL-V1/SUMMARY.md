# Cliente global multisucursal V1

La generación conserva intacto el snapshot `f37ebd8` del PR #13 y construye
una continuación limpia. `GlobalHistoryService` federa fuentes canónicas
autorizadas y une automáticamente solo por CI/RUC normalizado exacto.
Coincidencias débiles quedan separadas y requieren refinamiento explícito.

Operadora y Admin pueden consultar hechos autorizados de Asunción y Pilar.
La política expresa “ver global / operar local”: una operadora no puede operar
la sucursal ajena; Admin puede hacerlo según su rol. Historial no incluye APIs
de escritura y el adaptador SQLite continúa `mode=ro` + `query_only`.

La CLI falla cerrada. Caja revalida `CashSession` mediante `require_operator`
y entrega el contexto en memoria a una ventana `Toplevel`; no existen claims
autodeclarados, credenciales nuevas ni seguridad paralela.
