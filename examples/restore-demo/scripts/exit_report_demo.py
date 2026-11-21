"""Assemble a complete exit-report input from the restore demo.

The restore demo writes its summary and profile records into an output
directory, and the embedding inventory is committed alongside the bundle.
This module puts both under one directory and writes the `exit-manifest.v1`
that references them, which is the only arrangement in which an embeddings
store can reach a lock-in score of 0: the summary must commit to this exact
evidence document, and the scanner must re-run the restore to believe it.

The AI Infrastructure Suite is an optional, separately installed dependency.
It is imported lazily so this repository's offline demos and tests keep
working without it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from embedding_evidence import EVIDENCE_NAME
from restore_demo import run_demo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "bundle"
DEFAULT_EVIDENCE = ROOT / "evidence"
# The restore demo already writes an `evidence/` directory of its own, so the
# inventory copy gets a name of its own.
EVIDENCE_DIRECTORY = "embedding-evidence"
SUMMARY_NAME = "restore-summary.json"
MANIFEST_NAME = "exit-manifest.json"
# The embeddings vector declares the inventory instead, so it is absent here.
RESTORE_TESTED_VECTORS = (
    "policies",
    "prompts",
    "memory",
    "audit_history",
    "cost_history",
    "ontology",
)

Record = dict[str, Any]


class ExitReportDemoError(RuntimeError):
    """Raised when the exit-report input cannot be assembled."""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_exit_manifest(
    output: Path,
    *,
    bundle: Path = DEFAULT_BUNDLE,
    evidence: Path = DEFAULT_EVIDENCE,
) -> Path:
    """Run the restore demo, place the inventory beside it, write the manifest."""
    run_demo(bundle, output)
    source = evidence / EVIDENCE_NAME
    if not source.is_file():
        raise ExitReportDemoError(
            f"Embedding evidence is missing: run run_embedding_evidence.py first ({source})"
        )
    destination = output / EVIDENCE_DIRECTORY
    if destination.exists():
        raise ExitReportDemoError(f"Evidence destination already exists: {destination}")
    # Copying preserves bytes, so every digest the evidence declares, and the
    # digest the restore summary commits to, still hold.
    shutil.copytree(evidence, destination)
    summary_path = output / SUMMARY_NAME
    restore_entry = {
        "state": "restore_tested",
        "path": SUMMARY_NAME,
        "sha256": _digest(summary_path),
    }
    vectors: dict[str, Record] = dict.fromkeys(RESTORE_TESTED_VECTORS, restore_entry)
    vectors["embeddings"] = {
        "state": "embedding_inventory",
        "path": f"{EVIDENCE_DIRECTORY}/{EVIDENCE_NAME}",
        "sha256": _digest(destination / EVIDENCE_NAME),
    }
    manifest_path = output / MANIFEST_NAME
    manifest_path.write_bytes(
        (
            json.dumps(
                {"schema_version": "exit-manifest.v1", "vectors": vectors},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
    )
    return manifest_path


def run_exit_report(manifest: Path) -> tuple[Record, str]:
    """Build the verified exit report and its Markdown rendering."""
    try:
        from ai_infrastructure_suite.exit_report import (
            build_exit_report,
            render_markdown,
        )
    except ImportError as exc:  # pragma: no cover - exercised by skipping tests
        raise ExitReportDemoError(
            "ai-infrastructure-suite is required for the exit-report demo"
        ) from exc
    report = build_exit_report(manifest, verify_restores=True)
    return report, render_markdown(report)
