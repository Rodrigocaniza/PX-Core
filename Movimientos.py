from datetime import datetime
from pathlib import Path
import unicodedata

from datos import leer_datos, guardar_datos


RUTA_MOVIMIENTOS = "Datos/movimientos.txt"
RUTA_ADICIONALES = "Datos/movimientos_adicionales.txt"
RUTA_CONCEPTOS_ADICIONALES = "Datos/conceptos_adicionales.txt"
RUTA_INVERSIONES = "Datos/inversiones.txt"
RUTA_PRESTAMOS = "Datos/prestamos.txt"
RUTA_CUOTAS_PRESTAMOS = "Datos/cuotas_prestamos.txt"
RUTA_FONDO_ESTABILIDAD = "Datos/fondo_estabilidad.txt"
RUTA_LIQUIDACIONES = (
    Path(__file__).resolve().parent
    / "Datos"
    / "liquidaciones.txt"
)
PORCENTAJE_FONDO_ESTABILIDAD = 40
UNIDADES = ["PC", "MVPC", "P2", "MVP2", "ADMINISTRACIÓN"]
CONCEPTOS_INGRESO_ADICIONAL = [
    "Alquiler del consultorio",
]
CONCEPTOS_EGRESO_ADICIONAL = [
    "Alquiler - PC",
    "Alquiler - P2",
    "IPS",
    "Systemsoft",
    "SET",
    "Porta - Marketing",
    "Pago de tarjeta de crédito",
    "Bancard",
]
MARCADOR_CATALOGO_CONCEPTOS = "#CATALOGO_CONCEPTOS_V1"


def normalizar_texto(texto):
    texto = texto.strip().lower()
    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )
    return texto


def convertir_fecha(fecha_texto):
    return datetime.strptime(fecha_texto, "%d-%m-%Y")


def fecha_esta_en_rango(fecha_texto, fecha_desde, fecha_hasta):
    try:
        fecha = convertir_fecha(fecha_texto)
        return fecha_desde <= fecha <= fecha_hasta
    except ValueError:
        return False


def formatear_monto(monto):
    return f"{monto:,.0f}".replace(",", ".")


def formatear_porcentaje(porcentaje):
    return f"{porcentaje:.2f}".replace(".", ",")


def pedir_fecha(mensaje="Fecha (DD-MM-AAAA): ", permitir_volver=True):
    while True:
        fecha = input(mensaje).strip()

        if permitir_volver and fecha == "0":
            return None

        try:
            convertir_fecha(fecha)
            return fecha
        except ValueError:
            print()
            print("Fecha inválida. Usá el formato DD-MM-AAAA.")
            if permitir_volver:
                print("Escribí 0 para volver.")


def pedir_rango_fechas():
    while True:
        print()
        print("====================================")
        print("          RANGO DE FECHAS")
        print("====================================")
        print()
        print("0. Volver")
        print()

        fecha_desde_texto = pedir_fecha(
            "Fecha inicial (DD-MM-AAAA): "
        )

        if fecha_desde_texto is None:
            return None

        fecha_hasta_texto = pedir_fecha(
            "Fecha final (DD-MM-AAAA): "
        )

        if fecha_hasta_texto is None:
            return None

        fecha_desde = convertir_fecha(fecha_desde_texto)
        fecha_hasta = convertir_fecha(fecha_hasta_texto)

        if fecha_desde > fecha_hasta:
            print()
            print(
                "La fecha inicial no puede ser posterior "
                "a la fecha final."
            )
            continue

        return fecha_desde, fecha_hasta


def pedir_monto(mensaje="Monto: ", valor_actual=None):
    while True:
        if valor_actual is None:
            texto = input(mensaje).strip()
        else:
            texto = input(
                f"{mensaje.rstrip(': ')} "
                f"[{formatear_monto(valor_actual)}]: "
            ).strip()

            if texto == "":
                return valor_actual

        if texto == "0":
            return None

        texto_limpio = (
            texto
            .replace(".", "")
            .replace(",", "")
            .replace(" ", "")
        )

        try:
            monto = int(texto_limpio)

            if monto <= 0:
                raise ValueError

            return monto
        except ValueError:
            print("Monto inválido. Ingresá solamente números mayores a 0.")


def seleccionar_unidad(
    mensaje="Seleccione una unidad: ",
    permitir_volver=True,
    valor_actual=None
):
    while True:
        print()

        for numero, unidad in enumerate(UNIDADES, start=1):
            print(f"{numero}. {unidad}")

        if valor_actual is not None:
            print("ENTER. Conservar", valor_actual)

        if permitir_volver:
            print("0. Volver")

        opcion = input(mensaje).strip()

        if opcion == "" and valor_actual is not None:
            return valor_actual

        if permitir_volver and opcion == "0":
            return None

        try:
            indice = int(opcion) - 1

            if 0 <= indice < len(UNIDADES):
                return UNIDADES[indice]
        except ValueError:
            pass

        print()
        print("Opción inválida.")


def pedir_texto(mensaje, valor_actual=None):
    while True:
        if valor_actual is None:
            texto = input(mensaje).strip()
        else:
            texto = input(
                f"{mensaje.rstrip(': ')} [{valor_actual}]: "
            ).strip()

            if texto == "":
                return valor_actual

        if texto == "0":
            return None

        if texto != "":
            return texto

        print("Este campo no puede quedar vacío.")


def confirmar(mensaje):
    return input(mensaje).strip().upper() == "SI"


def registros_en_rango(ruta, separador, fecha_desde, fecha_hasta):
    registros = []

    for posicion, linea in enumerate(leer_datos(ruta)):
        datos = separador(linea)

        if datos is None:
            continue

        if fecha_esta_en_rango(
            datos["fecha"],
            fecha_desde,
            fecha_hasta
        ):
            registros.append((posicion, datos))

    return registros


def seleccionar_origen_deposito(valor_actual=None):
    while True:
        print()

        for numero, unidad in enumerate(UNIDADES, start=1):
            print(f"{numero}. {unidad}")

        print(f"{len(UNIDADES) + 1}. Otra persona")

        if valor_actual is not None:
            print("ENTER. Conservar", valor_actual)

        print("0. Cancelar")
        print()

        opcion = input(
            "Unidad o persona que deposita: "
        ).strip()

        if opcion == "" and valor_actual is not None:
            return valor_actual

        if opcion == "0":
            return None

        if opcion == str(len(UNIDADES) + 1):
            return pedir_texto(
                "Nombre de la persona: ",
                valor_actual
            )

        try:
            indice = int(opcion) - 1

            if 0 <= indice < len(UNIDADES):
                return UNIDADES[indice]
        except ValueError:
            pass

        print()
        print("Opción inválida.")


def clasificar_tipo(tipo_original):
    tipo = normalizar_texto(tipo_original)

    if tipo == "ingreso":
        return "Ingreso"

    if tipo == "egreso":
        return "Egreso"

    if tipo == "transferencia interna":
        return "Transferencia interna"

    if tipo == "cobro externo":
        return "Cobro externo"

    if (
        tipo in [
            "deposito interno",
            "deposito bancario",
            "deposito bancario interno",
        ]
        or tipo.endswith("sito interno")
    ):
        return "Deposito interno"

    return tipo_original.strip()


def separar_movimiento(movimiento):
    datos = [dato.strip() for dato in movimiento.split("|")]

    if len(datos) < 5:
        return None

    try:
        monto = int(
            datos[4]
            .replace(".", "")
            .replace(",", "")
            .strip()
        )
    except ValueError:
        return None

    return {
        "tipo": clasificar_tipo(datos[0]),
        "fecha": datos[1],
        "origen": datos[2],
        "destino": datos[3],
        "monto": monto,
    }


def construir_movimiento(tipo, fecha, datos_actuales=None):
    origen_actual = None
    destino_actual = None
    monto_actual = None

    if datos_actuales is not None:
        origen_actual = datos_actuales["origen"]
        destino_actual = datos_actuales["destino"]
        monto_actual = datos_actuales["monto"]

    if tipo == "Ingreso":
        unidad = seleccionar_unidad(
            "Unidad que recibe el ingreso: ",
            valor_actual=destino_actual
        )

        if unidad is None:
            return None

        monto = pedir_monto("Monto: ", monto_actual)

        if monto is None:
            return None

        return f"Ingreso|{fecha}|Externo|{unidad}|{monto}|Si"

    if tipo == "Egreso":
        unidad = seleccionar_unidad(
            "Unidad que realiza el egreso: ",
            valor_actual=origen_actual
        )

        if unidad is None:
            return None

        monto = pedir_monto("Monto: ", monto_actual)

        if monto is None:
            return None

        return f"Egreso|{fecha}|{unidad}|Externo|{monto}|Si"

    if tipo == "Transferencia interna":
        origen = seleccionar_unidad(
            "Unidad de origen: ",
            valor_actual=origen_actual
        )

        if origen is None:
            return None

        destino = seleccionar_unidad(
            "Unidad de destino: ",
            valor_actual=destino_actual
        )

        if destino is None:
            return None

        if origen == destino:
            print()
            print("El origen y el destino no pueden ser iguales.")
            return None

        monto = pedir_monto("Monto: ", monto_actual)

        if monto is None:
            return None

        return (
            f"Transferencia interna|{fecha}|"
            f"{origen}|{destino}|{monto}|No"
        )

    if tipo == "Deposito interno":
        origen = seleccionar_origen_deposito(origen_actual)

        if origen is None:
            return None

        banco = pedir_texto("Banco de destino: ", destino_actual)

        if banco is None:
            return None

        monto = pedir_monto("Monto: ", monto_actual)

        if monto is None:
            return None

        return f"Deposito interno|{fecha}|{origen}|{banco}|{monto}|No"

    if tipo == "Cobro externo":
        banco = pedir_texto("Banco que recibió el cobro: ", origen_actual)

        if banco is None:
            return None

        unidad = seleccionar_unidad(
            "Unidad a la que pertenece el cobro: ",
            valor_actual=destino_actual
        )

        if unidad is None:
            return None

        monto = pedir_monto("Monto: ", monto_actual)

        if monto is None:
            return None

        return f"Cobro externo|{fecha}|{banco}|{unidad}|{monto}|Si"

    return None


