PASS
Mision BC-OPTICA-SALES-ARTICLE-LINK-V1-004, slice 4 de 6, sobre ecc0c7b (slice 3), que
  sale de 54f5f06 (slice 2), de ed0dbba (slice 1) y de origin/main 7db56a0 = rc.31
Fuentes verificadas 6 sha256 ok
Convencion de hash: sha256 con saltos normalizados a LF, igual que los slices 1 a 3

ESTADO CANONICO VERIFICADO SIN ASUMIR NINGUN SHA DEL PROMPT
origin/main 7db56a0, slice 1 ed0dbba, slice 2 54f5f06, slice 3 ecc0c7b: los cuatro
  identicos en local y en origin
La 022 entro en ed0dbba, la 023 en 54f5f06 y la 024 en ecc0c7b, confirmado con
  git log --diff-filter=A sobre los archivos de migracion
Produccion: 21 migraciones, sha256 1c4fcc40...98ec, cero tablas del nucleo comercial
0 leases en PX-Core
Sesiones ajenas: siguen vivos los procesos de la mision de BC-Core. No tocan PX-Core/main
  y se dejan como estan
Headless Executor: NO se uso. BC-Core local no lo tiene y usarlo habria exigido
  sincronizar BC-Core, que estaba explicitamente fuera de alcance

LO QUE HUBO QUE AVERIGUAR ANTES DE DISEÑAR NADA
Una linea de venta de BC Caja NO es un articulo. Los datos productivos reales muestran
  frame_price y lens_price en la MISMA fila: es un par de anteojos, no un producto
La 022 habia agregado article_id asumiendo un articulo por linea. Faltaba el segundo
Partir la venta en dos filas para que cada una tuviera un solo articulo habria sido
  reescribir el subsistema de ventas, que es justo lo que este slice no hace. El vinculo
  se adapta a la forma que la operacion real tiene, no al reves

EL VINCULO
article_id: articulo del componente fisico. lens_article_id: articulo del trabajo de
  laboratorio. Dos columnas nullables sobre la fila que existe desde la 006
tracks_stock NO es columna de la linea: se deriva de la naturaleza del articulo, igual que
  en los slices 1 a 3. Ni descripcion, ni codigo, ni laboratorio, ni item_type deciden
  nada. Hay prueba con una linea cuya descripcion dice "Armazon/org uvx"

NADA DE LO QUE YA EXISTE EMPIEZA A MOVER STOCK POR SI SOLO
Una venta sin articulo vinculado se comporta exactamente como hoy. Hay prueba
Vincular un articulo es un acto nuevo que hoy no ocurre en ninguna parte
Ademas el integrador es OPCIONAL y por defecto no esta: SQLiteCashDayRepository(ruta)
  guarda como guardaba antes de que existiera el nucleo comercial. Hay prueba, y el gate
  Librarian verifica que el default del parametro sea None

SALE_COMPLETED
Se emite al guardarse una entrada ACTIVE con al menos una linea vinculada. ACTIVE es
  finalizada segun el modelo economico actual de BC Caja: la unica transicion posterior
  es VOIDED
El hecho se registra ANTES que sus efectos. Una venta de puros servicios y una de puro
  trabajo de laboratorio emiten el hecho y cero movimientos. Un hecho no depende de tener
  efectos, y esa es la misma correccion que el slice 3 tuvo que hacer sobre la marcha,
  aplicada de entrada
Trazabilidad: entity_id de la venta, sucursal, vendedora, momento, payload con dia, fecha,
  unidad, total y todas las lineas con su articulo y su tracks_stock, mas event_effects
Sigue siendo registro durable de hechos y efectos, no un event bus

EFECTOS DE STOCK
Una linea con articulo que mueve stock produce UN movimiento VENTA de cantidad 1
La cantidad es 1 porque SaleItem no tiene cantidad y nunca la tuvo: una linea es una
  unidad. Inventar una cantidad seria inventar un dato
Referencia durable: venta, linea, articulo, destino, evento, actor y momento
Servicios y trabajos forman parte de la venta, tienen precio, alimentan el hecho y no
  generan ningun movimiento. Hay prueba para servicio, para trabajo y para venta mixta
Produccion interna sale igual que cualquier producto stockeable. Hay prueba
Una entrada anulada no descuenta: anular es lo contrario de vender

SUCURSAL
Sale de cash_register_branches, el vinculo canonico de las migraciones 018 y 020. Se LEE,
  no se duplica ni se reinterpreta
La operadora no elige de donde sale el stock. Verificado en la firma: integrar_en no
  recibe destino y no existe ningun setter
Una caja sin vinculo no puede vender stock (SucursalNoResoluble). Si puede vender
  servicios: sin efecto de inventario la sucursal no hace falta. Hay prueba de las dos

STOCK INSUFICIENTE
La venta no se guarda. Comprobado sobre la MISMA conexion de la transaccion: preguntarlo
  por otra devolveria lo de antes de empezar, y en una venta de dos lineas del mismo
  articulo le daria el visto bueno a las dos
