import ideas
print("===================================")
print("        PROYECTO X - PX CORE")
print("===================================")
print()

nombre = input("¿Cómo te llamás? ")

print()
print("Bienvenido", nombre)
print()

while True:
    print()
    print("Menú")
    print("1 - Ver ideas")
    print("2 - Agregar idea")
    print("3 - Registrar horas")
    print("4 - Salir")

    opcion = input("Elegí una opción: ")

    print()

    if opcion == "1":
        ideas.ver_ideas()

    elif opcion == "2":
        ideas.mostrar()

    elif opcion == "3":
        print("Aquí registrarás las horas.")

    elif opcion == "4":
        print("Hasta luego", nombre)
        break

    else:
        print("Opción no válida.")