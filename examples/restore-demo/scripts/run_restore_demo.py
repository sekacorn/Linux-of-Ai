#!/usr/bin/env python3
"""Run the deterministic three-profile restore demonstration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from restore_demo import RestoreError, run_demo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "bundle"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--live-ollama", action="store_true")
    result.add_argument("--ollama-endpoint", default="http://127.0.0.1:11434")
    result.add_argument("--ollama-model", default="qwen2.5:3b")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = run_demo(
            args.bundle,
            args.output,
            live_ollama=args.live_ollama,
            ollama_endpoint=args.ollama_endpoint,
            ollama_model=args.ollama_model,
        )
    except (OSError, RestoreError) as exc:
        print(f"restore demo failed: {exc}", file=sys.stderr)
        return 2
    print("Three-profile restore demo passed")
    print(f"Mode: {report['provider_mode']}")
    print(f"Output: {args.output / 'restore-demo-result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
