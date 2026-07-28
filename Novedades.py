from datetime import datetime

from datos import leer_datos, guardar_datos
from Movimientos import formatear_monto

from Funcionarios import (
    RUTA_FUNCIONARIOS,
    separar_funcionario,
)


RUTA_NOVEDADES = (
    RUTA_FUNCIONARIOS.parent
    / "novedades_funcionarios.txt"
)

TIPOS_NOVEDAD = [
    "Reposo",
    "Ausencia",
    "Comisión",
    "Adelanto",
    "Otro descuento",
]


def obtener_funcionarios_activos():
    lineas = leer_datos(
        RUTA_FUNCIONARIOS
    )

    funcionarios = []

    for linea in lineas:
        funcionario = separar_funcionario(linea)

        if (
            funcionario is not None
            and funcionario["estado"] == "Activo"
        ):
            funcionarios.append(funcionario)

    return funcionarios


def seleccionar_funcionario_activo():
    funcionarios = obtener_funcionarios_activos()

    if len(funcionarios) == 0:
        print()
        print("No hay funcionarios activos registrados.")
        return None

    print()
    print("====================================")
    print("       FUNCIONARIOS ACTIVOS")
    print("====================================")
    print()

    for numero, funcionario in enumerate(
        funcionarios,
        start=1
    ):
        print(
            f"{numero}. "
            f"{funcionario['nombre']} | "
            f"{funcionario['cargo']}"
        )

    print("0. Cancelar")
    print()

    while True:
        opcion = input(
            "Seleccione un funcionario: "
        ).strip()

        if opcion == "0":
            return None

        if not opcion.isdigit():
            print("Ingresá un número válido.")
            continue

        indice = int(opcion) - 1

        if indice < 0 or indice >= len(funcionarios):
            print("La opción seleccionada no existe.")
            continue

        return funcionarios[indice]


def pedir_fecha(mensaje):
    while True:
        fecha = input(mensaje).strip()

        if fecha == "0":
            return None

        try:
            datetime.strptime(
                fecha,
                "%d-%m-%Y"
            )
            return fecha

        except ValueError:
            print()
            print(
                "Fecha inválida. "
                "Ejemplo correcto: 19-07-2026"
            )


def pedir_monto(mensaje):
    while True:
        monto = input(mensaje).strip()

        if monto == "0":
            return None

        monto = (
            monto
            .replace(".", "")
            .replace(",", "")
        )

        if not monto.isdigit():
            print("Ingresá un monto válido.")
            continue

        monto = int(monto)

        if monto <= 0:
            print("El monto debe ser mayor que cero.")
            continue

        return monto


def seleccionar_tipo_novedad():
    print()
    print("Tipo de novedad:")
    print()

    for numero, tipo in enumerate(
        TIPOS_NOVEDAD,
        start=1
    ):
        print(f"{numero}. {tipo}")

    print("0. Cancelar")
    print()

    while True:
        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "0":
            return None

        if not opcion.isdigit():
            print("Ingresá un número válido.")
            continue

        indice = int(opcion) - 1

        if indice < 0 or indice >= len(TIPOS_NOVEDAD):
            print("La opción seleccionada no existe.")
            continue

        return TIPOS_NOVEDAD[indice]


def crear_linea_novedad(datos):
    campos = [
        datos["cedula"],
        datos["nombre"],
        datos["tipo"],
        datos["fecha_inicio"],
        datos["fecha_fin"],
        str(datos["monto"]),
        datos["cubierto_ips"],
        datos["motivo"],
    ]

    return " | ".join(campos)


def separar_novedad(linea):
    partes = [
        parte.strip()
        for parte in linea.split("|")
    ]

    if len(partes) != 8:
        return None

    try:
        return {
            "cedula": partes[0],
            "nombre": partes[1],
            "tipo": partes[2],
            "fecha_inicio": partes[3],
            "fecha_fin": partes[4],
            "monto": int(partes[5]),
            "cubierto_ips": partes[6],
            "motivo": partes[7],
        }

    except ValueError:
        return None


