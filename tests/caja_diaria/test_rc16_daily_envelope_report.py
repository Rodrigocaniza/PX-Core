from __future__ import annotations

from datetime import date, datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

import fitz

from modulos.caja_diaria.application.admin_ops import CountResult
from modulos.caja_diaria.application.close_report import generate_daily_envelope_control
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem


def representative_close():
    day = CashDay.open(date="15-08-2026", unit="PC", opening_cash=500_000, opened_by="Responsable demo")
    # `opened_at` toma utc_now() por defecto: sin fijarlo, el cierre historico
    # del 15-08-2026 queda antes de la apertura y el dominio lo rechaza. La
    # jornada representativa debe ser determinista, no depender de la fecha.
    day.opened_at = datetime(2026, 8, 15, 8, 0, tzinfo=timezone.utc)
    base = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    day.add_entry(CashEntry(
        description="Cliente multi artículo", envelope="S-010", customer_phone="0981 000 010",
        saleswoman="Ana", delivery_date="18-08-2026", cash=200_000, card_check=100_000,
        agreement_amount=50_000, orders="Convenio A", installments="2 cuotas",
        observations="OD: -1.00\nOI: -0.75\nControlar altura y centrado.", created_at=base,
        items=(SaleItem(description="Armazón azul", code="ARM-10", frame_price=150_000),
               SaleItem(description="Cristales orgánicos", code="CRI-10", lens_price=200_000)),
    ))
    day.add_entry(CashEntry(
        description="Cliente con saldo", envelope="S-011", saleswoman="Belén", total=300_000,
        cash=100_000, agreement_amount=100_000, orders="Convenio B", installments="3 cuotas",
        observations="Saldo confirmado para control.", created_at=base.replace(minute=10),
    ))
    day.add_entry(CashEntry(
        description="Cliente sin sobre", total=250_000, cash=250_000, saleswoman="",
        observations="Falta número de sobre y vendedora.", created_at=base.replace(minute=20),
    ))
    long_notes = "\n".join(f"Línea clínica {index:03d}: detalle completo que no puede cortarse silenciosamente." for index in range(1, 91))
    day.add_entry(CashEntry(
        description="Cliente receta extensa", envelope="S-012", saleswoman="Ana", total=400_000,
        card_check=400_000, observations=long_notes, created_at=base.replace(minute=30),
    ))
    day.add_entry(CashEntry(description="Compra insumos", expenses=50_000, outflow_type="GASTO",
                            observations="Comprobante interno", created_at=base.replace(minute=40)))
    day.add_entry(CashEntry(description="Administración", withdrawal=75_000,
                            outflow_type="ENTREGA_ADMINISTRACION", observations="Entrega controlada",
                            created_at=base.replace(minute=45)))
    voided = day.add_entry(CashEntry(description="Venta anulada", envelope="S-099", total=999_000,
                                     cash=999_000, saleswoman="Ana", created_at=base.replace(minute=50)))
    day.void_entry(voided.id, "Carga duplicada")
    day.close(closed_at=datetime(2026, 8, 15, 21, 30, tzinfo=timezone.utc))
    count = CountResult("count-rc16", day.id, "CLOSING", {}, 900_000, 925_000, -25_000,
                        "Diferencia controlada", "Responsable demo", day.closed_at)
    return day, count


def pdf_text(path):
    with fitz.open(path) as document:
        return "\n".join(page.get_text() for page in document), document.page_count


