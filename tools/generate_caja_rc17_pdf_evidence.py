from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.caja_diaria.application.admin_ops import CountResult
from modulos.caja_diaria.application.continuous_report import generate_continuous_daily_control
from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem


def sample():
    day = CashDay.open(date=date(2026, 8, 15), unit="PC", opening_cash=500_000, opened_by="Responsable demo")
    base = datetime(2026, 8, 15, 11, 0, tzinfo=timezone.utc)
    for index in range(1, 31):
        items = (SaleItem(description=f"Armazón modelo {index:02d}", code=f"ARM-{index:03d}", frame_price=120_000),)
        if index % 4 == 0:
            items += (SaleItem(description=f"Cristales trabajo {index:02d}", code=f"CRI-{index:03d}",
                               lens_price=180_000, laboratory="Laboratorio central"),)
        total = sum(item.subtotal for item in items)
        agreement = 50_000 if index % 5 == 0 else 0
        cash = total - agreement - (50_000 if index % 6 == 0 else 0)
        note = f"OD -{index % 4}.00 · OI -{index % 3}.50 · Doctor control {index:02d}."
        if index == 12:
            note += "\n" + "\n".join(f"Detalle clínico {line:02d} sin pérdida de información." for line in range(1, 31))
        day.add_entry(CashEntry(description=f"Cliente operativo {index:02d}", envelope=f"S-{index:03d}",
                                customer_phone=f"09xx xxx {index:03d}", saleswoman=("Ana", "Belén", "Carla")[index % 3],
                                cash=cash, agreement_amount=agreement or None,
                                orders=f"Convenio {index:02d}" if agreement else "",
                                installments="2 cuotas" if agreement else "", observations=note,
                                items=items, created_at=base + timedelta(minutes=index * 7)))
    day.add_entry(CashEntry(description="Compra de insumos", expenses=80_000, outflow_type="GASTO",
                            observations="Control interno", created_at=base + timedelta(hours=5)))
    day.add_entry(CashEntry(description="Administración", withdrawal=150_000,
                            outflow_type="ENTREGA_ADMINISTRACION", observations="Entrega registrada",
                            created_at=base + timedelta(hours=5, minutes=10)))
    voided = day.add_entry(CashEntry(description="Venta anulada de control", envelope="S-099", total=200_000,
                                     cash=200_000, saleswoman="Ana", created_at=base + timedelta(hours=5, minutes=20)))
    day.void_entry(voided.id, "Carga duplicada"); day.close(closed_at=base + timedelta(hours=7))
    expected = day.opening_cash + day.totals().cash - day.totals().expenses - day.totals().withdrawals
    count = CountResult("count-rc17", day.id, "CLOSING", {}, expected, expected, 0, "", "Responsable demo", day.closed_at)
    return day, count


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("output", type=Path); args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True); day, count = sample()
    pdf = args.output / "planilla-continua-representativa.pdf"
    generate_continuous_daily_control(day, count, "RC17-DEMO-CLOSURE", pdf)
    with fitz.open(pdf) as document:
        for index, page in enumerate(document, 1):
            page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False).save(
                args.output / f"release-page-{index:02d}.png")
        print(f"RC17_EVIDENCE_OK pages={len(document)} pdf={pdf}")


if __name__ == "__main__":
    main()
