"""RC17 compact continuous daily-control report; presentation only."""
from __future__ import annotations

from pathlib import Path
from collections import defaultdict
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..domain.models import BUSINESS_TIMEZONE, CashEntryStatus
from .close_report import BLUE, GRAY, LIGHT, LINE, PALE_RED, PALE_YELLOW, money, stamp_page_chrome, text


HEADERS = (
    "Cliente / Descripción", "Sobre", "Producto / Trabajo", "Código", "Armazón", "Cristal",
    "Doctor", "Total", "Efectivo", "Tarjeta / Transf.", "Convenio / Orden",
    "Cuotas", "Saldo", "Gastos / Entregas",
)
WIDTHS_MM = (38, 13, 36, 12, 15, 16, 18, 18, 18, 19, 21, 13, 18, 21)


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("c-title", parent=base["Title"], fontSize=15, leading=17, textColor=BLUE),
        "meta": ParagraphStyle("c-meta", parent=base["BodyText"], fontSize=7.2, leading=8.6),
        "cell": ParagraphStyle("c-cell", parent=base["BodyText"], fontSize=6.4, leading=7.6),
        "num": ParagraphStyle("c-num", parent=base["BodyText"], fontSize=6.4, leading=7.6, alignment=TA_RIGHT),
        "head": ParagraphStyle("c-head", parent=base["BodyText"], fontName="Helvetica-Bold",
                                fontSize=6.1, leading=7, textColor=colors.white),
        "section": ParagraphStyle("c-section", parent=base["Heading2"], fontSize=10, leading=12,
                                   textColor=BLUE, spaceBefore=6, spaceAfter=3),
        "detail": ParagraphStyle("c-detail", parent=base["BodyText"], fontSize=7, leading=8.7),
    }


def _p(value, style, fallback="—"):
    value = str(value or "").strip() or fallback
    return Paragraph(escape(value).replace("\n", "<br/>"), style)


def _doctor(entry, item):
    return str(getattr(item, "prescription_doctor", "") or entry.prescription_doctor or "").strip() or "—"


def _sale_rows(entry, sty):
    items = entry.effective_items or ()
    rows = []
    for index, item in enumerate(items or (None,)):
        first = index == 0
        frame = money(item.frame_final_price) if item and item.frame_price is not None else "—"
        lens = money(item.lens_final_price) if item and item.lens_price is not None else "—"
        agreement = text(entry.orders) if entry.agreement_amount else "—"
        balance = money(entry.client_balance_amount) if entry.client_balance_amount else "Cancelado"
        rows.append([
            _p(entry.description if first else "", sty["cell"], ""),
            _p(entry.envelope if first else "", sty["cell"], ""),
            _p(item.description if item else entry.description, sty["cell"]),
            _p(item.code if item else entry.code, sty["cell"]),
            _p(frame, sty["num"]), _p(lens, sty["num"]),
            _p(_doctor(entry, item), sty["cell"]),
            _p(money(entry.total) if first else "", sty["num"], ""),
            _p(money(entry.cash) if first else "", sty["num"], ""),
            _p(money(entry.card_check) if first else "", sty["num"], ""),
            _p(agreement if first else "", sty["cell"], ""),
            _p(entry.installments if first else "", sty["cell"], ""),
            _p(balance if first else "", sty["num"], ""), _p("", sty["num"], ""),
        ])
    return rows


