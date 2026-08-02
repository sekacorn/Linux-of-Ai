"""Generate deterministic Linux of AI vendor-exit quickstart outputs offline."""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
REPORTS_DIR = ROOT / "reports"
AUDIT_DIR = ROOT / "audit"
OUTPUTS_DIR = ROOT / "outputs"
GENERATED_AT = "2026-01-01T00:00:00Z"
MAX_INPUT_BYTES = 2_000_000
MAX_TASKS = 1_000
ROUTES = {"candidate_model", "baseline_model", "human_review", "blocked_or_escalate"}
RISK_LEVELS = {"low", "medium", "high", "regulated", "unknown"}


class QuickstartDataError(ValueError):
    """Raised when replacement fixture data violates the quickstart contract."""


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise QuickstartDataError(
            f"Required input file is missing: {path.relative_to(ROOT)}"
        )
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise QuickstartDataError(
            f"Input file exceeds {MAX_INPUT_BYTES} bytes: {path.relative_to(ROOT)}"
        )
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise QuickstartDataError(f"Expected a JSON object: {path.relative_to(ROOT)}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for line_number, line in enumerate(_read_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise QuickstartDataError(
                f"Expected an object in {path.name} line {line_number}."
            )
        tasks.append(payload)
        if len(tasks) > MAX_TASKS:
            raise QuickstartDataError(f"Task count exceeds the {MAX_TASKS} task limit.")
    if not tasks:
        raise QuickstartDataError(f"No tasks found in {path.relative_to(ROOT)}")
    return tasks


