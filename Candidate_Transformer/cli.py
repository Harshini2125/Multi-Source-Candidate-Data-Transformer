"""Command-line surface.

    python -m candidate_transformer.cli <inputs_dir> [--config CONFIG] [--out OUT]

Points the pipeline at a directory of input files and a config, then writes the
resulting JSON to a file or stdout. The surface is intentionally thin — the
engine is where the value is.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG, OutputConfig
from .pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="candidate_transformer",
        description="Transform multi-source candidate data into canonical profiles.",
    )
    parser.add_argument("inputs", type=Path, help="directory of input files")
    parser.add_argument("--config", type=Path, default=None,
                        help="output config JSON (defaults to the canonical schema)")
    parser.add_argument("--out", type=Path, default=None,
                        help="write JSON here (defaults to stdout)")
    parser.add_argument("--no-validate", action="store_true",
                        help="skip output schema validation")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="log per-source extraction counts")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if not args.inputs.is_dir():
        parser.error(f"inputs directory not found: {args.inputs}")

    config = OutputConfig.load(args.config) if args.config else DEFAULT_CONFIG

    try:
        results = run(args.inputs, config, validate=not args.no_validate)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(results, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {len(results)} profile(s) to {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
