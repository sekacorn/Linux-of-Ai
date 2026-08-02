"""Exercise and validate the Linux of AI Quickstart Kit offline."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPOSITORY_ROOT / "scripts" / "create_vendor_exit_project.py"
EXPECTED_OUTPUTS = (
    "reports/ai_vendor_exit_report.md",
    "reports/ai_vendor_exit_report.json",
    "reports/model_routing_plan.md",
    "reports/model_routing_plan.json",
    "reports/aimeter_summary.json",
    "reports/route_aimeter_summary.json",
    "audit/audit_events.jsonl",
    "audit/route_audit_events.jsonl",
    "outputs/ai_system_map_report.md",
    "outputs/ai_system_map.mmd",
)
JSON_OUTPUTS = tuple(path for path in EXPECTED_OUTPUTS if path.endswith(".json"))
JSONL_OUTPUTS = tuple(path for path in EXPECTED_OUTPUTS if path.endswith(".jsonl"))
FORBIDDEN_PATTERNS = {
    "Windows user path": re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE),
    "macOS user path": re.compile(r"/Users/"),
    "email address": re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE
    ),
    "credential assignment": re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[^\s]+",
        re.IGNORECASE,
    ),
}


class VerificationError(RuntimeError):
    """Raised when a generated workspace does not meet the quickstart contract."""


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "no output"
        raise VerificationError(f"{label} failed: {details}")


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    events = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise VerificationError(
                f"Invalid JSONL in {path.name} line {line_number}: {error}"
            ) from error
        if not isinstance(event, dict):
            raise VerificationError(
                f"JSONL event in {path.name} line {line_number} is not an object."
            )
        events.append(event)
    if not events:
        raise VerificationError(f"No events found in {path.name}.")
    return events


def _verify_hash_chain(events: list[dict[str, Any]], source: str) -> None:
    previous_hash: str | None = None
    for index, event in enumerate(events, start=1):
        if event.get("previous_hash") != previous_hash:
            raise VerificationError(f"Broken previous_hash in {source} event {index}.")
        stored_hash = event.get("event_hash")
        payload = dict(event)
        payload.pop("event_hash", None)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        calculated_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if stored_hash != calculated_hash:
            raise VerificationError(f"Invalid event_hash in {source} event {index}.")
        previous_hash = stored_hash


def _verify_outputs(project: Path) -> dict[str, bytes]:
    snapshots: dict[str, bytes] = {}
    for relative_path in EXPECTED_OUTPUTS:
        path = project / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            raise VerificationError(
                f"Expected non-empty output is missing: {relative_path}"
            )
        snapshots[relative_path] = path.read_bytes()

    for relative_path in JSON_OUTPUTS:
        payload = _load_json(project / relative_path)
        if not isinstance(payload, dict) or not payload.get("schema_version"):
            raise VerificationError(
                f"JSON output lacks an object schema_version: {relative_path}"
            )

    for relative_path in JSONL_OUTPUTS:
        _verify_hash_chain(_load_jsonl(project / relative_path), relative_path)

    route_plan = _load_json(project / "reports/model_routing_plan.json")
    decisions = route_plan.get("task_decisions", [])
    if len(decisions) < 10:
        raise VerificationError(
            "Routing plan must include the complete fictional workload."
        )
    for decision in decisions:
        risk = decision.get("risk_level")
        route = decision.get("selected_route")
        if risk in {"high", "regulated", "unknown"} and route == "candidate_model":
            raise VerificationError(
                f"Unsafe candidate route for {risk} task: {decision.get('task_id')}"
            )
        if risk == "regulated" and route != "blocked_or_escalate":
            raise VerificationError(
                f"Regulated task is not blocked or escalated: {decision.get('task_id')}"
            )

    map_report = (project / "outputs/ai_system_map_report.md").read_text(
        encoding="utf-8"
    )
    mermaid = (project / "outputs/ai_system_map.mmd").read_text(encoding="utf-8")
    for heading in (
        "# AI System Map Report",
        "## Task and Route Controls",
        "## Limitations",
    ):
        if heading not in map_report:
            raise VerificationError(f"AI System Map report is missing: {heading}")
    for marker in (
        "flowchart TD",
        "AI System",
        "Task:",
        "Route:",
        "Audit events",
        "Cost/outcome metrics",
    ):
        if marker not in mermaid:
            raise VerificationError(f"Mermaid output is missing: {marker}")

    for path in sorted(
        candidate for candidate in project.rglob("*") if candidate.is_file()
    ):
        if (
            "__pycache__" in path.parts
            or path.name == ".env"
            or path.suffix.lower()
            in {
                ".db",
                ".pyc",
                ".pyo",
                ".sqlite",
                ".sqlite3",
            }
        ):
            raise VerificationError(
                f"Generated workspace contains a forbidden file: {path.relative_to(project)}"
            )
        if path.name == ".gitkeep":
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                raise VerificationError(
                    f"Generated file contains {label}: {path.relative_to(project)}"
                )

    return snapshots


def verify() -> None:
    with tempfile.TemporaryDirectory(
        prefix="linux-ai-quickstart-"
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        project = temporary_root / "vendor-exit-[fixture]"

        generated = _run(
            [sys.executable, str(GENERATOR), str(project)], cwd=REPOSITORY_ROOT
        )
        _require_success(generated, "Quickstart generation")
        if "Created Linux of AI quickstart project:" not in generated.stdout:
            raise VerificationError(
                "Generator did not print the creation confirmation."
            )
        if (
            "python run.py" not in generated.stdout
            or "make run" not in generated.stdout
        ):
            raise VerificationError("Generator did not print the expected next steps.")
        if not (project / "README.md").is_file():
            raise VerificationError("Generated README.md is missing.")
        if "{{PROJECT_NAME}}" in (project / "README.md").read_text(encoding="utf-8"):
            raise VerificationError("Project-name template token was not replaced.")

        refused = _run(
            [sys.executable, str(GENERATOR), str(project)], cwd=REPOSITORY_ROOT
        )
        if refused.returncode == 0 or "not empty" not in refused.stderr:
            raise VerificationError(
                "Generator did not refuse a non-empty target without --force."
            )

        run_result = _run([sys.executable, "run.py"], cwd=project)
        _require_success(run_result, "Generated quickstart run")
        if "Linux of AI Vendor Exit Quickstart complete." not in run_result.stdout:
            raise VerificationError(
                "Generated runner did not print its success message."
            )
        for relative_path in EXPECTED_OUTPUTS:
            if relative_path not in run_result.stdout:
                raise VerificationError(
                    f"Generated runner did not list its output: {relative_path}"
                )
        first_snapshot = _verify_outputs(project)

        second_run = _run([sys.executable, "run.py"], cwd=project)
        _require_success(second_run, "Deterministic quickstart rerun")
        second_snapshot = _verify_outputs(project)
        if first_snapshot != second_snapshot:
            raise VerificationError(
                "Generated outputs changed between deterministic runs."
            )

        sentinel = project / "user-file.txt"
        sentinel.write_text("preserve me\n", encoding="utf-8")
        forced = _run(
            [sys.executable, str(GENERATOR), str(project), "--force"],
            cwd=REPOSITORY_ROOT,
        )
        _require_success(forced, "Forced template refresh")
        if sentinel.read_text(encoding="utf-8") != "preserve me\n":
            raise VerificationError(
                "--force removed or changed an unrelated target file."
            )

        outside = temporary_root / "outside-readme.md"
        outside.write_text("must remain unchanged\n", encoding="utf-8")
        linked_project = temporary_root / "linked-project"
        linked_project.mkdir()
        linked_readme = linked_project / "README.md"
        try:
            linked_readme.symlink_to(outside)
        except (NotImplementedError, OSError):
            pass
        else:
            redirected = _run(
                [
                    sys.executable,
                    str(GENERATOR),
                    str(linked_project),
                    "--force",
                ],
                cwd=REPOSITORY_ROOT,
            )
            if (
                redirected.returncode == 0
                or "symbolic link or junction" not in redirected.stderr
            ):
                raise VerificationError(
                    "Generator did not refuse a template-owned symlink destination."
                )
            if outside.read_text(encoding="utf-8") != "must remain unchanged\n":
                raise VerificationError(
                    "Generator wrote through a template-owned symlink destination."
                )


def main() -> int:
    try:
        verify()
    except (OSError, VerificationError) as error:
        print(f"Quickstart verification failed: {error}", file=sys.stderr)
        return 1
    print("Linux of AI Quickstart Kit verification passed.")
    print("- generation and overwrite protection")
    print("- offline deterministic execution")
    print("- JSON, JSONL hash chains, reports, and Mermaid output")
    print("- risk routing and generated-file safety scans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