def _decimal(value: Any, label: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise QuickstartDataError(f"{label} must be a decimal number.") from error
    if not number.is_finite():
        raise QuickstartDataError(f"{label} must be finite.")
    return number


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _percent(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _clean_text(value: Any) -> str:
    return " ".join(str(value).replace("\x00", "").split())


def _markdown(value: Any) -> str:
    return (
        _clean_text(value).replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`")
    )


def _mermaid(value: Any) -> str:
    text = _clean_text(value)
    for character, replacement in {
        '"': "'",
        "[": "(",
        "]": ")",
        "{": "(",
        "}": ")",
        "<": "(",
        ">": ")",
    }.items():
        text = text.replace(character, replacement)
    return text


def _validate_tasks(tasks: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    for index, task in enumerate(tasks, start=1):
        task_id = _clean_text(task.get("task_id", ""))
        if not task_id or task_id in seen_ids:
            raise QuickstartDataError(
                f"Task {index} has a missing or duplicate task_id."
            )
        seen_ids.add(task_id)

        risk = task.get("risk_level")
        route = task.get("selected_route")
        allowed_routes = task.get("allowed_routes")
        if risk not in RISK_LEVELS:
            raise QuickstartDataError(
                f"Task {task_id} has unsupported risk_level: {risk}"
            )
        if route not in ROUTES:
            raise QuickstartDataError(
                f"Task {task_id} has unsupported selected_route: {route}"
            )
        if not isinstance(allowed_routes, list) or not allowed_routes:
            raise QuickstartDataError(f"Task {task_id} must declare allowed_routes.")
        if set(allowed_routes) - ROUTES:
            raise QuickstartDataError(
                f"Task {task_id} declares an unsupported allowed route."
            )
        if route not in allowed_routes:
            raise QuickstartDataError(
                f"Task {task_id} selects a route that is not allowed."
            )
        if risk in {"high", "regulated", "unknown"} and route == "candidate_model":
            raise QuickstartDataError(
                f"Task {task_id} cannot route {risk} work to candidate_model."
            )
        if risk == "regulated" and route != "blocked_or_escalate":
            raise QuickstartDataError(
                f"Regulated task {task_id} must be blocked or escalated."
            )


def _comparison(
    baseline: dict[str, Any], candidate: dict[str, Any], fixture: dict[str, Any]
) -> dict[str, Any]:
    baseline_quality = _decimal(baseline.get("quality_score"), "baseline quality_score")
    candidate_quality = _decimal(
        candidate.get("quality_score"), "candidate quality_score"
    )
    baseline_cost = _decimal(
        baseline.get("estimated_cost_usd"), "baseline estimated_cost_usd"
    )
    candidate_cost = _decimal(
        candidate.get("estimated_cost_usd"), "candidate estimated_cost_usd"
    )
    baseline_latency = _decimal(
        baseline.get("average_latency_seconds"), "baseline average_latency_seconds"
    )
    candidate_latency = _decimal(
        candidate.get("average_latency_seconds"), "candidate average_latency_seconds"
    )
    if baseline_quality <= 0 or baseline_cost <= 0 or baseline_latency <= 0:
        raise QuickstartDataError(
            "Baseline quality, cost, and latency must be greater than zero."
        )
    if candidate_quality < 0 or candidate_cost < 0 or candidate_latency < 0:
        raise QuickstartDataError(
            "Candidate quality, cost, and latency cannot be negative."
        )

    return {
        "baseline": baseline,
        "candidate": candidate,
        "quality_retained_pct": _percent(
            (candidate_quality / baseline_quality) * Decimal("100")
        ),
        "estimated_cost_reduction_pct": _percent(
            ((baseline_cost - candidate_cost) / baseline_cost) * Decimal("100")
        ),
        "latency_change_pct": _percent(
            ((candidate_latency - baseline_latency) / baseline_latency) * Decimal("100")
        ),
        "thresholds": fixture.get("thresholds", {}),
        "decision": _clean_text(
            fixture.get("decision", "Review fixture results before migration.")
        ),
        "recommended_use": _clean_text(
            fixture.get("recommended_use", "Use task-level routing and human review.")
        ),
    }


def _vendor_report(
    tasks: list[dict[str, Any]],
    comparison: dict[str, Any],
    source_digests: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": "linux-of-ai.vendor-exit-report.v1",
        "generated_at": GENERATED_AT,
        "source": {
            "mode": "deterministic-offline-fixture",
            "tasks": "input/tasks.jsonl",
            "comparison": "input/model_comparison_results.json",
            "digests_sha256": source_digests,
        },
        "workload": "fictional-customer-support",
        "task_count": len(tasks),
        "comparison": comparison,
        "conclusion": {
            "decision": comparison["decision"],
            "recommended_use": comparison["recommended_use"],
        },
        "limitations": [
            "This report uses fictional deterministic fixture data, not a live benchmark run.",
            "Estimated cost is not invoice-confirmed.",
            "Projected savings are not realized savings.",
            "This report does not prove that a migration is safe or compliant.",
            "Model behavior can change across versions, providers, prompts, and runtime environments.",
        ],
    }


def _route_plan(
    tasks: list[dict[str, Any]],
    comparison: dict[str, Any],
    source_digests: dict[str, str],
) -> dict[str, Any]:
    counts = {route: 0 for route in sorted(ROUTES)}
    decisions = []
    for task in tasks:
        route = str(task["selected_route"])
        counts[route] += 1
        decisions.append(
            {
                "task_id": task["task_id"],
                "name": task["name"],
                "category": task["category"],
                "risk_level": task["risk_level"],
                "selected_route": route,
                "allowed_routes": task["allowed_routes"],
                "human_review_required": bool(task.get("human_review_required", False)),
                "escalation": task.get("escalation"),
                "reason": task["route_reason"],
            }
        )
    return {
        "schema_version": "linux-of-ai.model-routing-plan.v1",
        "generated_at": GENERATED_AT,
        "workload": "fictional-customer-support",
        "baseline_model": f"{comparison['baseline']['provider']}:{comparison['baseline']['model']}",
        "candidate_model": f"{comparison['candidate']['provider']}:{comparison['candidate']['model']}",
        "source_digests_sha256": source_digests,
        "summary": {"total_tasks": len(tasks), "routes": counts},
        "task_decisions": decisions,
        "recommendation": comparison["recommended_use"],
        "limitations": [
            "Routes are deterministic fixture decisions, not live policy enforcement.",
            "Human review remains necessary where declared.",
            "Blocked or escalated work requires a qualified downstream process.",
            "This plan does not prove legal, regulatory, safety, security, or compliance status.",
        ],
    }


def _aimeter_summary(report: dict[str, Any]) -> dict[str, Any]:
    comparison = report["comparison"]
    return {
        "schema_version": "linux-of-ai.aimeter-style-summary.v1",
        "generated_at": GENERATED_AT,
        "integration_mode": "offline-file-pattern",
        "workload": report["workload"],
        "quality": {"quality_retained_pct": comparison["quality_retained_pct"]},
        "cost": {
            "baseline_estimated_cost": {
                "amount": comparison["baseline"]["estimated_cost_usd"],
                "currency": "USD",
                "invoice_confirmed": False,
            },
            "candidate_estimated_cost": {
                "amount": comparison["candidate"]["estimated_cost_usd"],
                "currency": "USD",
                "invoice_confirmed": False,
            },
            "estimated_cost_reduction_pct": comparison["estimated_cost_reduction_pct"],
            "projected_savings_realized": False,
        },
        "outcome": report["conclusion"],
        "limitations": [
            "This is an AIMeter OSS-style file pattern, not a live AIMeter integration.",
            "Estimated cost is not invoice-confirmed.",
            "Projected savings are not realized savings.",
            "Missing cost must remain unknown and must never be treated as zero.",
        ],
    }


def _route_aimeter_summary(
    plan: dict[str, Any], comparison: dict[str, Any]
) -> dict[str, Any]:
    task_count = Decimal(plan["summary"]["total_tasks"])
    baseline_per_task = (
        _decimal(comparison["baseline"]["estimated_cost_usd"], "baseline cost")
        / task_count
    )
    candidate_per_task = (
        _decimal(comparison["candidate"]["estimated_cost_usd"], "candidate cost")
        / task_count
    )
    counts = plan["summary"]["routes"]
    known_cost = candidate_per_task * Decimal(
        counts["candidate_model"]
    ) + baseline_per_task * Decimal(counts["baseline_model"])
    missing_count = counts["human_review"] + counts["blocked_or_escalate"]
    return {
        "schema_version": "linux-of-ai.route-aimeter-style-summary.v1",
        "generated_at": GENERATED_AT,
        "integration_mode": "offline-file-pattern",
        "routes": counts,
        "cost": {
            "known_estimated_model_cost_usd": _money(known_cost),
            "complete_estimated_cost_usd": None
            if missing_count
            else _money(known_cost),
            "missing_cost_task_count": missing_count,
            "missing_cost_is_zero": False,
            "human_review_cost_usd": None,
            "blocked_or_escalated_cost_usd": None,
            "currency": "USD",
            "invoice_confirmed": False,
        },
        "outcome": {"recommendation": plan["recommendation"]},
        "limitations": [
            "This is an AIMeter OSS-style file pattern, not a live AIMeter integration.",
            "The known estimate excludes unknown human-review and escalation costs.",
            "Missing cost is unknown, not zero.",
            "Projected savings are not realized savings.",
        ],
    }


def _chain_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous_hash: str | None = None
    chained = []
    for event in events:
        payload = dict(event)
        payload["previous_hash"] = previous_hash
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        chained.append(payload)
        previous_hash = payload["event_hash"]
    return chained


def _audit_events(report: dict[str, Any]) -> list[dict[str, Any]]:
    return _chain_events(
        [
            {
                "event_id": "vendor-exit-0001",
                "event_type": "fixture_inputs_loaded",
                "timestamp": "2026-01-01T00:00:00Z",
                "actor": "quickstart-runner",
                "summary": "Loaded deterministic offline comparison fixtures.",
            },
            {
                "event_id": "vendor-exit-0002",
                "event_type": "comparison_evaluated",
                "timestamp": "2026-01-01T00:00:01Z",
                "actor": "quickstart-runner",
                "quality_retained_pct": report["comparison"]["quality_retained_pct"],
                "estimated_cost_reduction_pct": report["comparison"][
                    "estimated_cost_reduction_pct"
                ],
                "summary": "Calculated deterministic quality, latency, and estimated cost signals.",
            },
            {
                "event_id": "vendor-exit-0003",
                "event_type": "vendor_exit_report_generated",
                "timestamp": "2026-01-01T00:00:02Z",
                "actor": "quickstart-runner",
                "summary": report["conclusion"]["decision"],
            },
        ]
    )


def _route_audit_events(plan: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {
            "event_id": "route-0001",
            "event_type": "routing_started",
            "timestamp": "2026-01-01T00:00:10Z",
            "actor": "quickstart-runner",
            "summary": "Started deterministic task-level routing.",
        }
    ]
    for index, decision in enumerate(plan["task_decisions"], start=2):
        events.append(
            {
                "event_id": f"route-{index:04d}",
                "event_type": "task_route_decision_recorded",
                "timestamp": "2026-01-01T00:00:11Z",
                "actor": "quickstart-runner",
                "task_id": decision["task_id"],
                "risk_level": decision["risk_level"],
                "selected_route": decision["selected_route"],
                "summary": decision["reason"],
            }
        )
    events.append(
        {
            "event_id": f"route-{len(events) + 1:04d}",
            "event_type": "routing_plan_generated",
            "timestamp": "2026-01-01T00:00:12Z",
            "actor": "quickstart-runner",
            "summary": "Generated the deterministic Model Routing Plan.",
        }
    )
    return _chain_events(events)


def _render_vendor_report(report: dict[str, Any]) -> str:
    comparison = report["comparison"]
    return "\n".join(
        [
            "# AI Vendor Exit Report",
            "",
            "## Executive Summary",
            "",
            _markdown(report["conclusion"]["decision"]),
            "",
            f"- Recommended use: {_markdown(report['conclusion']['recommended_use'])}",
            f"- Fictional tasks evaluated: {report['task_count']}",
            "",
            "## Model Comparison",
            "",
            "| Signal | Baseline | Candidate |",
            "|---|---:|---:|",
            f"| Quality score | {comparison['baseline']['quality_score']} | {comparison['candidate']['quality_score']} |",
            f"| Average latency (seconds) | {comparison['baseline']['average_latency_seconds']} | {comparison['candidate']['average_latency_seconds']} |",
            f"| Estimated cost (USD) | {comparison['baseline']['estimated_cost_usd']} | {comparison['candidate']['estimated_cost_usd']} |",
            "",
            "## Derived Signals",
            "",
            f"- Quality retained: {comparison['quality_retained_pct']}%",
            f"- Estimated cost reduction: {comparison['estimated_cost_reduction_pct']}%",
            f"- Latency change: {comparison['latency_change_pct']}%",
            "",
            "## Limitations",
            "",
            *[f"- {_markdown(item)}" for item in report["limitations"]],
            "",
            "## Reproducibility",
            "",
            "- Generated from deterministic files under `input/`.",
            "- No hosted model, external API, secret, or network access was used.",
            "",
        ]
    )


def _render_route_plan(plan: dict[str, Any]) -> str:
    lines = [
        "# Model Routing Plan",
        "",
        "## Summary",
        "",
        _markdown(plan["recommendation"]),
        "",
        "| Route | Task count |",
        "|---|---:|",
    ]
    for route, count in plan["summary"]["routes"].items():
        lines.append(f"| `{route}` | {count} |")
    lines.extend(
        [
            "",
            "## Task Decisions",
            "",
            "| Task | Risk | Selected route | Human review | Reason |",
            "|---|---|---|---|---|",
        ]
    )
    for decision in plan["task_decisions"]:
        lines.append(
            f"| {_markdown(decision['name'])} | {decision['risk_level']} | "
            f"`{decision['selected_route']}` | "
            f"{'required' if decision['human_review_required'] else 'not declared'} | "
            f"{_markdown(decision['reason'])} |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            *[f"- {_markdown(item)}" for item in plan["limitations"]],
            "",
        ]
    )
    return "\n".join(lines)


def _render_system_map(
    tasks: list[dict[str, Any]], plan: dict[str, Any], source_digests: dict[str, str]
) -> str:
    lines = [
        "# AI System Map Report",
        "",
        "## System",
        "",
        "- Name: Fictional Customer Support Vendor Exit",
        "- Environment: deterministic-offline-quickstart",
        "- Source map: `ontology/ai_system_map.yaml`",
        f"- Source map SHA-256: `{source_digests['ontology/ai_system_map.yaml']}`",
        f"- Policy SHA-256: `{source_digests['policies/support_policy.yaml']}`",
        "- Purpose: preserve workload, routing, review, audit, and measurement meaning during migration planning.",
        "",
        "## Task and Route Controls",
        "",
        "| Task | Category | Risk | Allowed routes | Selected route | Review or escalation |",
        "|---|---|---|---|---|---|",
    ]
    decisions = {decision["task_id"]: decision for decision in plan["task_decisions"]}
    for task in tasks:
        decision = decisions[task["task_id"]]
        control = decision["escalation"] or (
            "human_review" if decision["human_review_required"] else "not declared"
        )
        lines.append(
            f"| {_markdown(task['name'])} | {_markdown(task['category'])} | {task['risk_level']} | "
            f"{', '.join(f'`{route}`' for route in task['allowed_routes'])} | "
            f"`{decision['selected_route']}` | {_markdown(control)} |"
        )
    lines.extend(
        [
            "",
            "## Audit and Cost Expectations",
            "",
            "- Route decisions produce AIAuditLog-style, hash-chained JSONL evidence.",
            "- Cost and outcome signals use AIMeter OSS-style JSON files.",
            "- Hash chaining is a tamper-evident pattern; it is not immutability or legal non-repudiation.",
            "- Estimated cost is not invoice-confirmed, and missing cost is never treated as zero.",
            "",
            "## Limitations",
            "",
            "- This map is documentation and validation support, not compliance certification.",
            "- It does not prove a workflow is safe or automatically enforce policy.",
            "- It does not guarantee model behavior or replace qualified human review.",
            "- Ecosystem mappings are portable file patterns, not verified live integrations.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_mermaid(tasks: list[dict[str, Any]]) -> str:
    lines = [
        "flowchart TD",
        '  system["AI System: Fictional Customer Support Vendor Exit"]',
        '  audit[["Audit events"]]',
        '  cost[["Cost/outcome metrics"]]',
    ]
    route_ids = {
        "candidate_model": "route_candidate",
        "baseline_model": "route_baseline",
        "human_review": "route_human",
        "blocked_or_escalate": "route_blocked",
    }
    for route, node_id in route_ids.items():
        lines.append(f'  {node_id}(["Route: {route}"])')
    for index, task in enumerate(tasks, start=1):
        task_id = f"task_{index:02d}"
        lines.append(
            f'  {task_id}["Task: {_mermaid(task["name"])}<br/>Risk: {task["risk_level"]}"]'
        )
        lines.append(f"  system --> {task_id}")
        lines.append(f"  {task_id} -->|selected| {route_ids[task['selected_route']]}")
        lines.append(f"  {task_id} -.->|records| audit")
        lines.append(f"  {task_id} -.->|measures| cost")
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    content = "".join(
        json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        for event in events
    )
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def run() -> list[Path]:
    tasks = _read_jsonl(INPUT_DIR / "tasks.jsonl")
    _validate_tasks(tasks)
    baseline = _read_json(INPUT_DIR / "baseline_results.json")
    candidate = _read_json(INPUT_DIR / "candidate_results.json")
    comparison_fixture = _read_json(INPUT_DIR / "model_comparison_results.json")
    for label, payload in (("baseline", baseline), ("candidate", candidate)):
        if payload.get("task_count") != len(tasks):
            raise QuickstartDataError(
                f"{label} task_count must match the {len(tasks)} tasks in input/tasks.jsonl."
            )

    source_text = {
        "ontology/ai_system_map.yaml": _read_text(
            ROOT / "ontology" / "ai_system_map.yaml"
        ),
        "policies/support_policy.yaml": _read_text(
            ROOT / "policies" / "support_policy.yaml"
        ),
    }
    source_digests = {
        name: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for name, content in source_text.items()
    }

    comparison = _comparison(baseline, candidate, comparison_fixture)
    report = _vendor_report(tasks, comparison, source_digests)
    plan = _route_plan(tasks, comparison, source_digests)

    for directory in (REPORTS_DIR, AUDIT_DIR, OUTPUTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    outputs = [
        REPORTS_DIR / "ai_vendor_exit_report.md",
        REPORTS_DIR / "ai_vendor_exit_report.json",
        REPORTS_DIR / "model_routing_plan.md",
        REPORTS_DIR / "model_routing_plan.json",
        REPORTS_DIR / "aimeter_summary.json",
        REPORTS_DIR / "route_aimeter_summary.json",
        AUDIT_DIR / "audit_events.jsonl",
        AUDIT_DIR / "route_audit_events.jsonl",
        OUTPUTS_DIR / "ai_system_map_report.md",
        OUTPUTS_DIR / "ai_system_map.mmd",
    ]
    _write_text(outputs[0], _render_vendor_report(report))
    _write_json(outputs[1], report)
    _write_text(outputs[2], _render_route_plan(plan))
    _write_json(outputs[3], plan)
    _write_json(outputs[4], _aimeter_summary(report))
    _write_json(outputs[5], _route_aimeter_summary(plan, comparison))
    _write_jsonl(outputs[6], _audit_events(report))
    _write_jsonl(outputs[7], _route_audit_events(plan))
    _write_text(outputs[8], _render_system_map(tasks, plan, source_digests))
    _write_text(outputs[9], _render_mermaid(tasks))
    return outputs


def main() -> int:
    try:
        outputs = run()
    except (OSError, QuickstartDataError, json.JSONDecodeError) as error:
        print(f"Quickstart failed: {error}", file=sys.stderr)
        return 1
    print("Linux of AI Vendor Exit Quickstart complete.")
    print("Generated outputs:")
    for path in outputs:
        print(f"- {path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
