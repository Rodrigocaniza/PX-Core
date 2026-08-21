PASS
Mision BC-OPTICA-COMERCIAL-UI-Y-CARGA-INICIAL-V1-005, slice 5, sobre b580e50 (slice 4)
Fuentes verificadas 11 sha256 ok
Convencion de hash: sha256 con saltos normalizados a LF, igual que los slices 1 a 4

ESTADO CANONICO VERIFICADO SIN ASUMIR NINGUN SHA DEL PROMPT
origin/main 7db56a0, slices 1 a 4 en ed0dbba, 54f5f06, ecc0c7b y b580e50: los cinco
  identicos en local y en origin
Las migraciones 022, 023, 024 y 025 confirmadas commit por commit con --diff-filter=A
Produccion: 21 migraciones, sha256 1c4fcc40...98ec, sin la tabla articles
0 leases, 0 sesiones ajenas activas
Headless Executor: NO se uso. BC-Core local no lo tiene y usarlo habria exigido
  sincronizar BC-Core, fuera de alcance

LO QUE SE INSPECCIONO ANTES DE CONSTRUIR
El importador del slice 1 (planificar_importacion) ya existia y es puro: se reusa
import_runs de la migracion 015 ya existia y ya se usaba en admin_ops: se reusa
El unico Excel del repositorio es la plantilla mensual de BC Gestion, que es de nomina y
  no tiene nada que ver con articulos. NO se reciclo nada de ahi
No existe en el repositorio ningun archivo con los articulos reales de la Optica. Por eso
  este slice entrega el MECANISMO y el CONTRATO del archivo, no los articulos

DOMINIO AGREGADO: EL MINIMO, Y NADA MAS
articles gana location, min_stock y barcode. Son datos propios del articulo sin ninguna
  otra fuente posible: donde esta en el local, cuando avisar, y el codigo del proveedor
NO se agrego articles.cost. El costo es lo que dijo la factura y ya vive en
  purchase_lines.unit_cost. Una columna en el maestro seria una segunda verdad que puede
  contradecir al documento. La pantalla lo muestra DERIVADO de la ultima compra confirmada
  y, sin compras, dice PENDIENTE_DE_CONCILIACION. Hay prueba de las dos cosas y el
  Librarian verifica que la columna no exista
NO se agrego tax_rate por articulo. El IVA es 10% para todo y no hay evidencia de una sola
  excepcion; una columna inventaria una variabilidad que el negocio no tiene

CATALOGO NO ES STOCK
Aplicar el archivo crea articulos y CERO movimientos. Verificado sobre la copia productiva
El stock inicial entra como INGRESO_ADMINISTRATIVO con motivo INVENTARIO_INICIAL, con
  articulo, sucursal, cantidad, actor, fecha, motivo, observacion del recuento y
  document_kind CARGA_INICIAL con el id de la corrida
NO se falsea una compra: verificado que la carga de stock inicial deja 0 purchases y
  0 suppliers, y que el movimiento no tiene supplier_id. Falsearla habria dado un stock
  correcto colgando de un proveedor que nunca facturo eso
Idempotente por run_id: volver a apretar el boton no duplica el inventario
Si el recuento estuvo mal se compensa; el movimiento original queda

LA NATURALEZA NO SE INFIERE
Si la columna nature viene vacia o es invalida, la fila se rechaza. Deducirla del texto
  pondria a un cristal a descontar stock el dia que alguien escriba "armazon de cristal"
Un plan con rechazos no se aplica a medias: cargar 1.999 de 2.000 dejaria un catalogo que
  nadie sabe describir. El boton de aplicar solo se habilita sin rechazos
Vacio significa "no se", no cero. El plan reporta cuantas filas quedan pendientes
El mismo archivo no se carga dos veces: sha256, quien y cuando quedan en import_runs

LA UI NO TIENE REGLAS
Verificado mecanicamente que ni la pantalla ni el controlador nombran PURCHASE_CONFIRMED,
  SALE_COMPLETED, ni escriben en stock_movements, purchases o domain_events
revisar_compra() devuelve los dos totales y los problemas en castellano; la pantalla los
  muestra. Si la pantalla repitiera las reglas, el dia que el dominio cambie una seguiria
  diciendo la vieja
