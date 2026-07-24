import ideas
import proyectos
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
    print("1 - Ideas")
    print("2 - Proyectos")
    print("3 - Registrar horas")
    print("4 - Salir")

    opcion = input("Elegí una opción: ")

    print()

    if opcion == "1":
        ideas.menu()

    elif opcion == "2":
        proyectos.menu()

    elif opcion == "3":
        registrar_horas.menu()

    elif opcion == "4":
        print("Hasta luego", nombre)
        break

    else:
        print("Opción no válida.")