def elegir_tipo_movimiento(permitir_conservar=False):
    while True:
        print()
        print("1. Ingreso")
        print("2. Egreso")
        print("3. Transferencia interna")
        print("4. Depósito o cobro bancario")

        if permitir_conservar:
            print("5. Conservar el tipo actual")

        print("0. Cancelar")
        print()

        opcion = input("Seleccione el tipo de movimiento: ").strip()

        if opcion == "1":
            return "Ingreso"

        if opcion == "2":
            return "Egreso"

        if opcion == "3":
            return "Transferencia interna"

        if opcion == "4":
            while True:
                print()
                print("1. Depósito interno")
                print("   No suma como ingreso.")
                print("2. Cobro externo")
                print("   Sí suma como ingreso de la unidad.")
                print("0. Volver")
                print()

                tipo_deposito = input(
                    "Seleccione una opción: "
                ).strip()

                if tipo_deposito == "1":
                    return "Deposito interno"

                if tipo_deposito == "2":
                    return "Cobro externo"

                if tipo_deposito == "0":
                    break

                print("Opción inválida.")

        elif opcion == "5" and permitir_conservar:
            return "CONSERVAR"

        elif opcion == "0":
            return None

        else:
            print()
            print("Opción inválida.")


def cargar_dia():
    print()
    print("====================================")
    print("            CARGAR DÍA")
    print("====================================")
    print()
    print("La fecha se pedirá una sola vez.")
    print("Escribí 0 para volver.")
    print()

    fecha = pedir_fecha("Fecha del día (DD-MM-AAAA): ")

    if fecha is None:
        return

    cantidad_cargada = 0

    while True:
        print()
        print("====================================")
        print("       CARGA DEL DÍA", fecha)
        print("====================================")
        print()
        print("1. Ingreso")
        print("2. Egreso")
        print("3. Transferencia interna")
        print("4. Depósito o cobro bancario")
        print("0. Finalizar carga del día")
        print()
        print("Movimientos cargados:", cantidad_cargada)
        print()

        opcion = input("Seleccione una opción: ").strip()

        tipos = {
            "1": "Ingreso",
            "2": "Egreso",
            "3": "Transferencia interna",
        }

        if opcion in tipos:
            tipo = tipos[opcion]

        elif opcion == "4":
            tipo = elegir_tipo_movimiento()

            if tipo is None:
                continue

        elif opcion == "0":
            print()
            print(
                "Carga finalizada. Movimientos registrados:",
                cantidad_cargada
            )
            return

        else:
            print()
            print("Opción inválida.")
            continue

        movimiento = construir_movimiento(tipo, fecha)

        if movimiento is None:
            print()
            print("Movimiento cancelado.")
            continue

        lista_movimientos = leer_datos(RUTA_MOVIMIENTOS)
        lista_movimientos.append(movimiento)
        guardar_datos(RUTA_MOVIMIENTOS, lista_movimientos)
        cantidad_cargada += 1

        print()
        print("Movimiento registrado correctamente.")


def ver_movimientos():
    lista_movimientos = leer_datos(RUTA_MOVIMIENTOS)
    movimientos_validos = [
        movimiento
        for movimiento in lista_movimientos
        if separar_movimiento(movimiento) is not None
    ]

    print()
    print("====================================")
    print("       MOVIMIENTOS REGISTRADOS")
    print("====================================")
    print()

    if not movimientos_validos:
        print("No hay movimientos registrados.")
        return

    for numero, movimiento in enumerate(
        movimientos_validos,
        start=1
    ):
        datos = separar_movimiento(movimiento)
        print(
            f"{numero}. {datos['fecha']} | {datos['tipo']} | "
            f"{datos['origen']} → {datos['destino']} | "
            f"{formatear_monto(datos['monto'])}"
        )

    print()
    print("Cantidad total:", len(movimientos_validos))


def seleccionar_movimiento(mensaje):
    lista_completa = leer_datos(RUTA_MOVIMIENTOS)
    posiciones_validas = []

    print()
    print("====================================")
    print("       MOVIMIENTOS REGISTRADOS")
    print("====================================")
    print()

    for posicion, movimiento in enumerate(lista_completa):
        datos = separar_movimiento(movimiento)

        if datos is None:
            continue

        posiciones_validas.append(posicion)
        numero = len(posiciones_validas)

        print(
            f"{numero}. {datos['fecha']} | {datos['tipo']} | "
            f"{datos['origen']} → {datos['destino']} | "
            f"{formatear_monto(datos['monto'])}"
        )

    if not posiciones_validas:
        print("No hay movimientos registrados.")
        return None, None, None

    print()
    print("0. Volver")
    print()

    opcion = input(mensaje).strip()

    if opcion == "0":
        return None, None, None

    try:
        indice_visible = int(opcion) - 1

        if 0 <= indice_visible < len(posiciones_validas):
            posicion_real = posiciones_validas[indice_visible]
            return (
                lista_completa,
                posicion_real,
                separar_movimiento(
                    lista_completa[posicion_real]
                ),
            )
    except ValueError:
        pass

    print()
    print("Opción inválida.")
    return None, None, None


def mostrar_detalle_movimiento(datos):
    print()
    print("====================================")
    print("        DETALLE DEL MOVIMIENTO")
    print("====================================")
    print()
    print("Fecha:", datos["fecha"])
    print("Tipo:", datos["tipo"])
    print("Origen:", datos["origen"])
    print("Destino:", datos["destino"])
    print("Monto:", formatear_monto(datos["monto"]))


def modificar_movimiento(
    lista_movimientos=None,
    posicion=None,
    datos_actuales=None
):
    if lista_movimientos is None:
        (
            lista_movimientos,
            posicion,
            datos_actuales
        ) = seleccionar_movimiento(
            "Número del movimiento a modificar: "
        )

        if lista_movimientos is None:
            return

    print()
    nueva_fecha = input(
        f"Fecha [{datos_actuales['fecha']}]: "
    ).strip()

    if nueva_fecha == "0":
        return

    if nueva_fecha == "":
        nueva_fecha = datos_actuales["fecha"]
    else:
        try:
            convertir_fecha(nueva_fecha)
        except ValueError:
            print("Fecha inválida. No se modificó el movimiento.")
            return

    print()
    print("Tipo actual:", datos_actuales["tipo"])
    nuevo_tipo = elegir_tipo_movimiento(
        permitir_conservar=True
    )

    if nuevo_tipo is None:
        return

    if nuevo_tipo == "CONSERVAR":
        nuevo_tipo = datos_actuales["tipo"]
        datos_para_editar = datos_actuales
    else:
        datos_para_editar = None

    movimiento_modificado = construir_movimiento(
        nuevo_tipo,
        nueva_fecha,
        datos_para_editar
    )

    if movimiento_modificado is None:
        print()
        print("Modificación cancelada.")
        return

    lista_movimientos[posicion] = movimiento_modificado
    guardar_datos(RUTA_MOVIMIENTOS, lista_movimientos)

    print()
    print("Movimiento modificado correctamente.")


def eliminar_movimiento(
    lista_movimientos=None,
    posicion=None,
    datos=None
):
    if lista_movimientos is None:
        (
            lista_movimientos,
            posicion,
            datos
        ) = seleccionar_movimiento(
            "Número del movimiento a eliminar: "
        )

        if lista_movimientos is None:
            return

    print()
    confirmacion = input(
        "Escribí SI para confirmar la eliminación: "
    ).strip().upper()

    if confirmacion != "SI":
        print()
        print("Eliminación cancelada.")
        return

    movimiento_eliminado = lista_movimientos.pop(posicion)
    guardar_datos(RUTA_MOVIMIENTOS, lista_movimientos)

    print()
    print("Movimiento eliminado correctamente:")
    print(movimiento_eliminado)


def gestionar_movimientos():
    while True:
        (
            lista_movimientos,
            posicion,
            datos
        ) = seleccionar_movimiento(
            "Seleccione un movimiento: "
        )

        if lista_movimientos is None:
            return

        while True:
            print()
            print("====================================")
            print("        GESTIONAR MOVIMIENTO")
            print("====================================")
            print()
            print(
                f"{datos['fecha']} | {datos['tipo']} | "
                f"{datos['origen']} → {datos['destino']} | "
                f"{formatear_monto(datos['monto'])}"
            )
            print()
            print("1. Ver movimiento")
            print("2. Modificar movimiento")
            print("3. Eliminar movimiento")
            print("0. Volver a la lista")
            print()

            opcion = input("Seleccione una opción: ").strip()

            if opcion == "1":
                mostrar_detalle_movimiento(datos)

            elif opcion == "2":
                modificar_movimiento(
                    lista_movimientos,
                    posicion,
                    datos
                )
                break

            elif opcion == "3":
                eliminar_movimiento(
                    lista_movimientos,
                    posicion,
                    datos
                )
                break

            elif opcion == "0":
                break

            else:
                print()
                print("Opción inválida.")


