from datetime import datetime
from pathlib import Path

from Utilidades import formatear_monto
from datos import leer_datos, guardar_datos

RUTA_FUNCIONARIOS = (
    Path(__file__).resolve().parent
    / "Datos"
    / "funcionarios.txt"
)

RUTA_SALARIOS_MINIMOS = (
    Path(__file__).resolve().parent
    / "Datos"
    / "salarios_minimos.txt"
)

SALARIO_MINIMO_INICIAL = 3044000
FECHA_VIGENCIA_INICIAL = "01-07-2026"

UNIDADES = [
    "Administración",
    "PC",
    "MVPC",
    "P2",
    "MVP2",
]

MODALIDADES_PAGO = [
    "Diario",
    "Semanal",
    "Mensual",
]


def convertir_fecha(fecha):
    return datetime.strptime(
        fecha,
        "%d-%m-%Y"
    )


def formatear_cedula(cedula):
    cedula_limpia = (
        cedula
        .replace(".", "")
        .replace(" ", "")
    )

    if cedula_limpia.isdigit():
        return f"{int(cedula_limpia):,}".replace(",", ".")

    return cedula


def pedir_fecha(mensaje):
    while True:
        fecha = input(mensaje).strip()

        if fecha == "0":
            return None

        try:
            convertir_fecha(fecha)
            return fecha
        except ValueError:
            print(
                "Fecha inválida. Usá el formato "
                "DD-MM-AAAA."
            )

def crear_linea_salario(fecha, monto):
    return f"{fecha} | {monto}"


def separar_salario(linea):
    partes = [
        parte.strip()
        for parte in linea.split("|")
    ]

    if len(partes) != 2:
        return None

    try:
        fecha = convertir_fecha(partes[0])
        monto = int(partes[1])
    except ValueError:
        return None

    if monto <= 0:
        return None

    return {
        "fecha_texto": partes[0],
        "fecha": fecha,
        "monto": monto,
    }


def obtener_historial_salarios():
    lineas = leer_datos(
        RUTA_SALARIOS_MINIMOS
    )

    salarios = []

    for linea in lineas:
        datos = separar_salario(linea)

        if datos is not None:
            salarios.append(datos)

    if len(salarios) == 0:
        linea_inicial = crear_linea_salario(
            FECHA_VIGENCIA_INICIAL,
            SALARIO_MINIMO_INICIAL
        )

        guardar_datos(
            RUTA_SALARIOS_MINIMOS,
            [linea_inicial]
        )

        salarios.append({
            "fecha_texto": FECHA_VIGENCIA_INICIAL,
            "fecha": convertir_fecha(
                FECHA_VIGENCIA_INICIAL
            ),
            "monto": SALARIO_MINIMO_INICIAL,
        })

    salarios.sort(
        key=lambda salario: salario["fecha"]
    )

    return salarios


def obtener_salario_minimo(fecha=None):
    if fecha is None:
        fecha_consulta = datetime.now()
    elif isinstance(fecha, str):
        fecha_consulta = convertir_fecha(fecha)
    else:
        fecha_consulta = fecha

    salario_encontrado = None

    for salario in obtener_historial_salarios():
        if salario["fecha"] <= fecha_consulta:
            salario_encontrado = salario
        else:
            break

    if salario_encontrado is None:
        return None

    return salario_encontrado["monto"]


def ver_salario_minimo_vigente():
    fecha_actual = datetime.now()
    salario_vigente = None

    for salario in obtener_historial_salarios():
        if salario["fecha"] <= fecha_actual:
            salario_vigente = salario
        else:
            break

    print()
    print("====================================")
    print("       SALARIO MÍNIMO VIGENTE")
    print("====================================")
    print()

    if salario_vigente is None:
        print(
            "No existe un salario mínimo vigente "
            "para la fecha actual."
        )
        return

    print(
        "Monto:",
        formatear_monto(
            salario_vigente["monto"]
        ),
        "Gs."
    )
    print(
        "Vigente desde:",
        salario_vigente["fecha_texto"]
    )


