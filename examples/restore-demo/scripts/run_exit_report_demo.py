#!/usr/bin/env python3
"""Run the restore demo and report its embedding lock-in with ai-suite.

Requires a separately installed AI Infrastructure Suite. Without it, the
command explains what is missing and exits non-zero rather than failing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from exit_report_demo import (
    DEFAULT_BUNDLE,
    DEFAULT_EVIDENCE,
    ExitReportDemoError,
    build_exit_manifest,
    run_exit_report,
)
from restore_demo import RestoreError


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    result.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--json", action="store_true", help="print the JSON report")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        manifest = build_exit_manifest(
            args.output, bundle=args.bundle, evidence=args.evidence
        )
        report, markdown = run_exit_report(manifest)
    except (OSError, RestoreError, ExitReportDemoError, ValueError) as exc:
        print(f"exit-report demo failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else markdown)
    row = report["vectors"]["embeddings"]
    print(f"\nManifest: {manifest}", file=sys.stderr)
    print(
        f"Embeddings lock-in: {row['score']} ({row['verification_level']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
