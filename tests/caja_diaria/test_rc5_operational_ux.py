from pathlib import Path

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def test_rc5_header_alert_and_operational_order():
    assert 'aviso_entregas.grid(row=0, column=7' in SOURCE
    assert 'f"⚠ Trabajos {pendientes}"' in SOURCE
    assert SOURCE.index('text="RESUMEN DE CAJA"') < SOURCE.index('aviso_entregas =')
    assert SOURCE.index('"CLIENTE Y COMPROBANTE"') < SOURCE.index('"DETALLE DE VENTA"') < SOURCE.index('"PAGO"')
    assert SOURCE.index('text="OBSERVACIONES"') < SOURCE.index('text="Limpiar todo"')
    assert SOURCE.index('text="Limpiar todo"') > SOURCE.index('text="Guardar salida"')


def test_rc5_clear_confirmation_and_complete_reset_contract():
    clear = SOURCE[SOURCE.index("    def hay_cambios_sin_guardar():"):SOURCE.index("    def guardar_manual():")]
    for marker in (
        'messagebox.askyesno(', 'estado_edicion["entry_id"]',
        'estado_salida["entry_id"]', 'items_venta', '"notas"',
        'limpiar_salida()', 'grilla_caja.selection_remove',
    ):
        assert marker in clear
    assert 'limpiar_operacion(confirmar=False)' in SOURCE
    assert 'fg_color="#6D3AC1"' in SOURCE


def test_rc5_observations_and_compact_visibility_contract():
    assert 'draft_preferido, draft_minimo = 182, 145' in SOURCE
    assert 'height=alto_observaciones' in SOURCE
    assert 'filas_minimas = 5' in SOURCE
    assert 'TAMANO_LOTE_GRILLA = 250' in SOURCE
    assert 'campos_manual["notas"] = ctk.CTkTextbox' in SOURCE


def test_rc5_responsible_identity_is_protected_and_audited():
    assert '("salida_usuario", 105, "Responsable")' in SOURCE
    assert 'campos_manual["salida_usuario"].configure(state="disabled")' in SOURCE
    assert 'user=os.environ.get("USERNAME") or os.environ.get("USER") or ""' in SOURCE
    controller = Path("modulos/caja_diaria/ui/controller.py").read_text(encoding="utf-8")
    service = Path("modulos/caja_diaria/application/services.py").read_text(encoding="utf-8")
    assert 'performed_by=existing.performed_by' in controller
    assert 'audit_reason=reason, edited_by=user' in service