def ver_historial_salarios():
    salarios = obtener_historial_salarios()

    print()
    print("====================================")
    print("    HISTORIAL DE SALARIOS MÍNIMOS")
    print("====================================")
    print()

    for numero, salario in enumerate(
        salarios,
        start=1
    ):
        print(
            f"{numero}. "
            f"{salario['fecha_texto']} | "
            f"{formatear_monto(salario['monto'])} Gs."
        )

def registrar_reajuste_salario():
    print()
    print("====================================")
    print("   REGISTRAR REAJUSTE DEL SALARIO")
    print("====================================")
    print()
    print("Ingresá 0 para cancelar.")
    print()

    fecha_vigencia = pedir_fecha(
        "Fecha de vigencia (DD-MM-AAAA): "
    )

    if fecha_vigencia is None:
        return

    monto = pedir_monto(
        "Nuevo salario mínimo: "
    )

    if monto is None:
        return

    salarios = obtener_historial_salarios()
    fecha_nueva = convertir_fecha(fecha_vigencia)

    for salario in salarios:
        if salario["fecha"] == fecha_nueva:
            print()
            print(
                "Ya existe un salario registrado "
                "para esa fecha."
            )
            return

    print()
    print("Fecha de vigencia:", fecha_vigencia)
    print(
        "Nuevo salario mínimo:",
        formatear_monto(monto),
        "Gs."
    )
    print()

    confirmacion = input(
        "¿Guardar este reajuste? (S/N): "
    ).strip().lower()

    if confirmacion != "s":
        print()
        print("Registro cancelado.")
        return

    lineas = leer_datos(
        RUTA_SALARIOS_MINIMOS
    )

    lineas.append(
        crear_linea_salario(
            fecha_vigencia,
            monto
        )
    )

    lineas_validas = []

    for linea in lineas:
        datos = separar_salario(linea)

        if datos is not None:
            lineas_validas.append(datos)

    lineas_validas.sort(
        key=lambda salario: salario["fecha"]
    )

    lineas_ordenadas = [
        crear_linea_salario(
            salario["fecha_texto"],
            salario["monto"]
        )
        for salario in lineas_validas
    ]

    guardar_datos(
        RUTA_SALARIOS_MINIMOS,
        lineas_ordenadas
    )

    print()
    print("Reajuste registrado correctamente.")


def menu_salario_minimo():
    while True:
        print()
        print("====================================")
        print("     CONFIGURACIÓN DEL SALARIO")
        print("====================================")
        print()
        print("1. Ver salario mínimo vigente")
        print("2. Registrar nuevo reajuste")
        print("3. Ver historial de reajustes")
        print("0. Volver")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            ver_salario_minimo_vigente()

        elif opcion == "2":
            registrar_reajuste_salario()

        elif opcion == "3":
            ver_historial_salarios()

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")

def pedir_monto(mensaje, permitir_vacio=False):
    while True:
        valor = input(mensaje).strip()

        if valor == "0":
            return None

        if permitir_vacio and valor == "":
            return ""

        valor_limpio = (
            valor
            .replace(".", "")
            .replace(",", "")
            .replace(" ", "")
        )

        try:
            monto = int(valor_limpio)

            if monto < 0:
                raise ValueError

            return monto
        except ValueError:
            print(
                "Monto inválido. Ingresá solamente "
                "números."
            )


def elegir_opcion(
    titulo,
    opciones,
    permitir_conservar=False
):
    while True:
        print()
        print(titulo)
        print()

        if permitir_conservar:
            print("ENTER. Conservar dato actual")

        for numero, opcion in enumerate(
            opciones,
            start=1
        ):
            print(f"{numero}. {opcion}")

        print("0. Cancelar")
        print()

        seleccion = input(
            "Seleccione una opción: "
        ).strip()

        if permitir_conservar and seleccion == "":
            return "CONSERVAR"

        if seleccion == "0":
            return None

        try:
            indice = int(seleccion) - 1

            if 0 <= indice < len(opciones):
                return opciones[indice]
        except ValueError:
            pass

        print("Opción inválida.")


