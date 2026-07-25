def menu():

    while True:
        print()
        print("==============================")
        print("       MÓDULO DE PROYECTOS")
        print("==============================")
        print()
        print("1 - Ver proyectos")
        print("2 - Agregar proyecto")
        print("3 - Modificar proyecto")
        print("4 - Eliminar proyecto")
        print("5 - Volver al menú principal")

        opcion = input("Elegí una opción: ")

        print()

        if opcion == "1":
            ver_proyectos()

        elif opcion == "2":
            agregar_proyecto()

        elif opcion == "3":
            modificar_proyecto()

        elif opcion == "4":
            eliminar_proyecto()

        elif opcion == "5":
            break

            lista_proyectos = contenido.split("\n")



        elif opcion == "4":
            eliminar_proyecto()

        elif opcion == "5":
            break

        else:
            print("Opción no válida.")


def ver_proyectos():
    archivo = open("proyectos.txt", "r")
    contenido = archivo.read()
    archivo.close()

    lista_proyectos = contenido.split("\n")

    print()
    print("PROYECTOS REGISTRADOS")
    print()

    contador = 1

    for proyecto in lista_proyectos:
        if proyecto != "":
            print(contador, "-", proyecto)
            contador = contador + 1

    total_proyectos = contador - 1

    print()
    print("Cantidad total de proyectos:", total_proyectos)



def agregar_proyecto():
    nuevo_proyecto = input("Escribí un proyecto: ")
    nueva_descripcion = input("Escribí una descripción: ")
    nuevo_estado = input("Escribí el estado del proyecto: ")

    archivo = open("proyectos.txt", "a")
    archivo.write(nuevo_proyecto + "|" + nueva_descripcion + "|" + nuevo_estado + "\n")
    archivo.close()

    print()
    print("Proyecto agregado correctamente.")


def eliminar_proyecto():
    archivo = open("proyectos.txt", "r")
    contenido = archivo.read()
    archivo.close()

    lista_proyectos = contenido.split("\n")

    print()
    print("PROYECTOS REGISTRADOS")
    print()

    contador = 1

    for proyecto in lista_proyectos:
        if proyecto != "":
            print(contador, "-", proyecto)
            contador = contador + 1

    total_proyectos = contador - 1

    print()
    print("Cantidad total de proyectos:", total_proyectos)

    if total_proyectos > 0:
        opcion = input("Elegí un proyecto para eliminar: ")
        try:
            indice = int(opcion) - 1
            if 0 <= indice < len(lista_proyectos):
                proyecto_eliminado = lista_proyectos[indice]
                lista_proyectos.pop(indice)
                archivo = open("proyectos.txt", "w")
                archivo.write("\n".join(lista_proyectos))
                archivo.close()
                print()
                print("Proyecto eliminado:", proyecto_eliminado)
            else:
                print("Opción no válida.")
        except ValueError:
            print("Opción no válida.")
    else:
        print("No hay proyectos para eliminar.")

def modificar_proyecto():
    archivo = open("proyectos.txt", "r")
    contenido = archivo.read()
    archivo.close()

    lista_proyectos = contenido.split("\n")

    print()
    print("ELEGIR PROYECTO PARA MODIFICAR")
    print()

    contador = 1

    for proyecto in lista_proyectos:
        if proyecto != "":
            print(contador, "-", proyecto)
            contador = contador + 1

    total_proyectos = contador - 1

    print()
    print("Cantidad total de proyectos:", total_proyectos)

    opcion_proyecto = input("Elegí el número del proyecto a modificar: ")
    try:
        indice = int(opcion_proyecto) - 1
        if 0 <= indice < len(lista_proyectos):
            proyecto_seleccionado = lista_proyectos[indice]
            print()
            print("Proyecto seleccionado:", proyecto_seleccionado)
            print()

            nuevo_nombre = input("Escribí el nuevo nombre del proyecto (dejar en blanco para no modificar): ")
            nueva_descripcion = input("Escribí la nueva descripción del proyecto (dejar en blanco para no modificar): ")
            nuevo_estado = input("Escribí el nuevo estado del proyecto (dejar en blanco para no modificar): ")

            partes_proyecto = proyecto_seleccionado.split("|")
            nombre_actual = partes_proyecto[0] if len(partes_proyecto) > 0 else ""
            descripcion_actual = partes_proyecto[1] if len(partes_proyecto) > 1 else ""
            estado_actual = partes_proyecto[2] if len(partes_proyecto) > 2 else ""

            nombre_modificado = nuevo_nombre if nuevo_nombre != "" else nombre_actual
            descripcion_modificada = nueva_descripcion if nueva_descripcion != "" else descripcion_actual
            estado_modificado = nuevo_estado if nuevo_estado != "" else estado_actual

            proyecto_modificado = nombre_modificado + "|" + descripcion_modificada + "|" + estado_modificado
            lista_proyectos[indice] = proyecto_modificado

            archivo = open("proyectos.txt", "w")
            archivo.write("\n".join(lista_proyectos))
            archivo.close()

            print()
            print("Proyecto modificado correctamente.")
        else:
            print("Opción no válida.")
    except ValueError:
        print("Opción no válida.")
        return