El trigger del ledger de la 023 sigue debajo, para cualquier escritor
faltantes_de_stock() contesta antes de intentar guardar, con articulo, disponible, pedido
  y destino, para que el rechazo no llegue tarde
Una venta nunca pide la excepcion administrativa: el gate verifica que la palabra
  negative_override no aparezca en el modulo

ATOMICIDAD
Una sola transaccion: la que save() ya abria. El integrador recibe la conexion y no abre
  ninguna propia. Verificado mecanicamente: su codigo no contiene BEGIN ni COMMIT
Rollback con fallo inyectado en el segundo movimiento de una venta de dos lineas:
  0 entradas, 0 eventos, 0 efectos, 0 movimientos, stock intacto

IDEMPOTENCIA
Durable en la base, no una bandera en memoria: tabla sale_stock_integrations, mas las
  claves VENTA:{entrada} del hecho y VENTA:{entrada}:{linea} de cada movimiento
Probado guardando tres veces, reabriendo desde la base y volviendo a guardar, y con un
  repositorio nuevo sin nada en memoria, que es el caso despues de un corte

EDICION POSTVENTA
El guardado de Caja borra y reinserta las lineas en cada save. Eso esta bien para una
  venta que no saco nada del deposito y es inaceptable para una que si: el movimiento que
  la saco apunta a esa fila. save() ahora saltea las lineas de las ventas integradas
BLOQUEADO: cambiar, agregar o borrar lineas de una venta integrada, y anularla
PERMITIDO: telefono, observaciones, cliente, vendedora y todo lo que vive en cash_entries
  y no cambia la causalidad del inventario. La entrada NO queda congelada entera
Cuatro triggers lo hacen cumplir para cualquier escritor. El chequeo previo existe para
  que el rechazo sea un mensaje entendible y no una violacion de constraint a mitad del
  guardado
NO hay reversion y no se improvise: necesita el movimiento compensatorio de la 023 atado
  al circuito de negocio de la anulacion. Media reversion seria peor que bloquear

HISTORICO
planificar_backfill_de_ventas() calcula y NO escribe
No aplicable: una linea vieja identifica lo que alguien escribio esa tarde, no un articulo
  del catalogo. Elegir uno por parecido lo inventaria y ademas cambiaria el stock de hoy
  con una inferencia sobre el pasado
Las 10 lineas historicas siguen leyendose con article_id NULL. Hay prueba

DINERO
Una salida VENTA mueve una unidad y no mueve un guarani. Totales y arqueo sin cambios,
  verificado contando filas antes y despues y releyendo los totales del dia
Verificado mecanicamente que el modulo no inserta ni actualiza cash_entries, cash_days,
  cash_counts ni cash_day_corrections

PREPARADO, NO IMPLEMENTADO
FactuFacil, Trabajos, revision, Gestion Central y estadisticas cuelgan del mismo hecho y
  su payload ya lleva lo que necesitan. Este slice no deriva ninguna: el unico effect_kind
  que existe es STOCK_MOVEMENT, y hay prueba

MIGRACION 025
Aditiva: un ALTER TABLE ADD COLUMN nullable sobre sale_items, una tabla nueva, seis
  triggers, una vista y un indice. Cadena 24 -> 25

VERIFICACION SOBRE LA BASE PRODUCTIVA REAL
La cadena 022..025 se aplico sobre una COPIA de la base de la Optica, abierta en modo
  lectura y copiada con la API de backup
0 tablas perdidas, 0 filas cambiadas: 12 cash_entries y 10 sale_items intactos,
  integrity ok, foreign_key_check 0, SUM(cash_entries.total) 6.400.000
Los invariantes se probaron sobre esa copia usando una venta REAL de la Optica, no una
  fila inventada: se marco como integrada y se intentaron las seis mutaciones prohibidas,
  las seis rechazadas; y se comprobo que una venta NO integrada sigue siendo editable y
  borrable como siempre
Base productiva real sin tocar: sha256 1c4fcc40...98ec antes y despues

PRUEBAS
Dirigidas primero: 42 escritas antes de la implementacion
Suite completa 848 passed + 4 subtests, exit 0 (806 baseline del slice 3 + 42 nuevas)
Una corrida intermedia dio 5 errors en tests/gestion_central/test_ui_interactions.py.
  Aislados pasan y la corrida siguiente dio 848 limpios: es el flake heredado
  BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001, que ya habia aparecido igual en el slice 3. No
  lo introdujo este slice y no se lo corrigio

LO QUE NO SE HIZO, A PROPOSITO
UI: sin cambios. Se entrego lo que la UI va a necesitar, no la UI
Reversion de ventas, FactuFacil, Pedidos, transferencias entre sucursales
BC-Core y Telegram no se tocaron. Sesiones ajenas no se interrumpieron
Sin PR, sin merge, sin empaquetar, sin instalar. main intacto en 7db56a0
