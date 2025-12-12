"""Utility to export the FastAPI OpenAPI spec to a JSON file for QA tools."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fastapi.encoders import jsonable_encoder

# Allow importing app.main when running from folder-gateway-skill
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from app.main import app  # noqa: E402


def export_openapi(output_path: Path) -> None:
    spec = jsonable_encoder(app.openapi())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump OpenAPI JSON from app.main")
    default_output = REPO_ROOT / "folder-gateway-skill" / "openapi.json"
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=default_output,
        help=f"Output file path (default: {default_output})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_openapi(args.output)
    print(f"OpenAPI spec written to {args.output}")


if __name__ == "__main__":
    main()