def calcular_resumen_unidad(unidad, fecha_desde, fecha_hasta):
    lista_movimientos = leer_datos(RUTA_MOVIMIENTOS)
    unidad_normalizada = normalizar_texto(unidad)
    ingresos = 0
    egresos = 0
    transferencias_recibidas = 0
    transferencias_enviadas = 0

    for movimiento in lista_movimientos:
        datos = separar_movimiento(movimiento)

        if datos is None:
            continue

        if not fecha_esta_en_rango(
            datos["fecha"],
            fecha_desde,
            fecha_hasta
        ):
            continue

        tipo = datos["tipo"]
        origen = normalizar_texto(datos["origen"])
        destino = normalizar_texto(datos["destino"])
        monto = datos["monto"]

        if (
            tipo in ["Ingreso", "Cobro externo"]
            and destino == unidad_normalizada
        ):
            ingresos += monto

        elif tipo == "Egreso" and origen == unidad_normalizada:
            egresos += monto

        elif tipo == "Transferencia interna":
            if destino == unidad_normalizada:
                transferencias_recibidas += monto

            if origen == unidad_normalizada:
                transferencias_enviadas += monto

    resultado = ingresos - egresos

    return (
        ingresos,
        egresos,
        resultado,
        transferencias_recibidas,
        transferencias_enviadas,
    )


def ver_transferencias_internas(fecha_desde, fecha_hasta):
    lista_movimientos = leer_datos(RUTA_MOVIMIENTOS)
    transferencias = {}

    for movimiento in lista_movimientos:
        datos = separar_movimiento(movimiento)

        if datos is None:
            continue

        if datos["tipo"] != "Transferencia interna":
            continue

        if not fecha_esta_en_rango(
            datos["fecha"],
            fecha_desde,
            fecha_hasta
        ):
            continue

        ruta = f"{datos['origen']} → {datos['destino']}"
        transferencias[ruta] = (
            transferencias.get(ruta, 0) + datos["monto"]
        )

    print()
    print("====================================")
    print("       TRANSFERENCIAS INTERNAS")
    print("====================================")
    print()

    if not transferencias:
        print("No hay transferencias internas en el período.")
    else:
        for ruta, total in transferencias.items():
            print(f"{ruta}: {formatear_monto(total)}")


def ver_depositos_bancarios(fecha_desde, fecha_hasta):
    lista_movimientos = leer_datos(RUTA_MOVIMIENTOS)
    depositos = {}

    for movimiento in lista_movimientos:
        datos = separar_movimiento(movimiento)

        if datos is None:
            continue

        if datos["tipo"] != "Deposito interno":
            continue

        if not fecha_esta_en_rango(
            datos["fecha"],
            fecha_desde,
            fecha_hasta
        ):
            continue

        ruta = f"{datos['origen']} → {datos['destino']}"
        depositos[ruta] = (
            depositos.get(ruta, 0) + datos["monto"]
        )

    print()
    print("====================================")
    print("        DEPÓSITOS BANCARIOS")
    print("====================================")
    print()

    if not depositos:
        print("No hay depósitos bancarios en el período.")
    else:
        for ruta, total in depositos.items():
            print(f"{ruta}: {formatear_monto(total)}")


def ver_cobros_externos(fecha_desde, fecha_hasta):
    lista_movimientos = leer_datos(RUTA_MOVIMIENTOS)
    cobros = {}

    for movimiento in lista_movimientos:
        datos = separar_movimiento(movimiento)

        if datos is None:
            continue

        if datos["tipo"] != "Cobro externo":
            continue

        if not fecha_esta_en_rango(
            datos["fecha"],
            fecha_desde,
            fecha_hasta
        ):
            continue

        ruta = f"{datos['origen']} → {datos['destino']}"
        cobros[ruta] = cobros.get(ruta, 0) + datos["monto"]

    print()
    print("====================================")
    print("           COBROS EXTERNOS")
    print("====================================")
    print()

    if not cobros:
        print("No hay cobros externos en el período.")
    else:
        for ruta, total in cobros.items():
            print(f"{ruta}: {formatear_monto(total)}")


def separar_adicional(linea):
    datos = [dato.strip() for dato in linea.split("|")]

    if len(datos) not in [4, 5]:
        return None

    if datos[0] not in ["Ingreso", "Egreso"]:
        return None

    try:
        convertir_fecha(datos[1])
        monto = int(datos[3])
    except ValueError:
        return None

    return {
        "tipo": datos[0],
        "fecha": datos[1],
        "descripcion": datos[2],
        "monto": monto,
        "observacion": datos[4] if len(datos) == 5 else "",
    }


def cargar_catalogo_conceptos():
    registros = leer_datos(RUTA_CONCEPTOS_ADICIONALES)
    catalogo_inicializado = (
        MARCADOR_CATALOGO_CONCEPTOS in registros
    )
    catalogo = {
        "Ingreso": [],
        "Egreso": [],
    }

    for linea in registros:
        datos = [dato.strip() for dato in linea.split("|", 1)]

        if len(datos) != 2:
            continue

        tipo, concepto = datos

        if tipo not in catalogo or concepto == "":
            continue

        if concepto not in catalogo[tipo]:
            catalogo[tipo].append(concepto)

    if not catalogo_inicializado:
        catalogo["Ingreso"] = list(
            CONCEPTOS_INGRESO_ADICIONAL
        )
        catalogo["Egreso"] = list(
            CONCEPTOS_EGRESO_ADICIONAL
        )
        guardar_catalogo_conceptos(catalogo)

    return catalogo


def guardar_catalogo_conceptos(catalogo):
    registros = [MARCADOR_CATALOGO_CONCEPTOS]

    for tipo in ["Ingreso", "Egreso"]:
        for concepto in catalogo[tipo]:
            registros.append(f"{tipo}|{concepto}")

    guardar_datos(RUTA_CONCEPTOS_ADICIONALES, registros)


def concepto_ya_existe(conceptos, concepto, ignorar_indice=None):
    concepto_normalizado = normalizar_texto(concepto)

    for indice, concepto_existente in enumerate(conceptos):
        if indice == ignorar_indice:
            continue

        if normalizar_texto(concepto_existente) == concepto_normalizado:
            return True

    return False


def seleccionar_tipo_concepto():
    while True:
        print()
        print("1. Conceptos de ingreso")
        print("2. Conceptos de egreso")
        print("0. Volver")
        opcion = input("Seleccione el tipo: ").strip()

        if opcion == "1":
            return "Ingreso"
        if opcion == "2":
            return "Egreso"
        if opcion == "0":
            return None

        print("Opción inválida.")


def mostrar_catalogo_conceptos(catalogo):
    print()
    print("CONCEPTOS DE INGRESO")

    if catalogo["Ingreso"]:
        for numero, concepto in enumerate(
            catalogo["Ingreso"],
            start=1
        ):
            print(f"{numero}. {concepto}")
    else:
        print("Sin conceptos guardados.")

    print()
    print("CONCEPTOS DE EGRESO")

    if catalogo["Egreso"]:
        for numero, concepto in enumerate(
            catalogo["Egreso"],
            start=1
        ):
            print(f"{numero}. {concepto}")
    else:
        print("Sin conceptos guardados.")


def seleccionar_concepto_catalogo(conceptos):
    if not conceptos:
        print()
        print("No hay conceptos guardados en esta lista.")
        return None

    while True:
        print()

        for numero, concepto in enumerate(conceptos, start=1):
            print(f"{numero}. {concepto}")

        print("0. Volver")
        opcion = input("Seleccione el concepto: ").strip()

        if opcion == "0":
            return None

        try:
            indice = int(opcion) - 1

            if 0 <= indice < len(conceptos):
                return indice
        except ValueError:
            pass

        print("Opción inválida.")


def pedir_nombre_concepto(mensaje, valor_actual=None):
    while True:
        concepto = pedir_texto(mensaje, valor_actual)

        if concepto is None:
            return None

        if "|" in concepto:
            print("El concepto no puede contener el símbolo |.")
            continue

        return concepto


def agregar_concepto_adicional():
    tipo = seleccionar_tipo_concepto()

    if tipo is None:
        return

    concepto = pedir_nombre_concepto("Nuevo concepto: ")

    if concepto is None:
        return

    catalogo = cargar_catalogo_conceptos()

    if concepto_ya_existe(catalogo[tipo], concepto):
        print("Ese concepto ya existe.")
        return

    catalogo[tipo].append(concepto)
    guardar_catalogo_conceptos(catalogo)
    print("Concepto agregado correctamente.")


def modificar_concepto_adicional():
    tipo = seleccionar_tipo_concepto()

    if tipo is None:
        return

    catalogo = cargar_catalogo_conceptos()
    indice = seleccionar_concepto_catalogo(catalogo[tipo])

    if indice is None:
        return

    concepto_actual = catalogo[tipo][indice]
    concepto_nuevo = pedir_nombre_concepto(
        "Nuevo nombre: ",
        concepto_actual
    )

    if concepto_nuevo is None:
        return

    if concepto_ya_existe(
        catalogo[tipo],
        concepto_nuevo,
        ignorar_indice=indice
    ):
        print("Ese concepto ya existe.")
        return

    catalogo[tipo][indice] = concepto_nuevo
    guardar_catalogo_conceptos(catalogo)
    print("Concepto modificado correctamente.")
    print(
        "Los movimientos anteriores conservan "
        "el concepto que tenían."
    )


