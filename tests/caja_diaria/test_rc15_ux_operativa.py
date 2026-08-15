from pathlib import Path


SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def test_operator_flow_keeps_requested_section_order():
    client = SOURCE.index('"1", "CLIENTE Y COMPROBANTE"')
    detail = SOURCE.index('"2", "DETALLE DE VENTA"')
    payment = SOURCE.index('"3", "PAGO"')
    observations = SOURCE.index('text="OBSERVACIONES"')
    assert client < detail < payment < observations


def test_observations_gain_space_without_sacrificing_five_movements_or_footer():
    assert "draft_preferido, draft_minimo = 195, 175" in SOURCE
    assert "filas_minimas = 5" in SOURCE
    assert 'pie.place(x=x_actual, y=y_footer)' in SOURCE


def test_jobs_control_is_next_to_opening_cash_and_equivalent_width():
    opening = SOURCE.index('("caja_inicial", "Caja inicial", 150)')
    jobs = SOURCE.index('text="Trabajos a entregar: 0", width=150')
    form = SOURCE.index("formulario = ctk.CTkFrame")
    assert opening < jobs < form


def test_clear_is_visible_beside_save_and_clears_sale_and_all_outflow_fields():
    save = SOURCE.index("boton_salida = campos_manual[\"accion_salida\"]")
    clear = SOURCE.index('text="Limpiar todo", command=limpiar_operacion')
    assert save < clear
    assert 'fg_color="#6D3AC1"' in SOURCE[clear:clear + 300]
    clear_operation = SOURCE[SOURCE.index("def limpiar_operacion"):SOURCE.index("def guardar_manual")]
    assert "limpiar_salida()" in clear_operation
    clear_outflow = SOURCE[SOURCE.index("def limpiar_salida"):SOURCE.index("def guardar_salida_integrada")]
    for field in ("salida_tipo", "salida_concepto", "salida_monto", "salida_observacion"):
        assert field in clear_outflow


def test_outflow_does_not_duplicate_the_canonical_responsible():
    outflow_ui = SOURCE[SOURCE.index('text="SALIDA DE CAJA"'):SOURCE.index("# El draft es una zona propia")]
    assert "salida_usuario" not in outflow_ui
    assert "servicio registra al responsable" in outflow_ui


def test_release_version_is_visible_in_footer():
    assert "BC Caja 1.0.0-rc.16" in SOURCE