def limpiar_texto(texto):
    return texto.replace("|", "/").strip()


def crear_linea_funcionario(datos):
    return " | ".join([
        datos["nombre"],
        datos["cedula"],
        datos["fecha_ingreso"],
        datos["unidad"],
        datos["cargo"],
        datos["modalidad"],
        datos["tipo_sueldo"],
        str(datos["sueldo_base"]),
        datos["ips"],
        datos["horario"],
        datos["estado"],
        datos["observaciones"],
    ])


def separar_funcionario(linea):
    partes = [
        parte.strip()
        for parte in linea.split("|")
    ]

    # Formato anterior: funcionarios ya registrados
    if len(partes) == 11:
        try:
            sueldo_base = int(partes[6])
            convertir_fecha(partes[2])
        except ValueError:
            return None

        return {
            "nombre": partes[0],
            "cedula": partes[1],
            "fecha_ingreso": partes[2],
            "unidad": partes[3],
            "cargo": partes[4],
            "modalidad": partes[5],
            "tipo_sueldo": "Manual",
            "sueldo_base": sueldo_base,
            "ips": partes[7],
            "horario": partes[8],
            "estado": partes[9],
            "observaciones": partes[10],
        }

    # Nuevo formato con tipo de sueldo
    if len(partes) == 12:
        try:
            sueldo_base = int(partes[7])
            convertir_fecha(partes[2])
        except ValueError:
            return None

        return {
            "nombre": partes[0],
            "cedula": partes[1],
            "fecha_ingreso": partes[2],
            "unidad": partes[3],
            "cargo": partes[4],
            "modalidad": partes[5],
            "tipo_sueldo": partes[6],
            "sueldo_base": sueldo_base,
            "ips": partes[8],
            "horario": partes[9],
            "estado": partes[10],
            "observaciones": partes[11],
        }

    return None

def calcular_sueldo_funcionario(datos, fecha=None):
    if datos["tipo_sueldo"] == "Salario mínimo":
        salario_minimo = obtener_salario_minimo(fecha)

        if salario_minimo is not None:
            return salario_minimo

    return datos["sueldo_base"]

def obtener_funcionarios_validos():
    funcionarios = []

    for linea in leer_datos(RUTA_FUNCIONARIOS):
        if separar_funcionario(linea) is not None:
            funcionarios.append(linea)

    return funcionarios

def cedula_ya_registrada(cedula):
    cedula_buscada = cedula.lower().strip()

    for linea in obtener_funcionarios_validos():
        datos = separar_funcionario(linea)

        if datos["cedula"].lower() == cedula_buscada:
            return True

    return False


