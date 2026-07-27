from Movimientos import menu_movimientos
from Funcionarios import menu_funcionarios
from Socios import menu_socios
import ideas
import proyectos


def menu_gestion_empresarial():
    while True:
        print()
        print("====================================")
        print("      BC GESTIÓN EMPRESARIAL")
        print("====================================")
        print()
        print("1. Movimientos")
        print("2. Recursos Humanos")
        print("3. Socios")
        print("0. Volver al menú principal")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            menu_movimientos()

        elif opcion == "2":
            menu_funcionarios()

        elif opcion == "3":
            menu_socios()

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")


def menu_aprendizaje():
    while True:
        print()
        print("====================================")
        print("        ÁREA DE APRENDIZAJE")
        print("====================================")
        print()
        print("1. Ideas")
        print("2. Proyectos de práctica")
        print("0. Volver al menú principal")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            ideas.menu()

        elif opcion == "2":
            proyectos.menu()

        elif opcion == "0":
            break

        else:
            print()
            print("Opción inválida.")


def menu_principal(nombre):
    while True:
        print()
        print("====================================")
        print("             PROYECTO X")
        print("====================================")
        print()
        print("1. BC Gestión Empresarial")
        print("2. Área de aprendizaje")
        print("0. Salir")
        print()

        opcion = input(
            "Seleccione una opción: "
        ).strip()

        if opcion == "1":
            menu_gestion_empresarial()

        elif opcion == "2":
            menu_aprendizaje()

        elif opcion == "0":
            print()
            print("Hasta luego,", nombre)
            break

        else:
            print()
            print("Opción inválida.")


print("====================================")
print("             PROYECTO X")
print("====================================")
print()

nombre = input("¿Cómo te llamás? ").strip()

if nombre == "":
    nombre = "Usuario"

print()
print("Bienvenido,", nombre)

menu_principal(nombre)