def _continuous_table(day, count, sty, width):
    rows = [[_p(h, sty["head"]) for h in HEADERS]]
    styles = [("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("GRID", (0, 0), (-1, -1), .25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("LEFTPADDING", (0, 0), (-1, -1), 2.2), ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
              ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    rows.append([_p("CAJA INICIAL", sty["cell"])] + [_p("", sty["cell"], "") for _ in range(7)] +
                [_p(money(day.opening_cash), sty["num"])] + [_p("", sty["cell"], "") for _ in range(5)])
    styles += [("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EAF3FB")),
               ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold")]
    ordered = sorted(day.entries, key=lambda e: (e.created_at, e.id))
    band = 0
    for entry in ordered:
        start = len(rows)
        if entry.status is CashEntryStatus.VOIDED:
            row = ([_p(f"ANULADA · {entry.description}", sty["cell"]), _p(entry.envelope, sty["cell"]),
                    _p(entry.void_reason, sty["cell"])] + [_p("", sty["cell"], "") for _ in range(10)] +
                   [_p("ANULADA", sty["cell"])])
            rows.append(row); styles.append(("BACKGROUND", (0, start), (-1, start), PALE_RED))
        elif entry.outflow_type:
            label = "GASTO" if entry.outflow_type == "GASTO" else "ENTREGA ADM."
            amount = entry.expenses or entry.withdrawal
            rows.append([_p(entry.description, sty["cell"]), _p("", sty["cell"], ""), _p(label, sty["cell"])] +
                        [_p("", sty["cell"], "") for _ in range(10)] + [_p(money(amount), sty["num"])])
            styles.append(("BACKGROUND", (0, start), (-1, start), colors.HexColor("#F3F4F6")))
        else:
            sale_rows = _sale_rows(entry, sty); rows.extend(sale_rows)
            end = len(rows) - 1
            styles += [("NOSPLIT", (0, start), (-1, end)), ("LINEABOVE", (0, start), (-1, start), .7, GRAY)]
            if band % 2:
                styles.append(("BACKGROUND", (0, start), (-1, end), colors.HexColor("#F7FAFC")))
            if entry.client_balance_amount:
                styles.append(("BACKGROUND", (12, start), (12, start), PALE_YELLOW))
            if entry.agreement_amount:
                styles.append(("BACKGROUND", (10, start), (11, start), PALE_YELLOW))
            if not entry.envelope or not entry.description:
                styles.append(("BACKGROUND", (0, start), (1, start), PALE_RED))
            band += 1
    totals = day.totals()
    active = [e for e in day.entries if e.status is CashEntryStatus.ACTIVE and not e.outflow_type]
    agreements = sum(e.agreement_amount or 0 for e in active); balances = sum(e.client_balance_amount for e in active)
    total_row = len(rows)
    rows.append([_p("TOTALES", sty["head"])] + [_p("", sty["head"], "") for _ in range(6)] +
                [_p(money(totals.total), sty["num"]), _p(money(totals.cash), sty["num"]),
                 _p(money(totals.card_check), sty["num"]), _p(money(agreements), sty["num"]),
                 _p("", sty["num"], ""), _p(money(balances), sty["num"]),
                 _p(f"G {money(totals.expenses)} / E {money(totals.withdrawals)}", sty["num"])])
    rows.append([_p("CIERRE", sty["head"]), _p(
        f"Efectivo esperado {money(count.expected_total)}  ·  Efectivo contado {money(count.counted_total)}  ·  Diferencia {money(count.difference)}",
        sty["head"])] + [_p("", sty["head"], "") for _ in range(12)])
    styles += [("BACKGROUND", (0, total_row), (-1, total_row + 1), GRAY),
               ("TEXTCOLOR", (0, total_row), (-1, total_row + 1), colors.white),
               ("SPAN", (1, total_row + 1), (-1, total_row + 1))]
    scale = width / sum(x * mm for x in WIDTHS_MM)
    table = LongTable(rows, repeatRows=1, colWidths=[x * mm * scale for x in WIDTHS_MM], splitByRow=1)
    table.setStyle(TableStyle(styles)); return table


def _seller_totals(day, sty, width):
    values = defaultdict(lambda: [0, 0])
    for entry in day.entries:
        if entry.status is CashEntryStatus.ACTIVE and not entry.outflow_type:
            name = text(entry.saleswoman, "Sin vendedora")
            values[name][0] += 1; values[name][1] += entry.total or 0
    rows = [[_p("Vendedora", sty["head"]), _p("Ventas", sty["head"]), _p("Total", sty["head"])]]
    rows += [[_p(name, sty["detail"]), _p(qty, sty["num"]), _p(money(total), sty["num"])]
             for name, (qty, total) in sorted(values.items())]
    table = Table(rows, colWidths=[width * .55, width * .15, width * .30])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BLUE), ("GRID", (0, 0), (-1, -1), .25, LINE),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return table


def generate_continuous_daily_control(day, count, closure_id: str, destination: Path) -> Path:
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    content = destination.with_suffix(".content.tmp"); final = destination.with_suffix(".tmp")
    sty = _styles(); page_width = landscape(A4)[0]; width = page_width - 16 * mm
    opened = day.opened_at.astimezone(BUSINESS_TIMEZONE); closed = day.closed_at.astimezone(BUSINESS_TIMEZONE) if day.closed_at else None
    context = {"date": day.business_date.strftime("%d-%m-%Y"), "unit": day.unit, "closure": closure_id[:8],
               "title": "BC Caja — Planilla diaria de sobres"}
    meta = _p(f"Caja {day.unit} · Apertura {opened:%H:%M} · Cierre {closed:%H:%M} · Responsable {count.responsible} · Estado {day.status.value}", sty["meta"])
    story = [Paragraph("BC Caja — Planilla diaria de sobres", sty["title"]), meta,
             Paragraph("Totales por vendedora", sty["section"]), _seller_totals(day, sty, width),
             Spacer(1, 3 * mm), _continuous_table(day, count, sty, width)]
    doc = SimpleDocTemplate(str(content), pagesize=landscape(A4), leftMargin=8 * mm, rightMargin=8 * mm,
                            topMargin=18 * mm, bottomMargin=14 * mm, title="BC Caja — Planilla diaria de sobres")
    doc.build(story); stamp_page_chrome(content, final, context); content.unlink(missing_ok=True)
    final.replace(destination); return destination