def registrar_novedad():
    print()
    print("====================================")
    print("       REGISTRAR NOVEDAD")
    print("====================================")
    print()

    funcionario = seleccionar_funcionario_activo()

    if funcionario is None:
        return

    tipo = seleccionar_tipo_novedad()

    if tipo is None:
        return

    fecha_inicio = pedir_fecha(
        "Fecha de inicio (DD-MM-AAAA) "
        "o 0 para cancelar: "
    )

    if fecha_inicio is None:
        return

    fecha_fin = fecha_inicio
    monto = 0
    cubierto_ips = "No"

    if tipo == "Reposo":
        fecha_fin = pedir_fecha(
            "Fecha de finalización (DD-MM-AAAA) "
            "o 0 para cancelar: "
        )

        if fecha_fin is None:
            return

        inicio = datetime.strptime(
            fecha_inicio,
            "%d-%m-%Y"
        )
        fin = datetime.strptime(
            fecha_fin,
            "%d-%m-%Y"
        )

        if fin < inicio:
            print()
            print(
                "La fecha de finalización no puede "
                "ser anterior a la fecha de inicio."
            )
            return

        while True:
            print()
            print("¿El reposo está cubierto por IPS?")
            print("1. Sí")
            print("2. No")

            opcion_ips = input(
                "Seleccione una opción: "
            ).strip()

            if opcion_ips == "1":
                cubierto_ips = "Sí"
                break

            if opcion_ips == "2":
                cubierto_ips = "No"
                break

            print("Opción inválida.")

    elif tipo == "Ausencia":
        fecha_fin = fecha_inicio

    elif tipo in ["Comisión", "Adelanto", "Otro descuento"]:
        monto = pedir_monto(
            "Monto en guaraníes o 0 para cancelar: "
        )

        if monto is None:
            return

    etiqueta_detalle = (
        "Concepto de la comisión"
        if tipo == "Comisión"
        else "Motivo u observación"
    )
    motivo = input(f"{etiqueta_detalle}: ").strip()

    if motivo == "":
        if tipo == "Comisión":
            print(
                "El concepto es obligatorio para registrar "
                "una comisión."
            )
            return
        motivo = "Sin observación"

    datos_novedad = {
        "cedula": funcionario["cedula"],
        "nombre": funcionario["nombre"],
        "tipo": tipo,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "monto": monto,
        "cubierto_ips": cubierto_ips,
        "motivo": motivo,
    }

    print()
    print("====================================")
    print("       RESUMEN DE NOVEDAD")
    print("====================================")
    print()
    print("Funcionario:", datos_novedad["nombre"])
    print("Tipo:", datos_novedad["tipo"])
    print("Fecha de inicio:", datos_novedad["fecha_inicio"])
    print("Fecha de finalización:", datos_novedad["fecha_fin"])

    if tipo in ["Comisión", "Adelanto", "Otro descuento"]:
        print(
            "Monto:",
            formatear_monto(datos_novedad["monto"]),
            "Gs."
        )

    if tipo == "Reposo":
        print(
            "Cubierto por IPS:",
            datos_novedad["cubierto_ips"]
        )

    print("Motivo:", datos_novedad["motivo"])
    print()
    print("¿Guardar esta novedad?")
    print("1. Sí")
    print("2. No")

    while True:
        confirmacion = input(
            "Seleccione una opción: "
        ).strip()

        if confirmacion == "2":
            print()
            print("La novedad no fue guardada.")
            return

        if confirmacion != "1":
            print("Opción inválida.")
            continue

        break

    lineas = leer_datos(
        RUTA_NOVEDADES
    )

    lineas.append(
        crear_linea_novedad(
            datos_novedad
        )
    )

    guardar_datos(
        RUTA_NOVEDADES,
        lineas
    )

    print()
    print("Novedad guardada correctamente.")


def ver_novedades():
    lineas = leer_datos(
        RUTA_NOVEDADES
    )

    novedades = []

    for linea in lineas:
        novedad = separar_novedad(linea)

        if novedad is not None:
            novedades.append(novedad)

    if len(novedades) == 0:
        print()
        print("No hay novedades registradas.")
        return

    print()
    print("====================================")
    print("      NOVEDADES REGISTRADAS")
    print("====================================")

    for numero, novedad in enumerate(
        novedades,
        start=1
    ):
        print()
        print("------------------------------------")
        print(f"{numero}. {novedad['nombre']}")
        print("Tipo:", novedad["tipo"])
        print("Desde:", novedad["fecha_inicio"])
        print("Hasta:", novedad["fecha_fin"])

        if novedad["monto"] > 0:
            print(
                "Monto:",
                formatear_monto(
                    novedad["monto"]
                ),
                "Gs."
            )

        if novedad["tipo"] == "Reposo":
            print(
                "Cubierto por IPS:",
                novedad["cubierto_ips"]
            )

        print("Motivo:", novedad["motivo"])

    print()
    input("Presione ENTER para volver...")

