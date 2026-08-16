from pathlib import Path
import CajaDiaria

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def test_rc11_movement_columns_are_compact_aligned_and_complete():
    expected = (
        ("hora", "Hora", 52, "center"), ("descripcion", "Cliente", 150, "w"),
        ("cliente_telefono", "Teléfono", 95, "center"),
        ("tipo_resumen", "Tipo/Resumen", 115, "w"),
        ("sobre", "Comprobante", 85, "center"), ("total", "Total", 80, "center"),
        ("efectivo", "Efectivo", 80, "center"),
        ("tarjeta_transferencia", "Tarj./Transf.", 110, "center"),
        ("monto_convenio", "A cobrar conv.", 105, "center"),
        ("cuotas", "Cuotas", 55, "center"), ("saldo", "Saldo", 80, "center"),
        ("vendedora", "Vendedora", 85, "center"), ("estado", "Estado", 85, "center"),
    )
    assert CajaDiaria.MOVEMENT_COLUMN_SPECS == expected
    assert 'grilla_caja.heading("acciones", text="Acciones", anchor="center")' in SOURCE
    assert 'def ajustar_columnas_movimientos(ancho_disponible):' in SOURCE
    assert 'scroll_horizontal.grid_remove()' in SOURCE
    assert 'stretch=False' in SOURCE


def test_rc11_draft_distribution_and_anchors_are_compact():
    for marker in ('("producto", 0.35)', '("codigo", 0.12)', '("tipo", 0.18)',
                   '("armazon", 0.12)', '("cristal", 0.12)', '("subtotal", 0.11)'):
        assert marker in SOURCE
    assert 'anchor = "w" if clave in ("producto", "tipo") else "center"' in SOURCE
    assert 'lista_productos.configure(width=ancho_izquierdo_actual, height=draft_actual)' in SOURCE
    assert 'panel_total_draft.configure(' in SOURCE
    assert 'filas_minimas = 5' in SOURCE


def test_rc19_advances_schema_once_to_016():
    """Cada release avanza el esquema una sola vez; RC19 aporta 016."""
    migrations = sorted(Path("modulos/caja_diaria/infrastructure/migrations").glob("*.sql"))
    assert len(migrations) == 16
    assert migrations[-2].name == "015_admin_counts_notifications.sql"
    assert migrations[-1].name == "016_work_tracking.sql"