def eliminar_concepto_adicional():
    tipo = seleccionar_tipo_concepto()

    if tipo is None:
        return

    catalogo = cargar_catalogo_conceptos()
    indice = seleccionar_concepto_catalogo(catalogo[tipo])

    if indice is None:
        return

    concepto = catalogo[tipo][indice]
    print()
    print("Concepto seleccionado:", concepto)
    print(
        "Los movimientos anteriores no se eliminarán "
        "ni se modificarán."
    )

    if not confirmar("Escribí SI para quitarlo de la lista: "):
        print("Eliminación cancelada.")
        return

    catalogo[tipo].pop(indice)
    guardar_catalogo_conceptos(catalogo)
    print("Concepto eliminado de la lista correctamente.")


def menu_conceptos_adicionales():
    while True:
        catalogo = cargar_catalogo_conceptos()

        print()
        print("====================================")
        print("       ADMINISTRAR CONCEPTOS")
        print("====================================")
        mostrar_catalogo_conceptos(catalogo)
        print()
        print("1. Agregar concepto")
        print("2. Modificar concepto")
        print("3. Eliminar concepto")
        print("0. Volver")
        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            agregar_concepto_adicional()
        elif opcion == "2":
            modificar_concepto_adicional()
        elif opcion == "3":
            eliminar_concepto_adicional()
        elif opcion == "0":
            return
        else:
            print("Opción inválida.")


def seleccionar_concepto_adicional(tipo, valor_actual=None):
    catalogo = cargar_catalogo_conceptos()
    conceptos = catalogo[tipo]

    while True:
        print()
        print("Conceptos frecuentes:")

        for numero, concepto in enumerate(conceptos, start=1):
            print(f"{numero}. {concepto}")

        print(f"{len(conceptos) + 1}. Otro concepto")

        if valor_actual is not None:
            print("ENTER. Conservar", valor_actual)

        print("0. Volver")
        opcion = input("Seleccione el concepto: ").strip()

        if opcion == "" and valor_actual is not None:
            return valor_actual

        if opcion == "0":
            return None

        if opcion == str(len(conceptos) + 1):
            return pedir_texto(
                "Descripción: ",
                valor_actual
            )

        try:
            indice = int(opcion) - 1

            if 0 <= indice < len(conceptos):
                return conceptos[indice]
        except ValueError:
            pass

        print()
        print("Opción inválida.")


def pedir_observacion(valor_actual=None):
    if valor_actual is None:
        return input(
            "Observación (opcional, ENTER para omitir): "
        ).strip()

    texto = input(
        f"Observación [{valor_actual or 'Sin observación'}]: "
    ).strip()

    if texto == "":
        return valor_actual

    if normalizar_texto(texto) in ["borrar", "eliminar"]:
        return ""

    return texto


def registrar_adicional():
    print()
    print("====================================")
    print("   REGISTRAR INGRESO O EGRESO EXTRA")
    print("====================================")
    print()
    print("1. Ingreso")
    print("2. Egreso")
    print("0. Volver")

    opcion = input("Seleccione el tipo: ").strip()
    tipos = {"1": "Ingreso", "2": "Egreso"}

    if opcion == "0":
        return

    if opcion not in tipos:
        print("Opción inválida.")
        return

    fecha = pedir_fecha()

    if fecha is None:
        return

    tipo = tipos[opcion]
    descripcion = seleccionar_concepto_adicional(tipo)

    if descripcion is None:
        return

    monto = pedir_monto("Monto: ")

    if monto is None:
        return

    observacion = ""

    if descripcion == "Pago de tarjeta de crédito":
        print()
        print(
            "Ejemplo: Visa Oro 200.000 | "
            "Visa Clásica 2.234.343"
        )
        observacion = pedir_observacion()

    registros = leer_datos(RUTA_ADICIONALES)
    registros.append(
        f"{tipo}|{fecha}|{descripcion}|{monto}|{observacion}"
    )
    guardar_datos(RUTA_ADICIONALES, registros)
    print()
    print("Movimiento adicional registrado correctamente.")


def gestionar_adicionales():
    rango = pedir_rango_fechas()

    if rango is None:
        return

    fecha_desde, fecha_hasta = rango
    lista = leer_datos(RUTA_ADICIONALES)
    registros = registros_en_rango(
        RUTA_ADICIONALES,
        separar_adicional,
        fecha_desde,
        fecha_hasta
    )

    print()
    print("====================================")
    print("    INGRESOS Y EGRESOS ADICIONALES")
    print("====================================")
    print()

    if not registros:
        print("No hay registros en el período.")
        return

    for numero, (_, datos) in enumerate(registros, start=1):
        observacion = ""

        if datos["observacion"]:
            observacion = f" | Obs.: {datos['observacion']}"

        print(
            f"{numero}. {datos['fecha']} | {datos['tipo']} | "
            f"{datos['descripcion']} | "
            f"{formatear_monto(datos['monto'])}"
            f"{observacion}"
        )

    print()
    print("0. Volver")
    opcion = input("Seleccione un registro: ").strip()

    if opcion == "0":
        return

    try:
        indice = int(opcion) - 1
        posicion, datos = registros[indice]
    except (ValueError, IndexError):
        print("Opción inválida.")
        return

    print()
    print("1. Modificar")
    print("2. Eliminar")
    print("0. Volver")
    accion = input("Seleccione una opción: ").strip()

    if accion == "1":
        fecha = input(f"Fecha [{datos['fecha']}]: ").strip()

        if fecha == "":
            fecha = datos["fecha"]
        else:
            try:
                convertir_fecha(fecha)
            except ValueError:
                print("Fecha inválida.")
                return

        print("1. Ingreso")
        print("2. Egreso")
        print("ENTER. Conservar", datos["tipo"])
        tipo_opcion = input("Tipo: ").strip()
        tipo = {
            "1": "Ingreso",
            "2": "Egreso",
            "": datos["tipo"],
        }.get(tipo_opcion)

        if tipo is None:
            print("Opción inválida.")
            return

        descripcion = seleccionar_concepto_adicional(
            tipo,
            datos["descripcion"]
        )
        monto = pedir_monto("Monto: ", datos["monto"])

        if descripcion is None or monto is None:
            return

        observacion = datos["observacion"]

        if descripcion == "Pago de tarjeta de crédito":
            print()
            print(
                "Para borrar la observación, escribí BORRAR."
            )
            observacion = pedir_observacion(observacion)
        else:
            observacion = ""

        lista[posicion] = (
            f"{tipo}|{fecha}|{descripcion}|{monto}|{observacion}"
        )
        guardar_datos(RUTA_ADICIONALES, lista)
        print("Registro modificado correctamente.")

    elif accion == "2":
        if not confirmar("Escribí SI para eliminar: "):
            print("Eliminación cancelada.")
            return

        lista.pop(posicion)
        guardar_datos(RUTA_ADICIONALES, lista)
        print("Registro eliminado correctamente.")


def menu_adicionales():
    while True:
        print()
        print("====================================")
        print(" INGRESOS Y EGRESOS ADICIONALES")
        print("====================================")
        print()
        print("1. Registrar")
        print("2. Ver, modificar o eliminar")
        print("3. Administrar conceptos")
        print("0. Volver")
        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            registrar_adicional()
        elif opcion == "2":
            gestionar_adicionales()
        elif opcion == "3":
            menu_conceptos_adicionales()
        elif opcion == "0":
            return
        else:
            print("Opción inválida.")


def separar_inversion(linea):
    datos = [dato.strip() for dato in linea.split("|")]

    if len(datos) != 3:
        return None

    try:
        convertir_fecha(datos[0])
        monto = int(datos[2])
    except ValueError:
        return None

    return {
        "fecha": datos[0],
        "descripcion": datos[1],
        "monto": monto,
    }


def registrar_inversion():
    print()
    print("====================================")
    print("        REGISTRAR INVERSIÓN")
    print("====================================")
    print()
    print("No suma como ingreso ni resta como egreso.")

    fecha = pedir_fecha()

    if fecha is None:
        return

    descripcion = pedir_texto("Descripción: ")
    monto = pedir_monto("Monto: ")

    if descripcion is None or monto is None:
        return

    registros = leer_datos(RUTA_INVERSIONES)
    registros.append(f"{fecha}|{descripcion}|{monto}")
    guardar_datos(RUTA_INVERSIONES, registros)
    print("Inversión registrada correctamente.")


