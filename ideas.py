def mostrar():
    print()
    print("===================================")
    print("         MÓDULO DE IDEAS")
    print("===================================")
    print()

    nueva_idea = input("Escribí una idea: ")

    archivo = open("ideas.txt", "a")
    archivo.write(nueva_idea + "\n")
    archivo.close()

    print("Idea registrada:", nueva_idea)


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