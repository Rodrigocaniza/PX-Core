PASS
Mision BC-OPTICA-PURCHASES-PROVIDERS-V1-003, slice 3 de 6, sobre 54f5f06 (slice 2), que
  sale de ed0dbba (slice 1) y de origin/main 7db56a0 = BC Caja 1.0.0-rc.31
Fuentes verificadas 10 sha256 ok
Convencion de hash: sha256 con saltos normalizados a LF, igual que los slices 1 y 2

ESTADO CANONICO VERIFICADO SIN ASUMIR NINGUN SHA DEL PROMPT
origin/main 7db56a0, slice 1 ed0dbba, slice 2 54f5f06: los tres identicos en local y origin
La 022 entro en ed0dbba y la 023 en 54f5f06, confirmado con git log --diff-filter=A sobre
  los archivos de migracion, no por lo que dicen los artefactos
Produccion: 21 migraciones, sha256 1c4fcc40...98ec, cero tablas de los slices 2 y 3
0 leases en PX-Core
Sesiones ajenas: hay procesos python de otra mision de BC-Core (mission_workflow_engine y
  un venv de pilot-readiness) iniciados a las 16:38 y 16:42. Operan sobre BC-Core, no
  sobre PX-Core/main, y se dejan como estan porque BC-Core queda fuera del alcance

REUTILIZACION VERIFICADA, NO DUPLICACION
suppliers de la 022 se EXTIENDE con address, email y contact_name. No se creo una tabla de
  proveedores paralela
La naturaleza del articulo sigue decidiendo si mueve stock: la linea de compra NO lleva
  bandera propia. Hay prueba de que el trigger lista las mismas dos naturalezas que
  _NATURALEZAS_QUE_MUEVEN_STOCK y ninguna de las otras dos
domain_events y event_effects se usan tal como estan. PURCHASE_CONFIRMED es un hecho mas
stock_movements se usa tal como esta. Los INGRESO_COMPRA son movimientos normales
La referencia durable que el slice 2 dejo preparada (supplier_id, document_kind,
  document_id, document_line_id, document_number) se llena ahora SIN migrar el ledger, que
  es exactamente lo que ese slice prometio
Destination ASUNCION/PILAR: mismo vocabulario, sin tabla de sucursales

EL LEDGER NO SE REDISEÑO
Solo se expuso lo que ya hacia: registrar_en(connection, ...), asegurar_evento_en(...) y
  marcar_evento_procesado_en(...). La logica de insercion, idempotencia, stock negativo y
  append-only no cambio ni una linea
Lo que cambio es que el dueño de la transaccion puede ser otro, que es lo que hace posible
  que confirmar una compra sea atomico de punta a punta

PROVEEDORES
Identidad, razon social, RUC/CI, telefono, direccion, email, contacto, activo y auditoria
El duplicado se bloquea SOLO cuando hay identidad fiscal fiable: indice unico parcial sobre
  document donde no esta vacio. Dos proveedores sin RUC conviven, porque inventarles una
  identidad para poder compararlos seria peor que no compararlos. Hay prueba de las dos cosas
No hay baja, hay desactivacion: borrar un proveedor dejaria facturas apuntando a nadie, y
  esas facturas explican stock que existe
No es un CRM: los campos son los que la carga de una factura real pide y nada mas

LA FACTURA
purchases representa la factura a nivel empresa, UNA sola vez. Indice unico
  (supplier_id, document_number). Cargarla una vez por sucursal seria la misma factura
  existiendo dos veces, con dos verdades posibles
document_total es lo que dice el papel; la suma de las lineas es derivada. Se guardan los
  dos y se contrastan al confirmar: que no coincidan es un hecho a mostrar, no uno que el
  sistema deba arreglar solo. Hay prueba con TotalNoCuadra
due_date es derivado: pasarlo al constructor es TypeError, y el trigger
  purchases_vencimiento_derivado verifica que la fila guardada no contradiga fecha + plazo
CHECK: plazo y vencimiento existen si y solo si la condicion es CREDITO
Dos estados, BORRADOR y CONFIRMADA. No hay ANULADA, y eso es deliberado

LINEAS
Referencian el articulo canonico y conservan cantidad, costo unitario y la descripcion que
  traia la factura. Sin columna de total (es cantidad por costo) y sin bandera de stock
Una linea no-stock pertenece legitimamente a la factura: el laboratorio factura cristales,
  esa linea conserva su costo y su documentacion, y no genera unidades. Hay prueba

DISTRIBUCION FISICA
Solo para lo que mueve stock: trigger derivado de articles.nature, verificado tambien
  escribiendo directo contra la base
No se distribuye mas de lo comprado: trigger que acumula lo ya repartido
Al confirmar, lo repartido tiene que IGUALAR lo comprado. Un borrador puede estar
  incompleto, para eso es un borrador; lo que no puede es generar stock estando incompleto