def gestionar_inversiones():
    rango = pedir_rango_fechas()

    if rango is None:
        return

    fecha_desde, fecha_hasta = rango
    lista = leer_datos(RUTA_INVERSIONES)
    registros = registros_en_rango(
        RUTA_INVERSIONES,
        separar_inversion,
        fecha_desde,
        fecha_hasta
    )

    print()
    print("====================================")
    print("            INVERSIONES")
    print("====================================")

    if not registros:
        print("No hay inversiones en el período.")
        return

    for numero, (_, datos) in enumerate(registros, start=1):
        print(
            f"{numero}. {datos['fecha']} | "
            f"{datos['descripcion']} | "
            f"{formatear_monto(datos['monto'])}"
        )

    print()
    print("0. Volver")
    opcion = input("Seleccione una inversión: ").strip()

    if opcion == "0":
        return

    try:
        indice = int(opcion) - 1
        posicion, datos = registros[indice]
    except (ValueError, IndexError):
        print("Opción inválida.")
        return

    print("1. Modificar")
    print("2. Eliminar")
    print("0. Volver")
    accion = input("Seleccione una opción: ").strip()

    if accion == "1":
        fecha = input(f"Fecha [{datos['fecha']}]: ").strip()

        if fecha == "":
            fecha = datos["fecha"]
        else:
            try:
                convertir_fecha(fecha)
            except ValueError:
                print("Fecha inválida.")
                return

        descripcion = pedir_texto(
            "Descripción: ",
            datos["descripcion"]
        )
        monto = pedir_monto("Monto: ", datos["monto"])

        if descripcion is None or monto is None:
            return

        lista[posicion] = f"{fecha}|{descripcion}|{monto}"
        guardar_datos(RUTA_INVERSIONES, lista)
        print("Inversión modificada correctamente.")

    elif accion == "2":
        if not confirmar("Escribí SI para eliminar: "):
            print("Eliminación cancelada.")
            return

        lista.pop(posicion)
        guardar_datos(RUTA_INVERSIONES, lista)
        print("Inversión eliminada correctamente.")


def menu_inversiones():
    while True:
        print()
        print("====================================")
        print("            INVERSIONES")
        print("====================================")
        print()
        print("1. Registrar inversión")
        print("2. Ver, modificar o eliminar")
        print("0. Volver")
        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            registrar_inversion()
        elif opcion == "2":
            gestionar_inversiones()
        elif opcion == "0":
            return
        else:
            print("Opción inválida.")


def separar_prestamo(linea):
    datos = [dato.strip() for dato in linea.split("|")]

    if len(datos) != 7:
        return None

    try:
        convertir_fecha(datos[3])
        monto_recibido = int(datos[4])
        costo_total = int(datos[5])
        cantidad_cuotas = int(datos[6])
    except ValueError:
        return None

    return {
        "id": datos[0],
        "descripcion": datos[1],
        "banco": datos[2],
        "fecha": datos[3],
        "monto_recibido": monto_recibido,
        "costo_total": costo_total,
        "cantidad_cuotas": cantidad_cuotas,
    }


def separar_cuota(linea):
    datos = [dato.strip() for dato in linea.split("|")]

    if len(datos) != 4:
        return None

    try:
        numero = int(datos[1])
        convertir_fecha(datos[2])
        monto = int(datos[3])
    except ValueError:
        return None

    return {
        "prestamo_id": datos[0],
        "numero": numero,
        "fecha": datos[2],
        "monto": monto,
    }


def obtener_prestamos_validos():
    resultado = []

    for posicion, linea in enumerate(leer_datos(RUTA_PRESTAMOS)):
        datos = separar_prestamo(linea)

        if datos is not None:
            resultado.append((posicion, datos))

    return resultado


def cuotas_de_prestamo(prestamo_id):
    cuotas = []

    for posicion, linea in enumerate(
        leer_datos(RUTA_CUOTAS_PRESTAMOS)
    ):
        datos = separar_cuota(linea)

        if datos is not None and datos["prestamo_id"] == prestamo_id:
            cuotas.append((posicion, datos))

    return sorted(cuotas, key=lambda elemento: elemento[1]["numero"])


def estado_prestamo(prestamo):
    cuotas = cuotas_de_prestamo(prestamo["id"])
    total_pagado = sum(datos["monto"] for _, datos in cuotas)
    saldo = max(prestamo["costo_total"] - total_pagado, 0)
    pagado = total_pagado >= prestamo["costo_total"]
    fecha_pago_total = None

    if pagado and cuotas:
        fecha_pago_total = max(
            (datos["fecha"] for _, datos in cuotas),
            key=convertir_fecha
        )

    return {
        "cuotas": cuotas,
        "total_pagado": total_pagado,
        "saldo": saldo,
        "pagado": pagado,
        "fecha_pago_total": fecha_pago_total,
    }


def obtener_prestamos_por_estado(pagados, mes=None, anio=None):
    resultado = []

    for posicion, prestamo in obtener_prestamos_validos():
        estado = estado_prestamo(prestamo)

        if estado["pagado"] != pagados:
            continue

        if pagados and mes is not None and anio is not None:
            fecha_pago = convertir_fecha(estado["fecha_pago_total"])

            if fecha_pago.month != mes or fecha_pago.year != anio:
                continue

        resultado.append((posicion, prestamo, estado))

    if pagados:
        return sorted(
            resultado,
            key=lambda elemento: convertir_fecha(
                elemento[2]["fecha_pago_total"]
            ),
            reverse=True
        )

    return sorted(
        resultado,
        key=lambda elemento: convertir_fecha(elemento[1]["fecha"]),
        reverse=True
    )


def pedir_mes_anio():
    while True:
        print()
        print("Escribí el período en formato MM-AAAA.")
        print("Ejemplo: 07-2026")
        print("0. Volver")
        periodo = input("Período: ").strip()

        if periodo == "0":
            return None

        try:
            fecha = datetime.strptime(periodo, "%m-%Y")
            return fecha.month, fecha.year
        except ValueError:
            print("Período inválido. Usá el formato MM-AAAA.")


def registrar_prestamo():
    print()
    print("====================================")
    print("        REGISTRAR PRÉSTAMO")
    print("====================================")
    print()

    descripcion = pedir_texto("Descripción: ")
    banco = pedir_texto("Banco: ")
    fecha = pedir_fecha("Fecha de recepción (DD-MM-AAAA): ")
    monto_recibido = pedir_monto("Monto recibido: ")
    costo_total = pedir_monto("Total a devolver: ")
    cantidad_cuotas = pedir_monto("Cantidad de cuotas: ")

    if None in [
        descripcion,
        banco,
        fecha,
        monto_recibido,
        costo_total,
        cantidad_cuotas,
    ]:
        return

    if costo_total < monto_recibido:
        print()
        print(
            "El total a devolver no puede ser menor "
            "que el monto recibido."
        )
        return

    prestamos = leer_datos(RUTA_PRESTAMOS)
    ids = [
        datos["id"]
        for _, datos in obtener_prestamos_validos()
        if datos["id"].isdigit()
    ]
    nuevo_id = str(max([int(valor) for valor in ids], default=0) + 1)
    prestamos.append(
        f"{nuevo_id}|{descripcion}|{banco}|{fecha}|"
        f"{monto_recibido}|{costo_total}|{cantidad_cuotas}"
    )
    guardar_datos(RUTA_PRESTAMOS, prestamos)

    print()
    print("Préstamo registrado correctamente.")
    print("Monto recibido:", formatear_monto(monto_recibido))
    print("Total a devolver:", formatear_monto(costo_total))
    print(
        "Costo del préstamo:",
        formatear_monto(costo_total - monto_recibido)
    )


def mostrar_detalle_prestamo(prestamo):
    estado = estado_prestamo(prestamo)
    cuotas = estado["cuotas"]

    print()
    print("------------------------------------")
    print(prestamo["descripcion"], "-", prestamo["banco"])
    print("------------------------------------")
    print("Fecha de recepción:", prestamo["fecha"])
    print(
        "Monto recibido:",
        formatear_monto(prestamo["monto_recibido"])
    )
    print(
        "Total a devolver:",
        formatear_monto(prestamo["costo_total"])
    )
    print(
        "Costo total del préstamo:",
        formatear_monto(
            prestamo["costo_total"] - prestamo["monto_recibido"]
        )
    )
    print(
        "Cuotas pagadas:",
        f"{len(cuotas)} de {prestamo['cantidad_cuotas']}"
    )
    print(
        "Total pagado:",
        formatear_monto(estado["total_pagado"])
    )
    print("Saldo pendiente:", formatear_monto(estado["saldo"]))
    print("Estado:", "PAGADO" if estado["pagado"] else "ACTIVO")

    if estado["fecha_pago_total"] is not None:
        print("Fecha de pago total:", estado["fecha_pago_total"])


def seleccionar_prestamo(prestamos, titulo):
    pagina = 0
    por_pagina = 10

    if not prestamos:
        print()
        print("No hay préstamos para mostrar.")
        return None, None

    while True:
        total_paginas = (len(prestamos) + por_pagina - 1) // por_pagina
        inicio = pagina * por_pagina
        fin = inicio + por_pagina
        visibles = prestamos[inicio:fin]

        print()
        print("====================================")
        print(titulo.center(36))
        print("====================================")
        print(f"Página {pagina + 1} de {total_paginas}")
        print(
            f"Registros {inicio + 1} a "
            f"{min(fin, len(prestamos))} de {len(prestamos)}"
        )
        print()

        for numero, (_, prestamo, estado) in enumerate(
            visibles,
            start=1
        ):
            if estado["pagado"]:
                resumen = (
                    f"Pagado {estado['fecha_pago_total']} | "
                    f"{formatear_monto(estado['total_pagado'])}"
                )
            else:
                resumen = (
                    f"Saldo {formatear_monto(estado['saldo'])} | "
                    f"{len(estado['cuotas'])} de "
                    f"{prestamo['cantidad_cuotas']} cuotas"
                )

            print(
                f"{numero}. {prestamo['descripcion']} | "
                f"{prestamo['banco']} | {resumen}"
            )

        print()

        if pagina > 0:
            print("A. Página anterior")

        if pagina < total_paginas - 1:
            print("S. Página siguiente")

        print("0. Volver")
        opcion = input("Seleccione un préstamo: ").strip().upper()

        if opcion == "0":
            return None, None

        if opcion == "A" and pagina > 0:
            pagina -= 1
            continue

        if opcion == "S" and pagina < total_paginas - 1:
            pagina += 1
            continue

        try:
            posicion, prestamo, _ = visibles[int(opcion) - 1]
            return posicion, prestamo
        except (ValueError, IndexError):
            print("Opción inválida.")


