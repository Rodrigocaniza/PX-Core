def menu_movimientos():
    while True:
        print()
        print("====================================")
        print("          PX FINANZAS")
        print("        MENÚ MOVIMIENTOS")
        print("====================================")
        print()
        print("1. Registrar ingreso")
        print("2. Registrar egreso")
        print("3. Registrar transferencia interna")
        print("4. Registrar depósito bancario")
        print("5. Ver movimientos")
        print("6. Modificar movimiento")
        print("7. Eliminar movimiento")
        print("8. Volver")
        print()

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            registrar_ingreso()

        elif opcion == "2":
            print()
            print("REGISTRAR EGRESO")
            print("Función próximamente")

        elif opcion == "3":
            print()
            print("REGISTRAR TRANSFERENCIA INTERNA")
            print("Función próximamente")

        elif opcion == "4":
            menu_depositos()

        elif opcion == "5":
            print()
            print("VER MOVIMIENTOS")
            print("Función próximamente")

        elif opcion == "6":
            print()
            print("MODIFICAR MOVIMIENTO")
            print("Función próximamente")

        elif opcion == "7":
            print()
            print("ELIMINAR MOVIMIENTO")
            print("Función próximamente")

        elif opcion == "8":
            break

        else:
            print()
            print("Opción no válida")

def registrar_ingreso():
    lista_movimientos = leer_datos("Datos/movimientos.txt")

    fecha = input("Fecha: ")
    unidad = input("Unidad: ")
    categoria = input("Categoría: ")
    descripcion = input("Descripción: ")
    monto = input("Monto: ")

    movimiento = fecha + "|" + unidad + "|" + categoria + "|" + descripcion + "|" + monto

    lista_movimientos.append(movimiento)

    guardar_datos("Datos/movimientos.txt", lista_movimientos)

    print()
    print("Ingreso registrado correctamente.")

def menu_depositos():
    while True:
        print()
        print("====================================")
        print("        DEPÓSITO BANCARIO")
        print("====================================")
        print()
        print("1. Depósito interno")
        print("2. Cobro externo")
        print("3. Volver")
        print()

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            print()
            print("DEPÓSITO INTERNO")
            print("Este movimiento no suma a los ingresos.")
            print("Función próximamente")

        elif opcion == "2":
            print()
            print("COBRO EXTERNO")
            print("Este movimiento sí suma a los ingresos.")
            print("Función próximamente")

        elif opcion == "3":
            break

        else:
            print()
            print("Opción no válida")