def registrar_funcionario():
    print()
    print("====================================")
    print("       REGISTRAR FUNCIONARIO")
    print("====================================")
    print()
    print("Ingresá 0 para cancelar.")
    print()

    nombre = limpiar_texto(
        input("Nombre y apellido: ")
    )

    if nombre == "0":
        return

    if nombre == "":
        print()
        print("El nombre no puede quedar vacío.")
        return

    while True:
        cedula = limpiar_texto(
            input("Número de cédula: ")
        )

        if cedula == "0":
            return

        if cedula == "":
            print("La cédula no puede quedar vacía.")
            continue

        if cedula_ya_registrada(cedula):
            print()
            print(
                "Ya existe un funcionario registrado "
                "con esa cédula."
            )
            continue

        break

    fecha_ingreso = pedir_fecha(
        "Fecha de ingreso (DD-MM-AAAA): "
    )

    if fecha_ingreso is None:
        return

    unidad = elegir_opcion(
        "UNIDAD DEL FUNCIONARIO",
        UNIDADES
    )

    if unidad is None:
        return

    cargo = limpiar_texto(
        input("Cargo: ")
    )

    if cargo == "0":
        return

    if cargo == "":
        print()
        print("El cargo no puede quedar vacío.")
        return

    modalidad = elegir_opcion(
        "MODALIDAD DE PAGO",
        MODALIDADES_PAGO
    )

    if modalidad is None:
        return

    if modalidad == "Mensual":
        tipo_sueldo = elegir_opcion(
            "TIPO DE SUELDO",
            [
                "Salario mínimo",
                "Manual",
            ]
        )

        if tipo_sueldo is None:
            return

        if tipo_sueldo == "Salario mínimo":
            sueldo_base = obtener_salario_minimo()

            if sueldo_base is None:
                print()
                print(
                    "No existe un salario mínimo vigente "
                    "para la fecha actual."
                )
                return

            print()
            print(
                "Se utilizará automáticamente:",
                formatear_monto(sueldo_base),
                "Gs."
            )

        else:
            sueldo_base = pedir_monto(
                "Sueldo mensual base: "
            )

            if sueldo_base is None:
                return

    elif modalidad == "Diario":
        tipo_sueldo = "Manual"

        sueldo_base = pedir_monto(
            "Jornal diario base: "
        )

        if sueldo_base is None:
            return

    elif modalidad == "Semanal":
        tipo_sueldo = "Manual"

        sueldo_base = pedir_monto(
            "Pago semanal base: "
        )

        if sueldo_base is None:
            return

    else:
        print()
        print("Modalidad de pago inválida.")
        return

    ips = elegir_opcion(
        "¿TIENE IPS?",
        ["Sí", "No"]
    )

    if ips is None:
        return

    horario = limpiar_texto(
        input(
            "Horario laboral "
            "(ejemplo: 08:00 a 18:00): "
        )
    )

    if horario == "0":
        return

    if horario == "":
        horario = "No especificado"

    observaciones = limpiar_texto(
        input(
            "Observaciones "
            "(ENTER si no tiene): "
        )
    )

    if observaciones == "0":
        return

    if observaciones == "":
        observaciones = "Sin observaciones"

    datos = {
        "nombre": nombre,
        "cedula": cedula,
        "fecha_ingreso": fecha_ingreso,
        "unidad": unidad,
        "cargo": cargo,
        "modalidad": modalidad,
        "tipo_sueldo": tipo_sueldo,
        "sueldo_base": sueldo_base,
        "ips": ips,
        "horario": horario,
        "estado": "Activo",
        "observaciones": observaciones,
    }

    funcionarios = leer_datos(
        RUTA_FUNCIONARIOS
    )

    funcionarios.append(
        crear_linea_funcionario(datos)
    )

    guardar_datos(
        RUTA_FUNCIONARIOS,
        funcionarios
    )

    print()
    print("Funcionario registrado correctamente.")

def mostrar_funcionario(numero, linea):
    datos = separar_funcionario(linea)

    if datos is None:
        return

    print("------------------------------------")
    print(f"{numero}. {datos['nombre']}")
    print("------------------------------------")
    print("Cédula:", formatear_cedula(datos["cedula"]))
    print("Fecha de ingreso:", datos["fecha_ingreso"])
    print("Unidad:", datos["unidad"])
    print("Cargo:", datos["cargo"])
    sueldo_actual = calcular_sueldo_funcionario(
    datos
)

    print("Modalidad de pago:", datos["modalidad"])
    print("Tipo de sueldo:", datos["tipo_sueldo"])
    print(
    "Sueldo o jornal actual:",
    formatear_monto(sueldo_actual),
    "Gs."
)
    print("IPS:", datos["ips"])
    print("Horario:", datos["horario"])
    print("Estado:", datos["estado"])
    print("Observaciones:", datos["observaciones"])
    print()


def filtrar_funcionarios_por_estado(estado):
    resultado = []

    for linea in obtener_funcionarios_validos():
        datos = separar_funcionario(linea)

        if datos["estado"].lower() == estado.lower():
            resultado.append(linea)

    resultado.sort(
        key=lambda linea: (
            separar_funcionario(linea)["unidad"],
            separar_funcionario(linea)["nombre"].lower()
        )
    )

    return resultado