def gestionar_prestamos_activos():
    prestamos = obtener_prestamos_por_estado(False)
    posicion, prestamo = seleccionar_prestamo(
        prestamos,
        "PRÉSTAMOS ACTIVOS"
    )

    if prestamo is not None:
        gestionar_prestamo_seleccionado(posicion, prestamo)


def historial_prestamos_pagados():
    periodo = pedir_mes_anio()

    if periodo is None:
        return

    mes, anio = periodo
    prestamos = obtener_prestamos_por_estado(True, mes, anio)
    posicion, prestamo = seleccionar_prestamo(
        prestamos,
        f"PAGADOS {mes:02d}-{anio}"
    )

    if prestamo is not None:
        gestionar_prestamo_seleccionado(posicion, prestamo)


def registrar_pago_cuota(prestamo):
    estado = estado_prestamo(prestamo)
    cuotas = estado["cuotas"]

    if estado["pagado"]:
        print("Este préstamo ya está totalmente pagado.")
        return

    numeros_pagados = {datos["numero"] for _, datos in cuotas}
    numero = 1

    while numero in numeros_pagados:
        numero += 1

    if numero > prestamo["cantidad_cuotas"]:
        print("Todas las cuotas ya están registradas.")
        return

    fecha = pedir_fecha("Fecha de pago (DD-MM-AAAA): ")

    if fecha is None:
        return

    sugerido = round(
        prestamo["costo_total"] / prestamo["cantidad_cuotas"]
    )
    print()
    print("Cuota:", numero, "de", prestamo["cantidad_cuotas"])
    print("Monto estimado:", formatear_monto(sugerido))
    print("Ingresá el monto realmente pagado.")
    monto = pedir_monto("Monto de la cuota: ")

    if monto is None:
        return

    if monto > estado["saldo"]:
        print()
        print(
            "El monto supera el saldo pendiente de",
            formatear_monto(estado["saldo"])
        )
        print("Ingresá el pago real sin superar el saldo.")
        return

    registros = leer_datos(RUTA_CUOTAS_PRESTAMOS)
    registros.append(
        f"{prestamo['id']}|{numero}|{fecha}|{monto}"
    )
    guardar_datos(RUTA_CUOTAS_PRESTAMOS, registros)
    print()
    print("Cuota registrada correctamente.")
    print(
        "El monto completo de la cuota se contará "
        "como egreso del mes."
    )

    if monto == estado["saldo"]:
        print("El préstamo quedó totalmente pagado.")
        print(
            "Desde ahora aparecerá en el historial "
            "del período correspondiente."
        )


def modificar_prestamo(posicion, prestamo):
    lista = leer_datos(RUTA_PRESTAMOS)
    descripcion = pedir_texto(
        "Descripción: ",
        prestamo["descripcion"]
    )
    banco = pedir_texto("Banco: ", prestamo["banco"])
    fecha = input(f"Fecha [{prestamo['fecha']}]: ").strip()

    if fecha == "":
        fecha = prestamo["fecha"]
    else:
        try:
            convertir_fecha(fecha)
        except ValueError:
            print("Fecha inválida.")
            return

    monto_recibido = pedir_monto(
        "Monto recibido: ",
        prestamo["monto_recibido"]
    )
    costo_total = pedir_monto(
        "Total a devolver: ",
        prestamo["costo_total"]
    )
    cantidad_cuotas = pedir_monto(
        "Cantidad de cuotas: ",
        prestamo["cantidad_cuotas"]
    )

    if None in [
        descripcion,
        banco,
        monto_recibido,
        costo_total,
        cantidad_cuotas,
    ]:
        return

    if costo_total < monto_recibido:
        print("El total a devolver no puede ser menor al monto recibido.")
        return

    if cantidad_cuotas < len(cuotas_de_prestamo(prestamo["id"])):
        print(
            "La cantidad de cuotas no puede ser menor "
            "a las cuotas ya pagadas."
        )
        return

    lista[posicion] = (
        f"{prestamo['id']}|{descripcion}|{banco}|{fecha}|"
        f"{monto_recibido}|{costo_total}|{cantidad_cuotas}"
    )
    guardar_datos(RUTA_PRESTAMOS, lista)
    print("Préstamo modificado correctamente.")


def gestionar_cuotas(prestamo):
    cuotas = cuotas_de_prestamo(prestamo["id"])
    pagina = 0
    por_pagina = 10

    if not cuotas:
        print("Todavía no hay cuotas pagadas.")
        return

    while True:
        total_paginas = (len(cuotas) + por_pagina - 1) // por_pagina
        inicio = pagina * por_pagina
        visibles = cuotas[inicio:inicio + por_pagina]

        print()
        print("PAGOS REGISTRADOS")
        print(f"Página {pagina + 1} de {total_paginas}")
        print()

        for numero_visible, (_, datos) in enumerate(visibles, start=1):
            print(
                f"{numero_visible}. Cuota {datos['numero']} | "
                f"{datos['fecha']} | {formatear_monto(datos['monto'])}"
            )

        print()

        if pagina > 0:
            print("A. Página anterior")

        if pagina < total_paginas - 1:
            print("S. Página siguiente")

        print("0. Volver")
        opcion = input("Seleccione una cuota: ").strip().upper()

        if opcion == "0":
            return

        if opcion == "A" and pagina > 0:
            pagina -= 1
            continue

        if opcion == "S" and pagina < total_paginas - 1:
            pagina += 1
            continue

        try:
            posicion, datos = visibles[int(opcion) - 1]
            break
        except (ValueError, IndexError):
            print("Opción inválida.")

    print("1. Modificar fecha o monto")
    print("2. Eliminar")
    print("0. Volver")
    accion = input("Seleccione una opción: ").strip()
    lista = leer_datos(RUTA_CUOTAS_PRESTAMOS)

    if accion == "1":
        fecha = input(f"Fecha [{datos['fecha']}]: ").strip()

        if fecha == "":
            fecha = datos["fecha"]
        else:
            try:
                convertir_fecha(fecha)
            except ValueError:
                print("Fecha inválida.")
                return

        monto = pedir_monto("Monto: ", datos["monto"])

        if monto is None:
            return

        lista[posicion] = (
            f"{datos['prestamo_id']}|{datos['numero']}|"
            f"{fecha}|{monto}"
        )
        guardar_datos(RUTA_CUOTAS_PRESTAMOS, lista)
        print("Cuota modificada correctamente.")

    elif accion == "2":
        if not confirmar("Escribí SI para eliminar: "):
            print("Eliminación cancelada.")
            return

        lista.pop(posicion)
        guardar_datos(RUTA_CUOTAS_PRESTAMOS, lista)
        print("Cuota eliminada correctamente.")


def gestionar_prestamo_seleccionado(posicion, prestamo):
    while True:
        mostrar_detalle_prestamo(prestamo)
        estado = estado_prestamo(prestamo)
        print()

        if not estado["pagado"]:
            print("1. Registrar pago de cuota")

        print("2. Modificar préstamo")
        print("3. Modificar o eliminar una cuota")
        print("4. Eliminar préstamo")
        print("0. Volver")
        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1" and not estado["pagado"]:
            registrar_pago_cuota(prestamo)

        elif opcion == "2":
            modificar_prestamo(posicion, prestamo)
            datos_actualizados = separar_prestamo(
                leer_datos(RUTA_PRESTAMOS)[posicion]
            )
            if datos_actualizados is not None:
                prestamo = datos_actualizados

        elif opcion == "3":
            gestionar_cuotas(prestamo)

        elif opcion == "4":
            if not confirmar(
                "Escribí SI para eliminar el préstamo y sus cuotas: "
            ):
                print("Eliminación cancelada.")
                continue

            prestamos = leer_datos(RUTA_PRESTAMOS)
            prestamos.pop(posicion)
            guardar_datos(RUTA_PRESTAMOS, prestamos)

            cuotas = leer_datos(RUTA_CUOTAS_PRESTAMOS)
            cuotas = [
                linea
                for linea in cuotas
                if (
                    separar_cuota(linea) is None
                    or separar_cuota(linea)["prestamo_id"]
                    != prestamo["id"]
                )
            ]
            guardar_datos(RUTA_CUOTAS_PRESTAMOS, cuotas)
            print("Préstamo y cuotas eliminados correctamente.")
            return

        elif opcion == "0":
            return
        else:
            print("Opción inválida.")


def menu_prestamos():
    while True:
        print()
        print("====================================")
        print("        PRÉSTAMOS Y CUOTAS")
        print("====================================")
        print()
        print("1. Registrar préstamo")
        print("2. Ver préstamos activos")
        print("3. Historial de préstamos pagados")
        print("0. Volver")
        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            registrar_prestamo()
        elif opcion == "2":
            gestionar_prestamos_activos()
        elif opcion == "3":
            historial_prestamos_pagados()
        elif opcion == "0":
            return
        else:
            print("Opción inválida.")