def pedir_fecha_edicion(mensaje, fecha_actual):
    while True:
        fecha = input(
            f"{mensaje} [{fecha_actual}]: "
        ).strip()

        if fecha == "":
            return fecha_actual

        try:
            datetime.strptime(
                fecha,
                "%d-%m-%Y"
            )
            return fecha

        except ValueError:
            print(
                "Fecha inválida. "
                "Ejemplo correcto: 19-07-2026"
            )


def pedir_monto_edicion(mensaje, monto_actual):
    while True:
        monto = input(
            f"{mensaje} [{monto_actual}]: "
        ).strip()

        if monto == "":
            return monto_actual

        monto = (
            monto
            .replace(".", "")
            .replace(",", "")
        )

        if not monto.isdigit():
            print("Ingresá un monto válido.")
            continue

        monto = int(monto)

        if monto <= 0:
            print("El monto debe ser mayor que cero.")
            continue

        return monto


def obtener_novedades_validas():
    lineas = leer_datos(
        RUTA_NOVEDADES
    )

    novedades_validas = []

    for indice_linea, linea in enumerate(lineas):
        novedad = separar_novedad(linea)

        if novedad is not None:
            novedades_validas.append(
                {
                    "indice_linea": indice_linea,
                    "datos": novedad,
                }
            )

    return lineas, novedades_validas


def seleccionar_novedad(
    novedades_validas,
    titulo
):
    print()
    print("====================================")
    print(titulo)
    print("====================================")
    print()

    for numero, registro in enumerate(
        novedades_validas,
        start=1
    ):
        novedad = registro["datos"]

        descripcion = (
            f"{numero}. "
            f"{novedad['nombre']} | "
            f"{novedad['tipo']} | "
            f"{novedad['fecha_inicio']}"
        )

        if novedad["monto"] > 0:
            descripcion += (
                f" | "
                f"{formatear_monto(novedad['monto'])} Gs."
            )

        print(descripcion)

    print("0. Cancelar")
    print()

    while True:
        opcion = input(
            "Seleccione una novedad: "
        ).strip()

        if opcion == "0":
            return None

        if not opcion.isdigit():
            print("Ingresá un número válido.")
            continue

        indice = int(opcion) - 1

        if (
            indice < 0
            or indice >= len(novedades_validas)
        ):
            print("La opción seleccionada no existe.")
            continue

        return novedades_validas[indice]