Lo que la fuente no determina no se inventa: una linea stockeable sin reparto NO se
  confirma, en vez de mandar todo a Asuncion por defecto
Cantidades positivas y un destino por linea: CHECK, UNIQUE y dominio

CONFIRMACION
Todo en una sola transaccion BEGIN IMMEDIATE: el hecho, un INGRESO_COMPRA por linea
  stockeable y destino, los event_effects, el hecho a PROCESADO y la compra a CONFIRMADA
El hecho se registra ANTES que sus efectos, y no es un detalle de orden: una factura de
  puros servicios se confirma igual y su PURCHASE_CONFIRMED tiene que quedar registrado
  aunque no arrastre un solo movimiento. La primera version lo insertaba como efecto
  colateral del primer movimiento y esa factura fallaba con violacion de clave foranea. Lo
  encontro la prueba de linea no-stock, que estaba escrita antes que el codigo
Idempotencia por camino completo: COMPRA:{compra} para el hecho y
  COMPRA:{compra}:{linea}:{destino} para cada movimiento. Reconfirmar devuelve lo mismo sin
  escribir nada: 1 evento, 2 efectos, 2 movimientos, verificado contando filas
Rollback atomico: con un fallo inyectado en el segundo movimiento no queda nada. La compra
  sigue en BORRADOR, 0 eventos, 0 efectos, 0 movimientos

TRAZABILIDAD MECANICA
La vista stock_origen_compra contesta con una consulta, no leyendo codigo: que factura, que
  proveedor, que linea, que destino, que evento, cuando y quien confirmo, para cualquier
  unidad que este en el deposito

DINERO Y STOCK SEPARADOS
Registrar y confirmar una factura no toca Caja. Las pruebas cuentan las filas de cash_days,
  cash_entries, cash_counts y cash_day_corrections antes y despues
Una compra a credito no genera un egreso: es una obligacion, no una salida de dinero de hoy
Verificado mecanicamente que el modulo no nombra ninguna tabla de Caja

BOUNDARY EXPLICITO, NO IMPROVISADO
Notas de credito y anulacion exceden el slice y NO se improvisaron. En su lugar, 9 triggers
  hacen imposible editar o borrar una compra confirmada, sus lineas o su reparto, desde
  cualquier escritor. La factura original nunca desaparece para corregir el stock: para eso
  ya existe el movimiento compensatorio del slice 2, y hay prueba de que sacar una unidad
  rota deja la compra intacta
Cuentas por Pagar: solo se guarda e indexa el vencimiento
UI: no se implemento. El flujo es demostrable de punta a punta por el servicio y las pruebas
Transferencias entre sucursales: vocabulario del slice 2, sigue sin usarse
IVA: la factura guarda su total. Inventar una apertura impositiva sin evidencia seria lo
  que el principio prohibe

MIGRACION 024
Aditiva. Lo unico que toca de lo existente son tres ADD COLUMN con default sobre suppliers,
  tabla que crea la 022 y que en produccion no tiene ni una fila. Cadena 23 -> 24

VERIFICACION SOBRE LA BASE PRODUCTIVA REAL
La cadena 022+023+024 se aplico sobre una COPIA de la base de la Optica, abierta en modo
  lectura y copiada con la API de backup
0 tablas perdidas, 0 filas cambiadas en las 25 preexistentes, sale_items 10/10 con
  article_id NULL, integrity ok, foreign_key_check 0, SUM(cash_entries.total) 6.400.000
Los 14 invariantes se probaron sobre esa copia CON FILAS REALES sembradas, no sobre tablas
  vacias: un trigger BEFORE ... FOR EACH ROW sobre tabla vacia no rechaza nada, y eso ya
  dio un falso resultado en el slice anterior
Base productiva real sin tocar: sha256 1c4fcc40...98ec antes y despues

PRUEBAS
Dirigidas primero: 43 escritas antes de la implementacion
Suite completa 806 passed + 4 subtests, exit 0 (763 baseline del slice 2 + 43 nuevas)
Una corrida intermedia dio 5 errors en tests/gestion_central/test_ui_interactions.py.
  Aislados pasan y la corrida siguiente dio 806 limpios: es el flake heredado
  BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001, agravado por los procesos de la sesion ajena que
  estaban compitiendo por recursos. No lo introdujo este slice y no se lo corrigio

CONTRATO PROPIO CORREGIDO, Y LA CAUSA TAMBIEN
test_la_cadena_de_migraciones_llega_a_023, del slice 2, fijaba el final de la cadena. Es la
  TERCERA vez que aparece el mismo error: el slice 1 se lo corrigio a seis contratos
  ajenos y lo repitio en el propio, el slice 2 hizo lo mismo. Ademas de corregirla se
  agrego afirmar_cadena_completa_con() en tests/migration_chain.py, para que el proximo
  slice tenga donde apoyarse en vez de volver a escribirlo mal
