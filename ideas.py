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


def ver_ideas():
    archivo = open("ideas.txt", "r")
    contenido = archivo.read()
    archivo.close()

    lista_ideas = contenido.split("\n")

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

    archivo = open("ideas.txt", "a")
    archivo.write(nueva_idea + "\n")
    archivo.close()

    print("Idea registrada:", nueva_idea)

def eliminar_idea():
    archivo = open("ideas.txt", "r")
    contenido = archivo.read()
    archivo.close()

    lista_ideas = contenido.split("\n")

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
                archivo = open("ideas.txt", "w")
                archivo.write("\n".join(lista_ideas))
                archivo.close()
                print("Idea eliminada:", idea_eliminada)
            else:
                print("Opción no válida.")
        except ValueError:
            print("Opción no válida.")
    else:
        print("No hay ideas para eliminar.")