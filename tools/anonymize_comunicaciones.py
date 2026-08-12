from __future__ import annotations

import argparse
import json
from pathlib import Path

from modulos.comunicaciones.privacy import AnonymizationPipeline, PrivacyError, inspect_export


def main() -> int:
    parser = argparse.ArgumentParser(description="Anonimizacion local BC Comunicaciones")
    parser.add_argument("source")
    parser.add_argument("--output")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.preflight:
            print(json.dumps(inspect_export(args.source, repository_root=root), sort_keys=True))
        else:
            if not args.output:
                parser.error("--output es obligatorio")
            result = AnonymizationPipeline(repository_root=root).run(args.source, args.output)
            print(json.dumps({"status": result.status, "output_created": True, "report_created": True}))
        return 0
    except (PrivacyError, ValueError):
        print(json.dumps({"status": "REJECTED", "reason": "privacy_preflight_failed"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