def test_landscape_paginated_report_preserves_long_text_and_repeated_headers(tmp_path):
    day, count = representative_close(); destination = tmp_path / "control.pdf"
    before = repr(day)
    generate_daily_envelope_control(day, count, "closure-rc16-0001", destination)
    assert repr(day) == before
    with fitz.open(destination) as document:
        assert document.page_count >= 3
        for index, page in enumerate(document, start=1):
            assert page.rect.width > page.rect.height
            content = page.get_text()
            assert "BC Caja — Control diario de sobres" in content
            assert f"Página {index} de {document.page_count}" in content
            title_spans = [span for block in page.get_text("dict")["blocks"]
                           for line in block.get("lines", []) for span in line["spans"]
                           if span["text"].startswith("BC Caja — Control diario de sobres")]
            assert title_spans
            title_span = min(title_spans, key=lambda span: span["bbox"][1])
            assert title_span["bbox"][1] < 160
            pixmap = page.get_pixmap(alpha=False)
            x0, y0, x1, y1 = map(int, title_span["bbox"])
            glyph_pixels = 0
            glyph_rows = set()
            glyph_columns = set()
            for y in range(max(0, y0), min(pixmap.height, y1 + 1)):
                for x in range(max(0, x0), min(pixmap.width, x1 + 1)):
                    offset = (y * pixmap.width + x) * pixmap.n
                    red, green, blue = pixmap.samples[offset:offset + 3]
                    is_glyph = red < 140 and green < 140 and blue < 180
                    glyph_pixels += is_glyph
                    if is_glyph:
                        glyph_rows.add(y); glyph_columns.add(x)
            assert glyph_pixels > 20, f"encabezado tapado en página {index}"
            assert len(glyph_rows) >= 5 and len(glyph_columns) >= 40, f"glifos no visibles en página {index}"
        full_text = "\n".join(page.get_text() for page in document)
    assert "Línea clínica 001" in full_text and "Línea clínica 090" in full_text
    assert full_text.index("Cliente multi artículo") < full_text.index("Cliente con saldo") < full_text.index("Cliente receta extensa")


def test_summary_multi_item_balances_agreements_voids_and_outflows(tmp_path):
    day, count = representative_close(); destination = tmp_path / "control.pdf"
    generate_daily_envelope_control(day, count, "closure-rc16-0002", destination)
    content, _ = pdf_text(destination)
    for expected in ("1.300.000", "550.000", "500.000", "150.000", "100.000", "50.000",
                     "75.000", "925.000", "900.000", "-25.000", "4 / 3"):
        assert expected in content
    assert content.count("Armazón azul") == 1
    assert content.count("Cristales orgánicos") == 1
    assert "Cliente con saldo\n—\n—\n300.000" in content
    assert "CONVENIO" in content and "SALDO PENDIENTE" in content
    assert "SIN N.º DE SOBRE" in content and "FALTA VENDEDORA" in content
    assert "Ventas anuladas — excluidas de los totales" in content
    assert "Venta anulada" in content and "Carga duplicada" in content
    assert "Salidas de caja" in content and "Compra insumos" in content and "Entrega controlada" in content
    assert "Totales por vendedora" in content and "FactuFácil" in content and "Dato no disponible en RC15" in content


def test_close_generates_one_attachment_and_outbox_remains_idempotent(tmp_path):
    controller = build_cash_day_controller(tmp_path / "bc_caja.sqlite3")
    session = controller.admin.create_initial_admin("adminpdf", "Clave-PDF-Segura")
    controller.admin.update_setting(session.token, "mail", {
        "enabled": True, "recipient": "control@example.com", "cc": [],
        "subject": "Cierre {fecha} - {sucursal}", "host": "smtp.example.com",
        "port": 587, "username": "sender@example.com", "secret_ref": "smtp",
    })
    controller.admin.secret_store = type("Secrets", (), {"get": lambda _self, _name: "app-secret"})()
    day = controller.admin.open_from_count("15-08-2026", "PC", {100_000: 1}, "Responsable", "open-pdf")
    controller.service.add_entry(day.id, CashEntry(description="Cliente", envelope="S-1", total=100_000,
                                                   cash=100_000, saleswoman="Ana", observations="Receta completa"))
    sent: list[EmailMessage] = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def starttls(self, context): pass
        def login(self, username, password): pass
        def send_message(self, message): sent.append(message); return {}
    with patch("smtplib.SMTP", SMTP):
        closed, _, status = controller.admin.close_with_count(day.id, {100_000: 2}, "Responsable", "close-pdf")
        assert status == "SENT"
        assert controller.admin.process_outbox() == 0
    assert len(sent) == 1
    attachment = next(sent[0].iter_attachments())
    payload = attachment.get_payload(decode=True)
    assert attachment.get_content_type() == "application/pdf" and payload.startswith(b"%PDF-")
    with controller.service.repository._connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM mail_outbox WHERE cash_day_id=?", (closed.id,)).fetchone()[0] == 1
        assert connection.execute("SELECT status FROM mail_outbox WHERE cash_day_id=?", (closed.id,)).fetchone()[0] == "SENT"
    controller.service.repository.close()