def ver_funcionarios_por_estado(estado):
    funcionarios = filtrar_funcionarios_por_estado(
        estado
    )

    print()
    print("====================================")
    print(f"       FUNCIONARIOS {estado.upper()}")
    print("====================================")

    if len(funcionarios) == 0:
        print()
        print(
            f"No hay funcionarios en estado "
            f"{estado.lower()}."
        )
        return

    unidad_actual = None
    numero = 1

    for linea in funcionarios:
        datos = separar_funcionario(linea)

        if datos["unidad"] != unidad_actual:
            unidad_actual = datos["unidad"]

            print()
            print("====================================")
            print("UNIDAD:", unidad_actual)
            print("====================================")
            print()

        mostrar_funcionario(numero, linea)
        numero += 1

    print(
        "Cantidad total:",
        len(funcionarios)
    )


def ver_funcionarios_activos():
    ver_funcionarios_por_estado("Activo")


def ver_funcionarios_inactivos():
    ver_funcionarios_por_estado("Inactivo")

def seleccionar_funcionario(estado, mensaje):
    funcionarios = filtrar_funcionarios_por_estado(
        estado
    )

    if len(funcionarios) == 0:
        print()
        print(
            f"No hay funcionarios en estado "
            f"{estado.lower()}."
        )
        return None, None

    print()
    print("====================================")
    print(f"       FUNCIONARIOS {estado.upper()}")
    print("====================================")
    print()

    for numero, linea in enumerate(
        funcionarios,
        start=1
    ):
        datos = separar_funcionario(linea)

        print(
            f"{numero}. {datos['nombre']} | "
            f"{datos['unidad']} | {datos['cargo']}"
        )

    print()
    print("0. Volver")
    print()

    while True:
        opcion = input(mensaje).strip()

        if opcion == "0":
            return None, None

        try:
            indice = int(opcion) - 1

            if 0 <= indice < len(funcionarios):
                linea_elegida = funcionarios[indice]
                todas_las_lineas = leer_datos(
                    RUTA_FUNCIONARIOS
                )

                indice_original = todas_las_lineas.index(
                    linea_elegida
                )

                return todas_las_lineas, indice_original

        except (ValueError, IndexError):
            pass

        print("Opción inválida.")


def pedir_texto_modificado(
    mensaje,
    valor_actual,
    permitir_vacio=False
):
    valor = limpiar_texto(
        input(
            f"{mensaje} [{valor_actual}]: "
        )
    )

    if valor == "0":
        return None

    if valor == "":
        if permitir_vacio:
            return ""
        return valor_actual

    return valor


