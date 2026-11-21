#!/usr/bin/env python3
"""Regenerate the embedding-portability evidence from the restore demo bundle.

Writing into the committed `evidence/` directory is how that directory is kept
honest: the evidence is derived from the bundle rather than hand-edited, and a
test compares a fresh generation against what is committed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from embedding_evidence import EVIDENCE_NAME, EvidenceError, build_embedding_evidence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "bundle"
DEFAULT_OUTPUT = ROOT / "evidence"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    result.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        digest = build_embedding_evidence(args.bundle, args.output)
    except (OSError, EvidenceError) as exc:
        print(f"embedding evidence generation failed: {exc}", file=sys.stderr)
        return 2
    print("Embedding portability evidence written")
    print(f"Output: {args.output / EVIDENCE_NAME}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
