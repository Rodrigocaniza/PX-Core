from datos import leer_datos, guardar_datos
def menu():
    
    while True:
        print()
        print("==============================")
        print("       MÓDULO DE IDEAS")
        print("==============================")
        print()
        print("1 - Ver ideas")
        print("2 - Agregar idea")
        print("3 - Eliminar idea")
        print("4 - Volver al menú principal")

        opcion = input("Elegí una opción: ")

        print()

        if opcion == "1":
            ver_ideas()

        elif opcion == "2":
            agregar_idea()

        elif opcion == "3":
            eliminar_idea()

        elif opcion == "4":
            break

        else:
            print("Opción no válida.")

def leer_ideas():
    return leer_datos("Datos/ideas.txt")

def guardar_ideas(lista_ideas):
    guardar_datos("Datos/ideas.txt", lista_ideas)

def ver_ideas():
    lista_ideas = leer_ideas()

    print()
    print("IDEAS REGISTRADAS")
    print()

    contador = 1

    for idea in lista_ideas:
        if idea != "":
            print(contador, "-", idea)
            contador = contador + 1

    total_ideas = contador - 1

    print()
    print("Cantidad total de ideas:", total_ideas)

def agregar_idea():
    nueva_idea = input("Escribí una idea: ")

    lista_ideas = leer_ideas()
    lista_ideas.append(nueva_idea)
    guardar_ideas(lista_ideas)

    print("Idea registrada:", nueva_idea)

def eliminar_idea():
    lista_ideas = leer_ideas()

    print()
    print("IDEAS REGISTRADAS")
    print()

    contador = 1

    for idea in lista_ideas:
        if idea != "":
            print(contador, "-", idea)
            contador = contador + 1

    total_ideas = contador - 1

    print()
    print("Cantidad total de ideas:", total_ideas)

    if total_ideas > 0:
        opcion = input("Elegí una idea para eliminar: ")
        try:
            indice = int(opcion) - 1
            if 0 <= indice < len(lista_ideas):
                idea_eliminada = lista_ideas[indice]
                lista_ideas.pop(indice)
                guardar_ideas(lista_ideas)
                print("Idea eliminada:", idea_eliminada)
            else:
                print("Opción no válida.")
        except ValueError:
            print("Opción no válida.")
    else:
        print("No hay ideas para eliminar.")