def resumen_adicionales(fecha_desde, fecha_hasta):
    ingresos = 0
    egresos = 0

    for _, datos in registros_en_rango(
        RUTA_ADICIONALES,
        separar_adicional,
        fecha_desde,
        fecha_hasta
    ):
        if datos["tipo"] == "Ingreso":
            ingresos += datos["monto"]
        else:
            egresos += datos["monto"]

    return ingresos, egresos


def resumen_inversiones(fecha_desde, fecha_hasta):
    return sum(
        datos["monto"]
        for _, datos in registros_en_rango(
            RUTA_INVERSIONES,
            separar_inversion,
            fecha_desde,
            fecha_hasta
        )
    )


def resumen_cuotas(fecha_desde, fecha_hasta):
    total = 0
    detalle = []
    prestamos = {
        datos["id"]: datos
        for _, datos in obtener_prestamos_validos()
    }

    for _, cuota in registros_en_rango(
        RUTA_CUOTAS_PRESTAMOS,
        separar_cuota,
        fecha_desde,
        fecha_hasta
    ):
        total += cuota["monto"]
        prestamo = prestamos.get(cuota["prestamo_id"])
        nombre = (
            prestamo["descripcion"]
            if prestamo is not None
            else "Préstamo"
        )
        detalle.append((nombre, cuota))

    return total, detalle


def resumen_nomina_liquidada(fecha_desde, fecha_hasta):
    resumen = {
        "sueldo_bruto": 0,
        "descuento_ausencias": 0,
        "descuento_reposos": 0,
        "sueldo_bruto_ajustado": 0,
        "comisiones": 0,
        "remuneracion_bruta": 0,
        "descuento_ips": 0,
        "adelantos": 0,
        "otros_descuentos": 0,
        "neto_cobrar": 0,
        "salida_caja": 0,
        "egreso_planilla": 0,
        "diferencia_con_salida_caja": 0,
    }
    detalle = []

    for linea in leer_datos(RUTA_LIQUIDACIONES):
        partes = [
            parte.strip()
            for parte in linea.split("|")
        ]

        if len(partes) not in [9, 15, 16]:
            continue

        try:
            fecha_periodo = datetime.strptime(
                partes[2],
                "%m-%Y"
            )
            sueldo_bruto = int(partes[5])
            descuento_ips = int(partes[6])
            neto_cobrar = int(partes[7])

            if len(partes) in [15, 16]:
                descuento_ausencias = int(partes[11])
                descuento_reposos = int(partes[12])
                adelantos = int(partes[13])
                otros_descuentos = int(partes[14])
                comisiones = (
                    int(partes[15])
                    if len(partes) == 16
                    else 0
                )
            else:
                descuento_ausencias = 0
                descuento_reposos = 0
                adelantos = 0
                otros_descuentos = 0
                comisiones = 0
        except ValueError:
            continue

        if not (
            fecha_desde.year == fecha_periodo.year
            and fecha_desde.month == fecha_periodo.month
            or fecha_hasta.year == fecha_periodo.year
            and fecha_hasta.month == fecha_periodo.month
            or fecha_desde < fecha_periodo < fecha_hasta
        ):
            continue

        sueldo_bruto_ajustado = max(
            0,
            sueldo_bruto
            - descuento_ausencias
            - descuento_reposos,
        )
        remuneracion_bruta = (
            sueldo_bruto_ajustado + comisiones
        )
        salida_caja = neto_cobrar + adelantos
        egreso_planilla = remuneracion_bruta
        diferencia_con_salida_caja = (
            egreso_planilla - salida_caja
        )
        valores = {
            "sueldo_bruto": sueldo_bruto,
            "descuento_ausencias": descuento_ausencias,
            "descuento_reposos": descuento_reposos,
            "sueldo_bruto_ajustado": sueldo_bruto_ajustado,
            "comisiones": comisiones,
            "remuneracion_bruta": remuneracion_bruta,
            "descuento_ips": descuento_ips,
            "adelantos": adelantos,
            "otros_descuentos": otros_descuentos,
            "neto_cobrar": neto_cobrar,
            "salida_caja": salida_caja,
            "egreso_planilla": egreso_planilla,
            "diferencia_con_salida_caja": (
                diferencia_con_salida_caja
            ),
        }

        for concepto, monto_concepto in valores.items():
            resumen[concepto] += monto_concepto

        detalle.append(
            {
                "cedula": partes[0],
                "nombre": partes[1],
                "periodo": partes[2],
                **valores,
            }
        )

    return resumen, detalle


def resumen_sueldos_liquidados(fecha_desde, fecha_hasta):
    resumen, detalle = resumen_nomina_liquidada(
        fecha_desde,
        fecha_hasta,
    )
    return resumen["egreso_planilla"], detalle


def calcular_totales_generales(fecha_desde, fecha_hasta):
    total_ingresos = 0
    total_egresos = 0

    for unidad in UNIDADES:
        (
            ingresos,
            egresos,
            _,
            _,
            _,
        ) = calcular_resumen_unidad(
            unidad,
            fecha_desde,
            fecha_hasta
        )

        total_ingresos += ingresos
        total_egresos += egresos

    ingresos_adicionales, egresos_adicionales = (
        resumen_adicionales(fecha_desde, fecha_hasta)
    )
    total_cuotas, _ = resumen_cuotas(
        fecha_desde,
        fecha_hasta
    )
    nomina, _ = resumen_nomina_liquidada(
        fecha_desde,
        fecha_hasta
    )
    total_sueldos = nomina["egreso_planilla"]
    egresos_sin_nomina = (
        total_egresos
        + egresos_adicionales
        + total_cuotas
    )
    salida_caja_total = (
        egresos_sin_nomina + nomina["salida_caja"]
    )

    total_ingresos += ingresos_adicionales
    total_egresos += (
        egresos_adicionales
        + total_cuotas
        + total_sueldos
    )

    return {
        "ingresos": total_ingresos,
        "egresos": total_egresos,
        "resultado": total_ingresos - total_egresos,
        "ingresos_adicionales": ingresos_adicionales,
        "egresos_adicionales": egresos_adicionales,
        "cuotas": total_cuotas,
        "sueldos_funcionarios": total_sueldos,
        "nomina": nomina,
        "egresos_sin_nomina": egresos_sin_nomina,
        "salida_caja_total": salida_caja_total,
        "diferencia_egreso_caja": (
            total_egresos - salida_caja_total
        ),
    }


def calcular_indicadores_cierre(
    fecha_desde,
    fecha_hasta,
    total_sueldos_socios=0
):
    totales = calcular_totales_generales(
        fecha_desde,
        fecha_hasta
    )
    utilidad_mes = totales["resultado"]
    utilidad_positiva = max(utilidad_mes, 0)
    margen_porcentual = 0

    if totales["ingresos"] != 0:
        margen_porcentual = (
            utilidad_mes / totales["ingresos"] * 100
        )

    fondo_calculado = (
        utilidad_positiva
        * PORCENTAJE_FONDO_ESTABILIDAD
        // 100
    )

    return {
        **totales,
        # Se conservan estas claves con valor neutro para que versiones
        # anteriores de la interfaz sigan abriendo. Los sueldos de Sol y
        # Rodrigo se registran como liquidaciones normales en RR. HH.
        "resultado_antes_socios": utilidad_mes,
        "total_sueldos_socios": 0,
        "utilidad_mes": utilidad_mes,
        "margen_porcentual": margen_porcentual,
        "fondo_calculado": fondo_calculado,
        "utilidad_repartible_calculada": (
            utilidad_positiva - fondo_calculado
        ),
    }


def separar_registro_fondo(linea):
    partes = [parte.strip() for parte in linea.split("|")]

    if len(partes) != 5:
        return None

    try:
        fecha = datetime.strptime(partes[0], "%m-%Y")
        monto_calculado = int(partes[1])
        monto_aplicado = int(partes[2])
    except ValueError:
        return None

    modo = partes[3].upper()

    if (
        monto_calculado < 0
        or monto_aplicado < 0
        or modo not in ["AUTOMATICO", "MANUAL"]
    ):
        return None

    return {
        "periodo": fecha.strftime("%m-%Y"),
        "monto_calculado": monto_calculado,
        "monto_aplicado": monto_aplicado,
        "modo": modo,
        "observacion": partes[4],
    }


def crear_linea_fondo(registro):
    observacion = (
        registro["observacion"].strip().replace("|", "/")
        or "-"
    )
    return " | ".join(
        [
            registro["periodo"],
            str(registro["monto_calculado"]),
            str(registro["monto_aplicado"]),
            registro["modo"],
            observacion,
        ]
    )


def obtener_registros_fondo():
    registros = []

    for posicion, linea in enumerate(
        leer_datos(RUTA_FONDO_ESTABILIDAD)
    ):
        registro = separar_registro_fondo(linea)

        if registro is not None:
            registros.append((posicion, registro))

    return registros


def obtener_registro_fondo(periodo):
    for posicion, registro in obtener_registros_fondo():
        if registro["periodo"] == periodo:
            return posicion, registro

    return None