def modificar_novedad():
    lineas, novedades_validas = (
        obtener_novedades_validas()
    )

    if len(novedades_validas) == 0:
        print()
        print("No hay novedades para modificar.")
        return

    registro = seleccionar_novedad(
        novedades_validas,
        "       MODIFICAR NOVEDAD"
    )

    if registro is None:
        return

    indice_linea = registro["indice_linea"]
    novedad = registro["datos"]

    print()
    print(
        "Dejá el campo vacío y presioná ENTER "
        "para conservar el valor actual."
    )
    print()

    nueva_fecha_inicio = pedir_fecha_edicion(
        "Fecha de inicio",
        novedad["fecha_inicio"]
    )

    nueva_fecha_fin = nueva_fecha_inicio
    nuevo_monto = novedad["monto"]
    nuevo_cubierto_ips = novedad["cubierto_ips"]

    if novedad["tipo"] == "Reposo":
        nueva_fecha_fin = pedir_fecha_edicion(
            "Fecha de finalización",
            novedad["fecha_fin"]
        )

        inicio = datetime.strptime(
            nueva_fecha_inicio,
            "%d-%m-%Y"
        )

        fin = datetime.strptime(
            nueva_fecha_fin,
            "%d-%m-%Y"
        )

        if fin < inicio:
            print()
            print(
                "La fecha de finalización no puede "
                "ser anterior a la fecha de inicio."
            )
            return

        while True:
            print()
            print(
                "Cobertura IPS actual:",
                novedad["cubierto_ips"]
            )
            print("1. Sí")
            print("2. No")
            print("ENTER. Conservar")

            opcion_ips = input(
                "Seleccione una opción: "
            ).strip()

            if opcion_ips == "":
                break

            if opcion_ips == "1":
                nuevo_cubierto_ips = "Sí"
                break

            if opcion_ips == "2":
                nuevo_cubierto_ips = "No"
                break

            print("Opción inválida.")

    elif novedad["tipo"] in [
        "Comisión",
        "Adelanto",
        "Otro descuento"
    ]:
        nuevo_monto = pedir_monto_edicion(
            "Monto",
            novedad["monto"]
        )

    nuevo_motivo = input(
        f"Motivo [{novedad['motivo']}]: "
    ).strip()

    if nuevo_motivo == "":
        nuevo_motivo = novedad["motivo"]

    if (
        novedad["tipo"] == "Comisión"
        and nuevo_motivo in ["", "Sin observación"]
    ):
        print(
            "El concepto es obligatorio para registrar "
            "una comisión."
        )
        return

    nuevos_datos = {
        "cedula": novedad["cedula"],
        "nombre": novedad["nombre"],
        "tipo": novedad["tipo"],
        "fecha_inicio": nueva_fecha_inicio,
        "fecha_fin": nueva_fecha_fin,
        "monto": nuevo_monto,
        "cubierto_ips": nuevo_cubierto_ips,
        "motivo": nuevo_motivo,
    }

    print()
    print("====================================")
    print("         NUEVA NOVEDAD")
    print("====================================")
    print()
    print("Funcionario:", nuevos_datos["nombre"])
    print("Tipo:", nuevos_datos["tipo"])
    print("Desde:", nuevos_datos["fecha_inicio"])
    print("Hasta:", nuevos_datos["fecha_fin"])

    if nuevos_datos["monto"] > 0:
        print(
            "Monto:",
            formatear_monto(
                nuevos_datos["monto"]
            ),
            "Gs."
        )

    if nuevos_datos["tipo"] == "Reposo":
        print(
            "Cubierto por IPS:",
            nuevos_datos["cubierto_ips"]
        )

    print("Motivo:", nuevos_datos["motivo"])
    print()
    print("¿Guardar estos cambios?")
    print("1. Sí")
    print("2. No")

    while True:
        confirmacion = input(
            "Seleccione una opción: "
        ).strip()

        if confirmacion == "2":
            print()
            print("No se realizaron cambios.")
            return

        if confirmacion != "1":
            print("Opción inválida.")
            continue

        break

    lineas[indice_linea] = crear_linea_novedad(
        nuevos_datos
    )

    guardar_datos(
        RUTA_NOVEDADES,
        lineas
    )

    print()
    print("Novedad modificada correctamente.")


def eliminar_novedad():
    lineas, novedades_validas = (
        obtener_novedades_validas()
    )

    if len(novedades_validas) == 0:
        print()
        print("No hay novedades para eliminar.")
        return

    registro = seleccionar_novedad(
        novedades_validas,
        "        ELIMINAR NOVEDAD"
    )

    if registro is None:
        return

    indice_linea = registro["indice_linea"]
    novedad = registro["datos"]

    print()
    print("Novedad seleccionada:")
    print("Funcionario:", novedad["nombre"])
    print("Tipo:", novedad["tipo"])
    print("Desde:", novedad["fecha_inicio"])
    print("Hasta:", novedad["fecha_fin"])

    if novedad["monto"] > 0:
        print(
            "Monto:",
            formatear_monto(
                novedad["monto"]
            ),
            "Gs."
        )

    print("Motivo:", novedad["motivo"])
    print()
    print(
        "¿Está seguro de eliminar esta novedad?"
    )
    print("1. Sí, eliminar")
    print("2. No, cancelar")

    while True:
        confirmacion = input(
            "Seleccione una opción: "
        ).strip()

        if confirmacion == "2":
            print()
            print("La novedad no fue eliminada.")
            return

        if confirmacion != "1":
            print("Opción inválida.")
            continue

        break

    lineas.pop(indice_linea)

    guardar_datos(
        RUTA_NOVEDADES,
        lineas
    )

    print()
    print("Novedad eliminada correctamente.")

def menu_novedades():
    while True:
        print()
        print("====================================")
        print("   NOVEDADES DEL FUNCIONARIO")
        print("====================================")
        print()
        print("1. Registrar novedad")
        print("2. Ver novedades registradas")
        print("3. Modificar novedad")
        print("4. Eliminar novedad")
        print("0. Volver")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            registrar_novedad()

        elif opcion == "2":
            ver_novedades()

        elif opcion == "3":
            modificar_novedad()

        elif opcion == "4":
            eliminar_novedad()

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")
