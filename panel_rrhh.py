"""Adaptador embebible de Recursos Humanos."""

from interfaz_rrhh import VentanaRecursosHumanos


def crear_panel_rrhh(
    master,
    pestana="Gestión de funcionarios",
):
    panel = VentanaRecursosHumanos(
        master,
        pestana,
    )
    return panel