def modificar_funcionario():
    seleccion = seleccionar_funcionario(
        "Activo",
        "Seleccione el funcionario a modificar: "
    )

    funcionarios, indice = seleccion

    if funcionarios is None:
        return

    datos = separar_funcionario(
        funcionarios[indice]
    )

    print()
    print("====================================")
    print("       MODIFICAR FUNCIONARIO")
    print("====================================")
    print()
    print("Presioná ENTER para conservar un dato.")
    print("Ingresá 0 para cancelar.")
    print()

    nombre = pedir_texto_modificado(
        "Nombre y apellido",
        datos["nombre"]
    )

    if nombre is None:
        return

    while True:
        cedula = pedir_texto_modificado(
            "Número de cédula",
            datos["cedula"]
        )

        if cedula is None:
            return

        cedula_repetida = False

        for posicion, linea in enumerate(funcionarios):
            if posicion == indice:
                continue

            otro = separar_funcionario(linea)

            if (
                otro is not None
                and otro["cedula"].lower()
                == cedula.lower()
            ):
                cedula_repetida = True
                break

        if cedula_repetida:
            print()
            print(
                "Ya existe otro funcionario con "
                "esa cédula."
            )
        else:
            break

    while True:
        fecha_ingreso = input(
            "Fecha de ingreso "
            f"[{datos['fecha_ingreso']}]: "
        ).strip()

        if fecha_ingreso == "0":
            return

        if fecha_ingreso == "":
            fecha_ingreso = datos["fecha_ingreso"]
            break

        try:
            convertir_fecha(fecha_ingreso)
            break
        except ValueError:
            print(
                "Fecha inválida. Usá el formato "
                "DD-MM-AAAA."
            )

    unidad = elegir_opcion(
        f"UNIDAD ACTUAL: {datos['unidad']}",
        UNIDADES,
        permitir_conservar=True
    )

    if unidad is None:
        return

    if unidad == "CONSERVAR":
        unidad = datos["unidad"]

    cargo = pedir_texto_modificado(
        "Cargo",
        datos["cargo"]
    )

    if cargo is None:
        return

    modalidad = elegir_opcion(
    (
        "MODALIDAD ACTUAL: "
        f"{datos['modalidad']}"
    ),
    MODALIDADES_PAGO,
    permitir_conservar=True
)

    if modalidad is None:
        return

    if modalidad == "CONSERVAR":
        modalidad = datos["modalidad"]

    if modalidad == "Mensual":
        tipo_sueldo = elegir_opcion(
        (
            "TIPO DE SUELDO ACTUAL: "
            f"{datos['tipo_sueldo']}"
        ),
        [
            "Salario mínimo",
            "Manual",
        ],
        permitir_conservar=True
    )

    if tipo_sueldo is None:
        return

    if tipo_sueldo == "CONSERVAR":
        tipo_sueldo = datos["tipo_sueldo"]

    if tipo_sueldo == "Salario mínimo":
        sueldo_base = obtener_salario_minimo()

        if sueldo_base is None:
            print()
            print(
                "No existe un salario mínimo vigente "
                "para la fecha actual."
            )
            return

        print()
        print(
            "Se utilizará automáticamente:",
            formatear_monto(sueldo_base),
            "Gs."
        )

    else:
        print()
        print(
            "Sueldo mensual actual:",
            formatear_monto(datos["sueldo_base"]),
            "Gs."
        )

        sueldo_base = pedir_monto(
            "Nuevo sueldo (ENTER para conservar): ",
            permitir_vacio=True
        )

        if sueldo_base is None:
            return

        if sueldo_base == "":
            sueldo_base = datos["sueldo_base"]

        elif modalidad == "Diario":
            tipo_sueldo = "Manual"

    print()
    print(
        "Jornal actual:",
        formatear_monto(datos["sueldo_base"]),
        "Gs."
    )

    sueldo_base = pedir_monto(
        "Nuevo jornal (ENTER para conservar): ",
        permitir_vacio=True
    )

    if sueldo_base is None:
        return

    if sueldo_base == "":
        sueldo_base = datos["sueldo_base"]

    else:
        tipo_sueldo = "Manual"

    print()
    print(
        "Pago semanal actual:",
        formatear_monto(datos["sueldo_base"]),
        "Gs."
    )

    sueldo_base = pedir_monto(
        "Nuevo pago semanal "
        "(ENTER para conservar): ",
        permitir_vacio=True
    )

    if sueldo_base is None:
        return

    if sueldo_base == "":
        sueldo_base = datos["sueldo_base"]

    ips = elegir_opcion(
        f"IPS ACTUAL: {datos['ips']}",
        ["Sí", "No"],
        permitir_conservar=True
    )

    if ips is None:
        return

    if ips == "CONSERVAR":
        ips = datos["ips"]

    horario = pedir_texto_modificado(
        "Horario laboral",
        datos["horario"]
    )

    if horario is None:
        return

    observaciones = pedir_texto_modificado(
        "Observaciones",
        datos["observaciones"]
    )

    if observaciones is None:
        return

    datos_modificados = {
        "nombre": nombre,
        "cedula": cedula,
        "fecha_ingreso": fecha_ingreso,
        "unidad": unidad,
        "cargo": cargo,
        "modalidad": modalidad,
        "tipo_sueldo": tipo_sueldo,
        "sueldo_base": sueldo_base,
        "ips": ips,
        "horario": horario,
        "estado": datos["estado"],
        "observaciones": observaciones,
    }

    print()
    confirmacion = input(
        "¿Guardar los cambios? (S/N): "
    ).strip().lower()

    if confirmacion != "s":
        print()
        print("Modificación cancelada.")
        return

    funcionarios[indice] = crear_linea_funcionario(
        datos_modificados
    )

    guardar_datos(
        RUTA_FUNCIONARIOS,
        funcionarios
    )

    print()
    print("Funcionario modificado correctamente.")


