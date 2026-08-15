"""A4 landscape daily envelope-control report; presentation only."""
from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..domain.models import BUSINESS_TIMEZONE, CashEntryStatus

BLUE = colors.HexColor("#165FA7")
PALE_BLUE = colors.HexColor("#EAF3FB")
PALE_YELLOW = colors.HexColor("#FFF3CD")
PALE_RED = colors.HexColor("#FCE8E6")
GRAY = colors.HexColor("#52657D")
LIGHT = colors.HexColor("#F4F6F8")
LINE = colors.HexColor("#AAB7C4")


def money(value):
    return f"{int(value or 0):,}".replace(",", ".")


def text(value, fallback="—"):
    value = str(value or "").strip()
    return value or fallback


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("r-title", parent=base["Title"], fontSize=16, leading=19, textColor=BLUE, spaceAfter=4),
        "section": ParagraphStyle("r-section", parent=base["Heading2"], fontSize=11, leading=14, textColor=BLUE,
                                  spaceBefore=7, spaceAfter=4),
        "body": ParagraphStyle("r-body", parent=base["BodyText"], fontSize=8.2, leading=10.5),
        "small": ParagraphStyle("r-small", parent=base["BodyText"], fontSize=7.4, leading=9.2),
        "label": ParagraphStyle("r-label", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.4,
                                leading=9.2, textColor=GRAY),
        "warning": ParagraphStyle("r-warning", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8,
                                  leading=10, textColor=colors.HexColor("#9A3412")),
        "head": ParagraphStyle("r-head", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8,
                               leading=10, textColor=colors.white, alignment=TA_CENTER),
        "right": ParagraphStyle("r-right", parent=base["BodyText"], fontSize=8.2, leading=10.5, alignment=TA_RIGHT),
    }


def para(value, style, fallback="—"):
    return Paragraph(escape(text(value, fallback)).replace("\n", "<br/>"), style)


def counting_canvas():
    from reportlab.pdfgen.canvas import Canvas

    class CountingCanvas(Canvas):
        page_count = 0

        def showPage(self):
            type(self).page_count += 1
            super().showPage()

    return CountingCanvas


def final_canvas(total_pages, context):
    from reportlab.pdfgen.canvas import Canvas

    class FinalCanvas(Canvas):
        def showPage(self):
            page_width, page_height = landscape(A4)
            # Flowables may leave a translated/clipped graphics state active at
            # a forced page break. Unwind it before stamping fixed page chrome.
            while self.state_stack:
                self.restoreState()
            self.resetTransforms()
            self.saveState(); self.setStrokeColor(LINE); self.setLineWidth(.5)
            self.setFillColor(colors.white)
            self.rect(0, page_height - 15 * mm, page_width, 15 * mm, stroke=0, fill=1)
            self.line(14 * mm, page_height - 13 * mm, page_width - 14 * mm, page_height - 13 * mm)
            self.setFillColor(BLUE); self.setFont("Helvetica-Bold", 8.5)
            self.drawString(14 * mm, page_height - 10 * mm, "BC Caja — Control diario de sobres")
            self.setFillColor(GRAY); self.setFont("Helvetica", 7.5)
            self.drawRightString(page_width - 14 * mm, page_height - 10 * mm,
                                 f"{context['date']} · {context['unit']} · Cierre {context['closure']}")
            self.line(14 * mm, 11 * mm, page_width - 14 * mm, 11 * mm)
            self.drawString(14 * mm, 7 * mm, "Documento de control operativo · Uso interno")
            self.drawRightString(page_width - 14 * mm, 7 * mm,
                                 f"Página {self.getPageNumber()} de {total_pages}")
            self.restoreState()
            super().showPage()

    return FinalCanvas


