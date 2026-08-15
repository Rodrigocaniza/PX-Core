"""Generate and render the synthetic RC16 daily-envelope report evidence."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.caja_diaria.application.close_report import generate_daily_envelope_control
from tests.caja_diaria.test_rc16_daily_envelope_report import representative_close


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    pdf = args.output / "control-diario-sobres-representativo.pdf"
    day, count = representative_close()
    generate_daily_envelope_control(day, count, "RC16-DEMO-CLOSURE-0001", pdf)
    with fitz.open(pdf) as document:
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
            pixmap.save(args.output / f"release-v6-page-{index:02d}.png")
        print(f"BC_CAJA_RC16_PDF_EVIDENCE_OK pages={document.page_count} pdf={pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