Ni la UI ni el controlador mencionan negative_override
El operador no ve ids, claves de idempotencia, eventos ni efectos

CAJA NO DEPENDE DE LA PANTALLA COMERCIAL
La ventana vive en su propio modulo y se importa DENTRO de la funcion que la abre, con
  except ImportError. Si el modulo comercial faltara, Caja sigue abriendo igual
La estructura de sale_items no cambio: la venta optica sigue siendo UNA fila con sus dos
  componentes. Escribir a mano sigue funcionando y no descuenta nada

STOCK VISIBLE, CON ESTADOS Y NO CON NUMEROS AMBIGUOS
DISPONIBLE, SIN_STOCK, NO_LLEVA_STOCK, SUCURSAL_DESCONOCIDA, INACTIVO
Un servicio muestra "—" y no "0": no tiene stock cero, no tiene stock
Una caja sin sucursal muestra "?": no se finge saber
Lo que no tiene stock se muestra igual, marcado: esconderlo haria pensar que el articulo
  no existe y alguien lo crearia de nuevo
No se hizo dashboard de inventario ni transferencias

ESCENARIO REAL DE PUNTA A PUNTA, SOBRE COPIA PRODUCTIVA
21 pasos verificados: archivo -> catalogo sin stock -> naturalezas del archivo ->
  recuento auditado -> recuento idempotente -> proveedor -> factura a credito ->
  vencimiento derivado -> linea de cristal sin reparto -> revision confirmable ->
  reparto Asuncion/Pilar -> confirmar -> stock 26/16 -> venta -> stock 25/16 ->
  venta de puro servicio con hecho y sin movimientos -> venta sin stock rechazada ->
  trazabilidad salida->venta y entrada->factura->proveedor -> costo derivado ->
  articulo sin compra sin costo inventado -> 10 lineas historicas intactas

LA GUIA DESCRIBE UN FORMATO QUE EL CODIGO ACEPTA
El gate Librarian lee docs/PLANTILLA_ARTICULOS.csv con el lector real y lo pasa por el
  planificador real: 5 filas, 0 rechazos. Y verifica que la guia documente las cuatro
  naturalezas. Una guia que documenta un formato que el codigo rechaza es peor que no
  tener guia

MIGRACION 026
Aditiva: tres ADD COLUMN sobre articles, dos indices y un motivo sembrado
El indice del codigo de barras es PARCIAL: bloquea el duplicado solo cuando hay codigo.
  Sin codigo no hay duplicado que detectar y no se inventa uno, igual que con el RUC
Cadena 25 -> 26

VERIFICACION SOBRE LA BASE PRODUCTIVA REAL
Cadena 022..026 sobre una COPIA, abierta en modo lectura y copiada con la API de backup
0 tablas perdidas, 0 filas cambiadas: 12 cash_entries y 10 sale_items intactos,
  integrity ok, foreign_key_check 0, SUM(cash_entries.total) 6.400.000
Base real sin tocar: sha256 1c4fcc40...98ec antes y despues

PRUEBAS
Dirigidas primero: 57 escritas antes de la implementacion
Suite completa 905 passed + 4 subtests, exit 0 (848 baseline del slice 4 + 57)
El flake BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001 no aparecio en esta mision

CONTRATO PROPIO CORREGIDO
test_los_motivos_de_ingreso_administrativo_estan_sembrados, del slice 2, fijaba el
  conjunto EXACTO de motivos y se rompio al llegar INVENTARIO_INICIAL. Su intencion era
  "la 023 los sembro completos", no "nunca habra un quinto". Ahora afirma inclusion y
  ademas verifica que todos exijan observacion, que era lo que realmente importaba

LO QUE NO SE HIZO, A PROPOSITO
Reversion de ventas, notas de credito, Cuentas por Pagar, transferencias, IVA completo,
  cantidad por linea, dashboard de inventario, rediseno de Gestion Central, Telegram
No se empaqueto ni se instalo nada. main intacto en 7db56a0. Sin PR y sin merge
Los ~3.000 articulos reales NO se inventaron: se entrega la plantilla y la guia
