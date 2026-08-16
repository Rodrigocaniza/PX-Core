"""Chequeo de consistencia del paquete de la misión de comisiones.

Verifica las propiedades que los revisores independientes exigieron una y otra vez:
rangos de generación al día, conteos únicos, backlogs idénticos, sin anticipar la
revisión en curso y sin code spans rotos. Se ejecuta antes de publicar cada snapshot.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "artifacts" / "BC-GESTION-CENTRAL-COMISIONES-001"


def check(package: Path = PACKAGE) -> list[str]:
    docs = {p.name: p.read_text(encoding="utf-8") for p in package.glob("*.md")}
    workflow = json.loads((package / "WORKFLOW.json").read_text(encoding="utf-8"))
    problems: list[str] = []

    reviewed = max(g["generation"] for g in workflow["generations"])
    current = workflow["generation"]

    for name, text in docs.items():
        for match in re.finditer(r"generation-1/` a `generation-(\d+)/", text):
            if int(match.group(1)) != reviewed:
                problems.append(
                    f"{name}: cita el rango hasta generation-{match.group(1)}"
                    f" pero la última generación revisada es la {reviewed}")
        if re.search(rf"generation-{current}/", text):
            problems.append(f"{name}: referencia generation-{current}/, que aún no existe")
        if text.count("`") % 2:
            problems.append(f"{name}: comillas invertidas desbalanceadas")

    counts = {m.group(1).lower() for text in docs.values()
              for m in re.finditer(r"(catorce|quince|dieciséis|diecisiete)\s+"
                                   r"(?:defectos|bloqueantes)\s+financieros", text, re.I)}
    if len(counts) > 1:
        problems.append(f"conteo de bloqueantes financieros inconsistente: {sorted(counts)}")

    handoff = [line for line in docs["HANDOFF.md"].splitlines() if re.match(r"^\d+\. ", line)]
    recorded = workflow["non_blocking_findings_recorded"]
    if len(handoff) != len(recorded):
        problems.append(f"backlogs distintos: HANDOFF {len(handoff)} vs WORKFLOW {len(recorded)}")

    for directory in sorted(package.glob("generation-*")):
        number = int(directory.name.split("-")[1])
        if number > reviewed:
            problems.append(f"{directory.name}/ existe pero esa generación no figura como revisada")
    return problems


def main() -> int:
    problems = check()
    if problems:
        print("PAQUETE INCONSISTENTE:")
        for problem in problems:
            print(" -", problem)
        return 1
    print("PAQUETE CONSISTENTE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