def desactivar_funcionario():
    seleccion = seleccionar_funcionario(
        "Activo",
        "Seleccione el funcionario a desactivar: "
    )

    funcionarios, indice = seleccion

    if funcionarios is None:
        return

    datos = separar_funcionario(
        funcionarios[indice]
    )

    print()
    print("Funcionario:", datos["nombre"])
    print("Unidad:", datos["unidad"])
    print("Cargo:", datos["cargo"])
    print()
    print(
        "El funcionario conservará todo su historial."
    )

    confirmacion = input(
        "¿Confirmar desactivación? (S/N): "
    ).strip().lower()

    if confirmacion != "s":
        print()
        print("Desactivación cancelada.")
        return

    datos["estado"] = "Inactivo"

    funcionarios[indice] = crear_linea_funcionario(
        datos
    )

    guardar_datos(
        RUTA_FUNCIONARIOS,
        funcionarios
    )

    print()
    print("Funcionario desactivado correctamente.")


def reactivar_funcionario():
    seleccion = seleccionar_funcionario(
        "Inactivo",
        "Seleccione el funcionario a reactivar: "
    )

    funcionarios, indice = seleccion

    if funcionarios is None:
        return

    datos = separar_funcionario(
        funcionarios[indice]
    )

    print()
    print("Funcionario:", datos["nombre"])
    print("Unidad:", datos["unidad"])
    print()

    confirmacion = input(
        "¿Confirmar reactivación? (S/N): "
    ).strip().lower()

    if confirmacion != "s":
        print()
        print("Reactivación cancelada.")
        return

    datos["estado"] = "Activo"

    funcionarios[indice] = crear_linea_funcionario(
        datos
    )

    guardar_datos(
        RUTA_FUNCIONARIOS,
        funcionarios
    )

    print()
    print("Funcionario reactivado correctamente.")

def menu_gestion_funcionarios():
    while True:
        print()
        print("====================================")
        print("     GESTIÓN DE FUNCIONARIOS")
        print("====================================")
        print()
        print("1. Registrar funcionario")
        print("2. Ver funcionarios activos")
        print("3. Modificar funcionario")
        print("4. Desactivar funcionario")
        print("5. Ver funcionarios inactivos")
        print("6. Reactivar funcionario")
        print("7. Novedades del funcionario")
        print("0. Volver")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            registrar_funcionario()

        elif opcion == "2":
            ver_funcionarios_activos()

        elif opcion == "3":
            modificar_funcionario()

        elif opcion == "4":
            desactivar_funcionario()

        elif opcion == "5":
            ver_funcionarios_inactivos()

        elif opcion == "6":
            reactivar_funcionario()

        elif opcion == "7":
            from Novedades import menu_novedades
            menu_novedades()

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")


def menu_sueldos_liquidaciones():
    while True:
        print()
        print("====================================")
        print("      SUELDOS Y LIQUIDACIONES")
        print("====================================")
        print()
        print("1. Liquidaciones")
        print("2. Configuración del salario mínimo")
        print("0. Volver")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            from Liquidaciones import menu_liquidaciones
            menu_liquidaciones()

        elif opcion == "2":
            menu_salario_minimo()

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")


def menu_funcionarios():
    while True:
        print()
        print("====================================")
        print("        RECURSOS HUMANOS")
        print("====================================")
        print()
        print("1. Gestión de funcionarios")
        print("2. Sueldos y liquidaciones")
        print("0. Volver al menú principal")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            menu_gestion_funcionarios()

        elif opcion == "2":
            menu_sueldos_liquidaciones()

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")