def guardar_fondo_del_cierre(periodo, monto_calculado):
    lista = leer_datos(RUTA_FONDO_ESTABILIDAD)
    existente = obtener_registro_fondo(periodo)

    if existente is None:
        registro = {
            "periodo": periodo,
            "monto_calculado": monto_calculado,
            "monto_aplicado": monto_calculado,
            "modo": "AUTOMATICO",
            "observacion": "Generado por el cierre mensual",
        }
        lista.append(crear_linea_fondo(registro))
    else:
        posicion, registro = existente
        registro["monto_calculado"] = monto_calculado

        if registro["modo"] == "AUTOMATICO":
            registro["monto_aplicado"] = monto_calculado
            registro["observacion"] = (
                "Actualizado por el cierre mensual"
            )

        lista[posicion] = crear_linea_fondo(registro)

    guardar_datos(RUTA_FONDO_ESTABILIDAD, lista)
    return obtener_registro_fondo(periodo)[1]


def es_mes_completo(fecha_desde, fecha_hasta):
    if (
        fecha_desde.year != fecha_hasta.year
        or fecha_desde.month != fecha_hasta.month
        or fecha_desde.day != 1
    ):
        return False

    siguiente_mes = fecha_hasta.replace(day=28)

    while True:
        try:
            siguiente_mes = siguiente_mes.replace(
                day=siguiente_mes.day + 1
            )
        except ValueError:
            break

    return fecha_hasta.day == siguiente_mes.day


def ver_cierre_mensual():
    rango = pedir_rango_fechas()

    if rango is None:
        print()
        print("Volviendo al menú de movimientos...")
        return

    fecha_desde, fecha_hasta = rango
    total_ingresos = 0
    total_egresos = 0
    ingresos_adicionales, egresos_adicionales = (
        resumen_adicionales(fecha_desde, fecha_hasta)
    )
    total_inversiones = resumen_inversiones(
        fecha_desde,
        fecha_hasta
    )
    total_cuotas, detalle_cuotas = resumen_cuotas(
        fecha_desde,
        fecha_hasta
    )
    nomina, detalle_sueldos = (
        resumen_nomina_liquidada(
            fecha_desde,
            fecha_hasta
        )
    )
    total_sueldos = nomina["egreso_planilla"]

    print()
    print("====================================")
    print("            CIERRE MENSUAL")
    print("====================================")
    print()
    print(
        "Período:",
        fecha_desde.strftime("%d-%m-%Y"),
        "al",
        fecha_hasta.strftime("%d-%m-%Y")
    )

    for unidad in UNIDADES:
        (
            ingresos,
            egresos,
            resultado,
            transferencias_recibidas,
            transferencias_enviadas,
        ) = calcular_resumen_unidad(
            unidad,
            fecha_desde,
            fecha_hasta
        )

        total_ingresos += ingresos
        total_egresos += egresos

        print()
        print("------------------------------------")
        print(unidad)
        print("------------------------------------")
        print("INGRESOS:", formatear_monto(ingresos))
        print("EGRESOS:", formatear_monto(egresos))
        print("RESULTADO:", formatear_monto(resultado))
        print(
            "TRANSFERENCIAS RECIBIDAS:",
            formatear_monto(transferencias_recibidas)
        )
        print(
            "TRANSFERENCIAS ENVIADAS:",
            formatear_monto(transferencias_enviadas)
        )

    ver_transferencias_internas(fecha_desde, fecha_hasta)
    ver_depositos_bancarios(fecha_desde, fecha_hasta)
    ver_cobros_externos(fecha_desde, fecha_hasta)

    print()
    print("====================================")
    print("      MOVIMIENTOS ADICIONALES")
    print("====================================")
    print(
        "INGRESOS ADICIONALES:",
        formatear_monto(ingresos_adicionales)
    )
    print(
        "EGRESOS ADICIONALES:",
        formatear_monto(egresos_adicionales)
    )

    print()
    print("====================================")
    print("      CUOTAS DE PRÉSTAMOS PAGADAS")
    print("====================================")

    if not detalle_cuotas:
        print("No hay cuotas pagadas en el período.")
    else:
        for nombre, cuota in detalle_cuotas:
            print(
                f"{cuota['fecha']} | {nombre} | "
                f"Cuota {cuota['numero']} | "
                f"{formatear_monto(cuota['monto'])}"
            )

    print("TOTAL CUOTAS:", formatear_monto(total_cuotas))
    print(
        "Las cuotas completas se incluyen en los egresos."
    )

    print()
    print("====================================")
    print("          SUELDOS LIQUIDADOS")
    print("====================================")

    if not detalle_sueldos:
        print("No hay sueldos liquidados en el período.")
    else:
        for sueldo in detalle_sueldos:
            print(
                f"{sueldo['periodo']} | "
                f"{sueldo['nombre']} | "
                f"Neto {formatear_monto(sueldo['neto_cobrar'])} | "
                f"Adelantos {formatear_monto(sueldo['adelantos'])} | "
                f"Salida {formatear_monto(sueldo['salida_caja'])}"
            )

    print(
        "REMUNERACIÓN BRUTA:",
        formatear_monto(nomina["remuneracion_bruta"])
    )
    print(
        "DESCUENTO IPS:",
        formatear_monto(nomina["descuento_ips"])
    )
    print(
        "OTROS DESCUENTOS:",
        formatear_monto(nomina["otros_descuentos"])
    )
    print(
        "ADELANTOS YA PAGADOS:",
        formatear_monto(nomina["adelantos"])
    )
    print(
        "NETO PAGADO AL LIQUIDAR:",
        formatear_monto(nomina["neto_cobrar"])
    )
    print(
        "TOTAL NÓMINA INCLUIDA EN EGRESOS:",
        formatear_monto(nomina["egreso_planilla"])
    )
    print(
        "SALIDA REAL DE CAJA POR NÓMINA:",
        formatear_monto(nomina["salida_caja"])
    )
    print(
        "El total de egresos usa la remuneración bruta para "
        "coincidir con la planilla. No vuelvas a cargar sueldos "
        "o adelantos como movimientos."
    )
    print(
        "El pago de IPS se cuenta por separado cuando está "
        "registrado en movimientos adicionales."
    )

    print()
    print("====================================")
    print("            INVERSIONES")
    print("====================================")
    print("TOTAL INVERTIDO:", formatear_monto(total_inversiones))
    print("Las inversiones no suman ni restan del resultado.")

    total_ingresos += ingresos_adicionales
    total_egresos += (
        egresos_adicionales
        + total_cuotas
        + total_sueldos
    )
    indicadores = calcular_indicadores_cierre(
        fecha_desde,
        fecha_hasta
    )
    periodo = fecha_desde.strftime("%m-%Y")
    registro_fondo = None

    if es_mes_completo(fecha_desde, fecha_hasta):
        registro_fondo = guardar_fondo_del_cierre(
            periodo,
            indicadores["fondo_calculado"]
        )

    fondo_aplicado = indicadores["fondo_calculado"]

    if registro_fondo is not None:
        fondo_aplicado = registro_fondo["monto_aplicado"]

    utilidad_repartible = max(
        indicadores["utilidad_mes"] - fondo_aplicado,
        0
    )

    print()
    print("====================================")
    print("          RESULTADO DEL MES")
    print("====================================")
    print("TOTAL INGRESOS:", formatear_monto(total_ingresos))
    print("TOTAL EGRESOS:", formatear_monto(total_egresos))
    print(
        "UTILIDAD DEL MES:",
        formatear_monto(indicadores["utilidad_mes"])
    )
    print(
        "MARGEN PORCENTUAL:",
        formatear_porcentaje(
            indicadores["margen_porcentual"]
        ) + "%"
    )
    print(
        f"FONDO DE ESTABILIDAD "
        f"({PORCENTAJE_FONDO_ESTABILIDAD}%):",
        formatear_monto(fondo_aplicado)
    )
    print(
        "UTILIDAD REPARTIBLE:",
        formatear_monto(utilidad_repartible)
    )

    if indicadores["utilidad_mes"] <= 0:
        print(
            "No se genera fondo ni utilidad repartible "
            "porque la utilidad del mes no es positiva."
        )

    if registro_fondo is None:
        print(
            "Consulta parcial: el fondo no se guardó. "
            "Para registrarlo, usá desde el día 1 hasta "
            "el último día del mismo mes."
        )
    elif registro_fondo["modo"] == "MANUAL":
        print(
            "Fondo aplicado: AJUSTADO MANUALMENTE "
            "desde Socios."
        )
        print(
            "Fondo calculado por los movimientos:",
            formatear_monto(
                registro_fondo["monto_calculado"]
            )
        )

    print("====================================")
    input("Presioná ENTER para volver...")


def menu_movimientos():
    while True:
        print()
        print("====================================")
        print("           MOVIMIENTOS")
        print("====================================")
        print()
        print("1. Cargar día")
        print("2. Ver, modificar o eliminar movimientos")
        print("3. Ingresos y egresos adicionales")
        print("4. Inversiones")
        print("5. Préstamos y cuotas")
        print("6. Cierre mensual")
        print("7. Sobres de venta PC")
        print("0. Volver")
        print()

        opcion = input("Seleccione una opción: ").strip()

        if opcion == "1":
            cargar_dia()

        elif opcion == "2":
            gestionar_movimientos()

        elif opcion == "3":
            menu_adicionales()

        elif opcion == "4":
            menu_inversiones()

        elif opcion == "5":
            menu_prestamos()

        elif opcion == "6":
            ver_cierre_mensual()

        elif opcion == "7":
            import SobresVenta
            SobresVenta.menu_sobres_pc()

        elif opcion == "0":
            return

        else:
            print()
            print("Opción inválida.")