def stamp_page_chrome(source, destination, context):
    """Merge immutable chrome after layout, outside Platypus canvas state."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen.canvas import Canvas

    reader = PdfReader(str(source)); writer = PdfWriter(); total = len(reader.pages)
    page_width, page_height = landscape(A4)
    for index, page in enumerate(reader.pages, start=1):
        stream = BytesIO(); overlay = Canvas(stream, pagesize=landscape(A4))
        overlay.setFillColor(colors.white)
        overlay.rect(0, page_height - 15 * mm, page_width, 15 * mm, stroke=0, fill=1)
        overlay.setStrokeColor(LINE); overlay.setLineWidth(.5)
        overlay.line(14 * mm, page_height - 13 * mm, page_width - 14 * mm, page_height - 13 * mm)
        overlay.setFillColor(BLUE); overlay.setFont("Helvetica-Bold", 8.5)
        overlay.drawString(14 * mm, page_height - 10 * mm, "BC Caja — Control diario de sobres")
        overlay.setFillColor(GRAY); overlay.setFont("Helvetica", 7.5)
        overlay.drawRightString(page_width - 14 * mm, page_height - 10 * mm,
                                f"{context['date']} · {context['unit']} · Cierre {context['closure']}")
        overlay.line(14 * mm, 11 * mm, page_width - 14 * mm, 11 * mm)
        overlay.drawString(14 * mm, 7 * mm, "Documento de control operativo · Uso interno")
        overlay.drawRightString(page_width - 14 * mm, 7 * mm, f"Página {index} de {total}")
        overlay.save(); stream.seek(0)
        # Compose onto a fresh page so each source stream is wrapped in its own
        # graphics state by pypdf; malformed clipping cannot cross layers.
        combined = writer.add_blank_page(width=page_width, height=page_height)
        combined.merge_page(page, over=True)
        # Chrome is deliberately the last layer.  Some PDF viewers retain a
        # clipping path from the content stream; placing the overlay last keeps
        # the page identity and footer visible independently of that state.
        combined.merge_page(PdfReader(stream).pages[0], over=True)
        combined.compress_content_streams()
    writer.compress_identical_objects(remove_unreferenced=True)
    with Path(destination).open("wb") as handle:
        writer.write(handle)


def summary(day, count, sty, width):
    totals = day.totals()
    sales = [e for e in day.entries if e.status is CashEntryStatus.ACTIVE and not e.outflow_type]
    agreements = sum(e.agreement_amount or 0 for e in sales)
    balances = sum(e.client_balance_amount for e in sales)
    envelopes = len({e.envelope for e in sales if e.envelope})
    values = [
        ("Caja inicial", money(day.opening_cash)), ("Total ventas", money(totals.total)),
        ("Efectivo cobrado", money(totals.cash)), ("Tarjeta / Transferencia", money(totals.card_check)),
        ("A cobrar convenio", money(agreements)), ("Saldo clientes", money(balances)),
        ("Gastos", money(totals.expenses)), ("Entregas administración", money(totals.withdrawals)),
        ("Efectivo esperado", money(count.expected_total)), ("Efectivo contado", money(count.counted_total)),
        ("Diferencia", money(count.difference)), ("Ventas / sobres", f"{len(sales)} / {envelopes}"),
    ]
    pairs = [[para(label, sty["label"]), para(value, sty["right"])] for label, value in values]
    rows = [sum(pairs[i:i + 3], []) for i in range(0, len(pairs), 3)]
    table = Table(rows, colWidths=[width / 9, width * 2 / 9] * 3)
    commands = [("GRID", (0, 0), (-1, -1), .35, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE), ("BACKGROUND", (2, 0), (2, -1), PALE_BLUE),
                ("BACKGROUND", (4, 0), (4, -1), PALE_BLUE), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if count.difference:
        commands += [("BACKGROUND", (3, 3), (3, 3), PALE_RED), ("TEXTCOLOR", (3, 3), (3, 3), colors.red)]
    table.setStyle(TableStyle(commands)); return table


def sale_flowables(entry, sty, width, show_identity=False):
    flags = []
    if not entry.envelope: flags.append("SIN N.º DE SOBRE")
    if entry.client_balance_amount: flags.append("SALDO PENDIENTE")
    if entry.agreement_amount: flags.append("CONVENIO")
    if not entry.saleswoman: flags.append("FALTA VENDEDORA")
    if not entry.effective_items: flags.append("SIN DETALLE")
    title = (f"{entry.created_at.astimezone(BUSINESS_TIMEZONE):%H:%M} · "
             f"Sobre {text(entry.envelope, 'SIN NÚMERO')} · {text(entry.description)}")
    heading = Table([[para(title, sty["body"]), para(" · ".join(flags), sty["warning"], "")]],
                    colWidths=[width * .62, width * .38])
    heading.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE_YELLOW if flags else PALE_BLUE),
                                 ("BOX", (0, 0), (-1, -1), .6, BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    fields = [
        ("Comprobante/boleta", "No registrado en RC15"), ("Teléfono", entry.customer_phone),
        ("Vendedora", entry.saleswoman), ("Fecha entrega", entry.delivery_date.strftime("%d-%m-%Y") if entry.delivery_date else "—"),
        ("Total", money(entry.total)), ("Efectivo", money(entry.cash)),
        ("Tarjeta/Transferencia", money(entry.card_check)),
        ("Convenio / cuotas", f"{text(entry.orders)} · {money(entry.agreement_amount)} · {text(entry.installments)}"),
        ("Saldo pendiente", money(entry.client_balance_amount)), ("FactuFácil", "Dato no disponible en RC15"),
    ]
    pairs = [[para(label, sty["label"]), para(value, sty["small"])] for label, value in fields]
    details = Table([sum(pairs[0:4], []), sum(pairs[4:8], []), sum(pairs[8:10], [])],
                    colWidths=[width * .10, width * .15] * 4)
    details.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("BACKGROUND", (0, 0), (0, -1), LIGHT), ("BACKGROUND", (2, 0), (2, -1), LIGHT),
                                 ("BACKGROUND", (4, 0), (4, -1), LIGHT), ("BACKGROUND", (6, 0), (6, -1), LIGHT),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    item_rows = [[para("Productos / trabajo realizado", sty["head"]), para("Código", sty["head"]),
                  para("Detalle", sty["head"]), para("Subtotal", sty["head"])]]
    for item in entry.effective_items:
        detail = " · ".join(filter(None, (item.item_type, item.laboratory, item.prescription_doctor)))
        visible_subtotal = item.subtotal if entry.items else entry.total
        item_rows.append([para(item.description, sty["small"]), para(item.code, sty["small"]),
                          para(detail, sty["small"]), para(money(visible_subtotal), sty["right"])])
    items = LongTable(item_rows, repeatRows=1, colWidths=[width * .35, width * .12, width * .38, width * .15])
    items.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), GRAY), ("GRID", (0, 0), (-1, -1), .25, LINE),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    note_lines = str(entry.observations or "").splitlines() or ["—"]

    def note_table(lines):
        rows = [[para("Observaciones / receta", sty["head"]), para("Texto completo", sty["head"])]]
        rows += [[para("", sty["label"], ""), para(line, sty["body"])] for line in lines]
        # Chunks are bounded below the frame height, so a non-splitting Table is
        # safer than LongTable here and cannot escape the document frame.
        table = Table(rows, colWidths=[width * .16, width * .84], splitByRow=0)
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .25, LINE),
                                   ("BACKGROUND", (0, 0), (-1, 0), GRAY),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 4),
                                   ("TOPPADDING", (0, 0), (-1, -1), 4),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return table

    # ReportLab can place a very large split-table fragment above the frame on
    # continuation pages. Bound each fragment explicitly so long prescriptions
    # always start below the page header and repeat their own column heading.
    note_chunks = [note_lines[i:i + 15] for i in range(0, len(note_lines), 15)]
    notes = []
    for index, chunk in enumerate(note_chunks):
        table = note_table(chunk)
        if index:
            continuation = Table([[para("BC Caja — Control diario de sobres · continuación", sty["label"]),
                                   para("Observaciones / receta", sty["right"])]],
                                 colWidths=[width * .65, width * .35])
            continuation.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), .4, LINE),
                                               ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                               ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            notes.extend([PageBreak(), continuation, Spacer(1, 3 * mm), table])
        else:
            continuation = Table([[para("BC Caja — Control diario de sobres · continuación", sty["label"]),
                                   para("Observaciones / receta", sty["right"])]],
                                 colWidths=[width * .65, width * .35])
            continuation.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), .4, LINE),
                                               ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                               ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            notes.extend([PageBreak(), continuation, Spacer(1, 3 * mm), table])
    block = [heading, details, items, *notes, Spacer(1, 3 * mm)]
    guard = Spacer(1, 18 * mm)
    identity = []
    if show_identity:
        marker = Table([[para("BC Caja — Control diario de sobres · continuación", sty["label"]),
                         para("Control de sobres", sty["right"])]], colWidths=[width * .65, width * .35])
        marker.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), .4, LINE),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        identity = [marker, Spacer(1, 3 * mm)]
    prefix = ([PageBreak(), *identity] if show_identity else [guard])
    return (prefix + block if len(note_lines) <= 15
            else [*prefix, heading, details, items, *notes, Spacer(1, 3 * mm)])


def section(title, rows, sty, width, headers):
    data = [[para(h, sty["head"]) for h in headers]] + rows
    table = LongTable(data, repeatRows=1, colWidths=[width / len(headers)] * len(headers), splitByRow=1, splitInRow=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BLUE), ("GRID", (0, 0), (-1, -1), .35, LINE),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return [Paragraph(title, sty["section"]), table]


def generate_daily_envelope_control(day, count, closure_id, destination: Path) -> Path:
    """Generate the PDF without mutating the day, repository, outbox, or totals."""
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(".tmp")
    width = landscape(A4)[0] - 28 * mm
    sty = styles(); opened = day.opened_at.astimezone(BUSINESS_TIMEZONE)
    closed = day.closed_at.astimezone(BUSINESS_TIMEZONE) if day.closed_at else None
    context = {"date": day.business_date.strftime("%d-%m-%Y"), "unit": day.unit, "closure": closure_id[:8]}
    total_pages = 0

    def static_chrome(canvas, _doc):
        page_width, page_height = landscape(A4)
        canvas.saveState(); canvas.setStrokeColor(LINE); canvas.setLineWidth(.5)
        canvas.line(14 * mm, page_height - 13 * mm, page_width - 14 * mm, page_height - 13 * mm)
        canvas.setFillColor(BLUE); canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawString(14 * mm, page_height - 10 * mm, "BC Caja — Control diario de sobres")
        canvas.setFillColor(GRAY); canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(page_width - 14 * mm, page_height - 10 * mm,
                               f"{context['date']} · {context['unit']} · Cierre {context['closure']}")
        canvas.line(14 * mm, 11 * mm, page_width - 14 * mm, 11 * mm)
        canvas.drawString(14 * mm, 7 * mm, "Documento de control operativo · Uso interno")
        if total_pages:
            canvas.drawRightString(page_width - 14 * mm, 7 * mm,
                                   f"Página {canvas.getPageNumber()} de {total_pages}")
        canvas.restoreState()
    doc = SimpleDocTemplate(str(temp), pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm,
                            # Keep split-table continuation fragments below the
                            # static header band on every page.
                            topMargin=25 * mm, bottomMargin=15 * mm, title="BC Caja — Control diario de sobres")
    meta_values = [["Fecha", context["date"], "Sucursal/caja", day.unit, "N.º cierre", closure_id],
                   ["Responsable", count.responsible, "Apertura / cierre", f"{opened:%H:%M} / {closed:%H:%M}" if closed else f"{opened:%H:%M} / —",
                    "Estado", day.status.value]]
    meta = Table([[para(v, sty["label"] if i % 2 == 0 else sty["body"]) for i, v in enumerate(row)] for row in meta_values],
                 colWidths=[width * .09, width * .19, width * .11, width * .18, width * .08, width * .35])
    meta.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .3, LINE), ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
                              ("BACKGROUND", (2, 0), (2, -1), PALE_BLUE), ("BACKGROUND", (4, 0), (4, -1), PALE_BLUE),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story = [Paragraph("BC Caja — Control diario de sobres", sty["title"]), meta,
             Paragraph("Resumen económico", sty["section"]), summary(day, count, sty, width),
             Paragraph("Control de sobres", sty["section"])]
    sales = sorted((e for e in day.entries if e.status is CashEntryStatus.ACTIVE and not e.outflow_type), key=lambda e: (e.created_at, e.id))
    for index, entry in enumerate(sales):
        story.extend(sale_flowables(entry, sty, width, show_identity=index > 0))
    outflows = sorted((e for e in day.entries if e.status is CashEntryStatus.ACTIVE and e.outflow_type), key=lambda e: (e.created_at, e.id))
    out_rows = [[para(f"{e.created_at.astimezone(BUSINESS_TIMEZONE):%H:%M}", sty["small"]),
                 para("Gasto" if e.outflow_type == "GASTO" else "Entrega administración", sty["small"]),
                 para(e.description, sty["small"]), para(money(e.expenses or e.withdrawal), sty["right"]),
                 para(e.observations, sty["small"])] for e in outflows]
    story += section("Salidas de caja", out_rows or [[para("Sin salidas", sty["body"])] + [para("", sty["body"])] * 4],
                     sty, width, ["Hora", "Tipo", "Concepto/destino", "Monto", "Observaciones"])
    final_marker = Table([[para("BC Caja — Control diario de sobres · continuación", sty["label"]),
                           para("Control final", sty["right"])]], colWidths=[width * .65, width * .35])
    final_marker.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), .4, LINE),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                      ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                      ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [PageBreak(), final_marker, Spacer(1, 3 * mm)]
    voided = sorted((e for e in day.entries if e.status is CashEntryStatus.VOIDED), key=lambda e: (e.created_at, e.id))
    void_rows = [[para(f"{e.created_at.astimezone(BUSINESS_TIMEZONE):%H:%M}", sty["small"]), para(e.envelope, sty["small"]),
                  para(e.description, sty["small"]), para(money(e.total or e.expenses or e.withdrawal), sty["right"]),
                  para(e.void_reason, sty["small"])] for e in voided]
    story += section("Ventas anuladas — excluidas de los totales", void_rows or [[para("Sin anulaciones", sty["body"])] + [para("", sty["body"])] * 4],
                     sty, width, ["Hora", "Sobre", "Cliente", "Importe", "Motivo"])
    sellers = defaultdict(lambda: [0, 0])
    for entry in sales:
        key = text(entry.saleswoman, "Sin vendedora"); sellers[key][0] += 1; sellers[key][1] += entry.total or 0
    seller_rows = [[para(name, sty["body"]), para(qty, sty["right"]), para(money(total), sty["right"])]
                   for name, (qty, total) in sorted(sellers.items())]
    story += section("Totales por vendedora", seller_rows or [[para("Sin ventas", sty["body"]), para("0", sty["right"]), para("0", sty["right"])]],
                     sty, width, ["Vendedora", "Ventas", "Total"])
    signature = Table([[""], [""]], colWidths=[width], rowHeights=[15 * mm, 15 * mm],
                      style=TableStyle([("BOX", (0, 0), (-1, -1), .5, LINE), ("LINEBELOW", (0, 0), (-1, 0), .35, LINE)]))
    story += [Paragraph("Observaciones finales de control", sty["section"]), signature, Spacer(1, 7 * mm),
              Table([["Responsable / firma", "Control / firma"]], colWidths=[width / 2] * 2,
                    style=TableStyle([("LINEABOVE", (0, 0), (-1, -1), .5, GRAY), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                      ("FONT", (0, 0), (-1, -1), "Helvetica", 8), ("TEXTCOLOR", (0, 0), (-1, -1), GRAY)]))]
    # Layout first, then merge chrome as a separate PDF layer. This avoids any
    # dependency on the graphics state left by a split table or forced page break.
    content_path = destination.with_suffix(".content.tmp")
    content_doc = SimpleDocTemplate(str(content_path), pagesize=landscape(A4), leftMargin=14 * mm,
                                    rightMargin=14 * mm, topMargin=25 * mm, bottomMargin=15 * mm)
    content_doc.build(story)
    stamp_page_chrome(content_path, temp, context)
    content_path.unlink(missing_ok=True)
    temp.replace(destination); return destination
