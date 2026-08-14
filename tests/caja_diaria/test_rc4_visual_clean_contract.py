from pathlib import Path

import CajaDiaria


SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def test_rc4_exact_field_orders_and_read_only_totals():
    client = SOURCE.index('("descripcion", "Cliente", 185)')
    for marker in ('"cliente_documento"', '"cliente_telefono"', '"sobre"',
                   '"fecha_entrega"', '"vendedora"'):
        following = SOURCE.index(marker, client)
        assert following > client
        client = following
    assert [field[0] for field in CajaDiaria.PRODUCTO_TRABAJO] == [
        "arm_org", "cod", "laboratorio", "armazon", "cristal", "receta_dr"
    ]
    assert [field[0] for field in CajaDiaria.COBRO_PAGO] == [
        "efectivo", "transferencia", "tarjeta_cheque", "ordenes",
        "monto_convenio", "cuotas", "total", "saldo"
    ]
    assert '"armazon": (4, 0), "cristal": (4, 2)' in SOURCE
    assert '"total": (5, 0), "saldo": (5, 2)' in SOURCE
    assert 'campos_manual[clave].bind("<Key>", lambda _event: "break")' in SOURCE


def test_rc4_observations_calendar_and_clear_contract():
    assert 'def abrir_selector_fecha_entrega()' in SOURCE
    assert 'campos_manual["notas"] = ctk.CTkTextbox' in SOURCE
    clear = SOURCE[SOURCE.index("    def limpiar_operacion(confirmar=True):"):SOURCE.index("    def guardar_manual():")]
    for marker in ('estado_edicion["entry_id"] = None', 'items_venta.clear()',
                   'item_editando["index"] = None', 'grilla_caja.selection_remove',
                   'limpiar_salida()'):
        assert marker in clear
    outflow_clear = SOURCE[SOURCE.index("    def limpiar_salida():"):SOURCE.index("    def guardar_salida_integrada():")]
    assert 'estado_salida["entry_id"] = None' in outflow_clear
    assert '"salida_observacion", "salida_usuario"' in outflow_clear
    assert 'boton_salida.configure(text="Guardar salida")' in outflow_clear


def test_rc4_never_displays_open_status_in_english():
    assert 'text="Estado: ABIERTO"' in SOURCE
    assert "'ABIERTO' if cash_day.status.value == 'OPEN'" in SOURCE
