#!/usr/bin/env python3
"""Generate the offline Linux of AI Vendor Exit Demo outputs."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
AUDIT_DIR = ROOT / "audit"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def money(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def percent(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def write_json(path: Path, payload: dict | list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def comparison_payload(baseline: dict, candidate: dict) -> dict:
    baseline_cost = money(baseline["estimated_cost_usd"])
    candidate_cost = money(candidate["estimated_cost_usd"])
    baseline_quality = Decimal(baseline["quality_score"])
    candidate_quality = Decimal(candidate["quality_score"])
    baseline_latency = Decimal(baseline["average_latency_seconds"])
    candidate_latency = Decimal(candidate["average_latency_seconds"])

    cost_reduction = ((baseline_cost - candidate_cost) / baseline_cost) * Decimal("100")
    quality_retained = (candidate_quality / baseline_quality) * Decimal("100")
    latency_change = ((candidate_latency - baseline_latency) / baseline_latency) * Decimal("100")

    return {
        "label": "deterministic example data",
        "baseline": {
            "provider": baseline["provider"],
            "model": baseline["model"],
            "quality_score": baseline["quality_score"],
            "average_latency_seconds": baseline["average_latency_seconds"],
            "estimated_cost_usd": str(baseline_cost),
        },
        "candidate": {
            "provider": candidate["provider"],
            "model": candidate["model"],
            "quality_score": candidate["quality_score"],
            "average_latency_seconds": candidate["average_latency_seconds"],
            "estimated_cost_usd": str(candidate_cost),
        },
        "estimated_cost_reduction_percent": percent(cost_reduction),
        "quality_retained_percent": percent(quality_retained),
        "latency_change_percent": percent(latency_change),
        "decision": "Candidate acceptable with human review",
        "recommended_use": "low-risk internal support workflows",
        "excluded_use": (
            "high-risk legal, medical, financial, security-sensitive, or "
            "external-facing use without additional evaluation"
        ),
        "notes": (
            "This file represents ModelSwapBench-style output for an offline "
            "integration-pattern demo."
        ),
    }


def report_payload(tickets: list[dict], comparison: dict) -> dict:
    risk_counts: dict[str, int] = {}
    escalation_categories: list[str] = []
    for ticket in tickets:
        risk_counts[ticket["risk_level"]] = risk_counts.get(ticket["risk_level"], 0) + 1
        if ticket["risk_level"] == "high":
            escalation_categories.append(ticket["category"])

    return {
        "demo": "Linux of AI Vendor Exit Demo",
        "generated_at": "2026-01-01T00:00:00Z",
        "offline_first": True,
        "deterministic": True,
        "scenario": (
            "A fictional company evaluates whether a lower-cost local/open "
            "model can replace an expensive hosted model for low-risk internal "
            "customer-support drafting."
        ),
        "comparison": comparison,
        "risk_counts": risk_counts,
        "escalation_categories": sorted(set(escalation_categories)),
        "conclusion": {
            "decision": comparison["decision"],
            "recommended_use": comparison["recommended_use"],
            "do_not_use_for": comparison["excluded_use"],
            "compliance_boundary": (
                "Do not use as proof of legal, regulatory, safety, or security compliance."
            ),
        },
    }


def render_report(report: dict) -> str:
    comparison = report["comparison"]
    return f"""# AI Vendor Exit Report

Demo: Linux of AI Vendor Exit Demo

Generated: {report["generated_at"]}

This is deterministic example data for an offline integration-pattern demo. No OpenAI, Anthropic, Google, Hugging Face, or other hosted provider API was called.

## Scenario

{report["scenario"]}

## Model Comparison

| Measure | Baseline | Candidate |
|---|---:|---:|
| Provider | {comparison["baseline"]["provider"]} | {comparison["candidate"]["provider"]} |
| Model | {comparison["baseline"]["model"]} | {comparison["candidate"]["model"]} |
| Quality score | {comparison["baseline"]["quality_score"]} | {comparison["candidate"]["quality_score"]} |
| Average latency | {comparison["baseline"]["average_latency_seconds"]} seconds | {comparison["candidate"]["average_latency_seconds"]} seconds |
| Estimated cost | ${comparison["baseline"]["estimated_cost_usd"]} | ${comparison["candidate"]["estimated_cost_usd"]} |

Estimated cost reduction: {comparison["estimated_cost_reduction_percent"]}%

Quality retained: {comparison["quality_retained_percent"]}%

Decision: {comparison["decision"]}

Recommended use: {comparison["recommended_use"]}

## Governance Result

The candidate is acceptable only for low-risk internal support workflows with human review. High-risk legal, medical, financial, security-sensitive, or external-facing use requires additional evaluation and escalation.

## Ecosystem Evidence

- OpenOntologyLite defines Customer, SupportTicket, RiskLevel, Response, and Escalation.
- AgentPolicyPack defines when candidate output is allowed, reviewed, or escalated.
- ModelSwapBench is represented by the deterministic comparison and this AI Vendor Exit Report.
- AIAuditLog-style events record benchmark, decision, and recommendation evidence.
- AIMeter OSS-style data summarizes estimated cost, quality retained, and outcome boundaries.
- AgentForge could orchestrate this workflow in a live system.
- PrivateAIStack could host the local/private candidate model path in a controlled deployment.

## Important Boundaries

- This demo uses compatible files and reports, not deep runtime integration between all packages.
- Hash chaining is tamper-evident, not immutable.
- Signatures do not prove real-world identity.
- This report does not create legal non-repudiation or automatic compliance.
- Calculated cost is not invoice-confirmed cost.
- Projected savings are not realized savings.
- API success is not automatically business success.
- Budgets are evaluated, not automatically enforced.

Do not use as proof of legal, regulatory, safety, or security compliance.
"""


def render_cost_summary(report: dict) -> str:
    comparison = report["comparison"]
    return f"""# Cost and Outcome Summary

This AIMeter OSS-style summary uses Decimal-based calculations in `scripts/run_demo.py`.

| Measure | Value |
|---|---:|
| Baseline estimated cost | ${comparison["baseline"]["estimated_cost_usd"]} |
| Candidate estimated cost | ${comparison["candidate"]["estimated_cost_usd"]} |
| Estimated cost reduction | {comparison["estimated_cost_reduction_percent"]}% |
| Baseline quality score | {comparison["baseline"]["quality_score"]} |
| Candidate quality score | {comparison["candidate"]["quality_score"]} |
| Quality retained | {comparison["quality_retained_percent"]}% |
| Candidate latency change | {comparison["latency_change_percent"]}% |

Decision: {comparison["decision"]}

Recommended use: {comparison["recommended_use"]}

Boundaries:

- Missing pricing is never zero.
- Calculated cost is not invoice-confirmed.
- Projected savings are not realized savings.
- API success is not automatically business success.
- Budgets are evaluated, not automatically enforced.
"""


def aimeter_summary(report: dict) -> dict:
    comparison = report["comparison"]
    return {
        "schema_version": "linux-of-ai.aimeter-export.v1",
        "generated_at": report["generated_at"],
        "source": {
            "service": "linux-of-ai-vendor-exit-demo",
            "component": "run_demo.py",
            "export_type": "aimeter-oss-style-cost-outcome-summary",
            "integration_mode": "offline-file-export",
        },
        "workload": "customer-support-drafting",
        "baseline": {
            "provider": comparison["baseline"]["provider"],
            "model": comparison["baseline"]["model"],
            "quality_score": comparison["baseline"]["quality_score"],
        },
        "candidate": {
            "provider": comparison["candidate"]["provider"],
            "model": comparison["candidate"]["model"],
            "quality_score": comparison["candidate"]["quality_score"],
        },
        "quality": {
            "quality_retention_pct": comparison["quality_retained_percent"],
        },
        "cost": {
            "baseline_estimated_cost": {
                "amount": comparison["baseline"]["estimated_cost_usd"],
                "currency": "USD",
                "basis": "estimated",
                "invoice_confirmed": False,
            },
            "candidate_estimated_cost": {
                "amount": comparison["candidate"]["estimated_cost_usd"],
                "currency": "USD",
                "basis": "estimated",
                "invoice_confirmed": False,
            },
            "estimated_cost_reduction_pct": comparison["estimated_cost_reduction_percent"],
            "projected_savings_realized": False,
        },
        "latency": {
            "latency_delta_pct": comparison["latency_change_percent"],
        },
        "outcome": {
            "decision": comparison["decision"],
            "recommendation": comparison["recommended_use"],
        },
        "limitations": [
            "This is an AIMeter OSS-style portable export, not a live AIMeter runtime integration.",
            "Estimated cost is not invoice-confirmed.",
            "Projected savings are not realized savings.",
            "Missing pricing must remain unknown and must not be treated as zero.",
        ],
    }


def route_plan_payload(tickets: list[dict], comparison: dict) -> dict:
    route_rules = {
        "password_reset": ("candidate_model", "Low-risk password reset guidance can move to the candidate model."),
        "billing_question": ("human_review", "Billing workflows are customer-facing and should keep review."),
        "account_cancellation": ("human_review", "Account changes should keep review before customer action."),
        "refund_request": ("human_review", "Refund requests require policy-aware review."),
        "security_concern": ("blocked_or_escalate", "Suspicious login activity requires escalation to the security process."),
        "legal_medical_financial": ("blocked_or_escalate", "Legal, medical, or financial questions require escalation."),
        "angry_customer": ("human_review", "Angry customer escalation requires human review before response."),
    }
    decisions = []
    counts = {
        "candidate_model": 0,
        "baseline_model": 0,
        "human_review": 0,
        "blocked_or_escalate": 0,
    }
    for ticket in tickets:
        route, reason = route_rules.get(ticket["category"], ("baseline_model", "Unmapped category remains on the baseline model."))
        if ticket["risk_level"] == "high" and route == "candidate_model":
            route = "human_review"
            reason = "High-risk tasks are not routed directly to the candidate model."
        counts[route] += 1
        decisions.append(
            {
                "task_id": ticket["ticket_id"],
                "category": ticket["category"],
                "route": route,
                "risk_level": ticket["risk_level"],
                "quality_signal": "fixture-level comparison only",
                "cost_signal": "estimated",
                "latency_signal": "estimated",
                "policy_notes": ticket.get("policy_flags", []),
                "reason": reason,
            }
        )

    total = Decimal(len(decisions))
    baseline_cost = money(comparison["baseline"]["estimated_cost_usd"])
    candidate_cost = money(comparison["candidate"]["estimated_cost_usd"])
    candidate_share = Decimal(counts["candidate_model"]) / total
    routed_cost = (candidate_cost * candidate_share) + (baseline_cost * (Decimal("1") - candidate_share))
    savings = ((baseline_cost - routed_cost) / baseline_cost) * Decimal("100")

    return {
        "schema_version": "linux-of-ai.model-routing-plan.v1",
        "generated_at": "2026-01-01T00:00:00Z",
        "workload": "customer-support-drafting",
        "baseline_model": f'{comparison["baseline"]["provider"]}:{comparison["baseline"]["model"]}',
        "candidate_model": f'{comparison["candidate"]["provider"]}:{comparison["candidate"]["model"]}',
        "summary": {
            "total_tasks": len(decisions),
            "routes": counts,
            "candidate_model_pct": percent((Decimal(counts["candidate_model"]) / total) * Decimal("100")),
            "baseline_model_pct": percent((Decimal(counts["baseline_model"]) / total) * Decimal("100")),
            "human_review_pct": percent((Decimal(counts["human_review"]) / total) * Decimal("100")),
            "blocked_or_escalate_pct": percent((Decimal(counts["blocked_or_escalate"]) / total) * Decimal("100")),
            "baseline_total_estimated_cost": str(baseline_cost),
            "routed_blended_estimated_cost": str(routed_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "estimated_blended_savings_pct": percent(savings),
        },
        "task_decisions": decisions,
        "recommendation": (
            "Move low-risk candidate-routed tasks first, keep human review for "
            "sensitive tasks, and escalate blocked legal, medical, or financial tasks."
        ),
        "limitations": [
            "This route plan is deterministic fixture output, not a live ModelSwapBench run.",
            "The integration pattern is offline-first and file-based.",
            "Estimated cost is not invoice-confirmed.",
            "Projected savings are not realized savings.",
            "Route decisions are not legal, regulatory, safety, security, or compliance guarantees.",
            "Human review may be required.",
        ],
    }


def render_route_plan(plan: dict) -> str:
    summary = plan["summary"]
    lines = [
        "# Model Routing Plan",
        "",
        "## Executive Summary",
        "",
        plan["recommendation"],
        "",
        "## Models Compared",
        "",
        f'- Baseline model/provider: `{plan["baseline_model"]}`',
        f'- Candidate model/provider: `{plan["candidate_model"]}`',
        "",
        "## Workload",
        "",
        f'- Workload name: {plan["workload"]}',
        f'- Task count: {summary["total_tasks"]}',
        "",
        "## Routing Summary",
        "",
        f'- Candidate model: {summary["candidate_model_pct"]}% of tasks',
        f'- Baseline model: {summary["baseline_model_pct"]}% of tasks',
        f'- Human review: {summary["human_review_pct"]}% of tasks',
        f'- Blocked/escalate: {summary["blocked_or_escalate_pct"]}% of tasks',
        f'- Estimated blended savings: {summary["estimated_blended_savings_pct"]}%',
        "",
        "## Task Routing Table",
        "",
        "| Task | Category | Route | Risk | Reason |",
        "|---|---|---|---|---|",
    ]
    for decision in plan["task_decisions"]:
        lines.append(
            f'| {decision["task_id"]} | {decision["category"]} | `{decision["route"]}` | '
            f'{decision["risk_level"]} | {decision["reason"]} |'
        )
    lines.extend(
        [
            "",
            "## Estimated Blended Cost Impact",
            "",
            f'- Baseline total estimated cost: ${summary["baseline_total_estimated_cost"]}',
            f'- Routed/blended estimated cost: ${summary["routed_blended_estimated_cost"]}',
            f'- Estimated savings vs baseline: {summary["estimated_blended_savings_pct"]}%',
            "- Estimated cost is not invoice-confirmed.",
            "- Projected savings are not realized savings.",
            "",
            "## Risk and Human Review",
            "",
            "- Human review remains required for sensitive or borderline tasks.",
            "- Legal, medical, and financial tasks are blocked or escalated in this fixture.",
            "",
            "## Recommendation",
            "",
            plan["recommendation"],
            "",
            "## Limitations",
            "",
            *[f"- {limitation}" for limitation in plan["limitations"]],
            "",
            "## Reproducibility",
            "",
            "- Generated by `scripts/run_demo.py`.",
            "- No hosted provider API was called.",
            "",
        ]
    )
    return "\n".join(lines)


def route_aimeter_summary(plan: dict) -> dict:
    return {
        "schema_version": "linux-of-ai.route-plan.aimeter-export.v1",
        "generated_at": plan["generated_at"],
        "source": {
            "service": "linux-of-ai-vendor-exit-demo",
            "component": "run_demo.py",
            "export_type": "aimeter-oss-style-route-cost-outcome-summary",
            "integration_mode": "offline-file-export",
        },
        "workload": plan["workload"],
        "baseline_model": plan["baseline_model"],
        "candidate_model": plan["candidate_model"],
        "cost": {
            "baseline_total_estimated_cost": {
                "amount": plan["summary"]["baseline_total_estimated_cost"],
                "currency": "USD",
                "basis": "estimated",
                "invoice_confirmed": False,
            },
            "routed_blended_estimated_cost": {
                "amount": plan["summary"]["routed_blended_estimated_cost"],
                "currency": "USD",
                "basis": "estimated",
                "invoice_confirmed": False,
            },
            "estimated_savings_vs_baseline_pct": plan["summary"]["estimated_blended_savings_pct"],
            "projected_savings_realized": False,
        },
        "routes": plan["summary"]["routes"],
        "outcome": {
            "recommendation": plan["recommendation"],
        },
        "limitations": plan["limitations"]
        + ["This is an AIMeter OSS-style portable export, not a live AIMeter runtime integration."],
    }


def audit_events(report: dict) -> list[dict]:
    base_events = [
        {
            "event_id": "audit-0001",
            "event_type": "vendor_exit_report_started",
            "actor": "vendor-exit-demo",
            "run_id": "vendor-exit-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:00Z",
            "summary": "Started deterministic vendor-exit demo report generation.",
        },
        {
            "event_id": "audit-0002",
            "event_type": "model_comparison_loaded",
            "actor": "vendor-exit-demo",
            "run_id": "vendor-exit-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:01Z",
            "summary": "Loaded deterministic baseline and candidate comparison fixtures.",
        },
        {
            "event_id": "audit-0003",
            "event_type": "thresholds_evaluated",
            "actor": "vendor-exit-demo",
            "run_id": "vendor-exit-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:02Z",
            "summary": "Evaluated quality, cost, latency, and workflow boundaries.",
            "estimated_cost_reduction_percent": report["comparison"]["estimated_cost_reduction_percent"],
            "quality_retained_percent": report["comparison"]["quality_retained_percent"],
        },
        {
            "event_id": "audit-0004",
            "event_type": "vendor_exit_decision_recorded",
            "actor": "vendor-exit-demo",
            "run_id": "vendor-exit-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:03Z",
            "summary": report["conclusion"]["decision"],
            "recommended_use": report["conclusion"]["recommended_use"],
        },
        {
            "event_id": "audit-0005",
            "event_type": "report_generated",
            "actor": "vendor-exit-demo",
            "run_id": "vendor-exit-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:04Z",
            "summary": "Generated AI Vendor Exit Report Markdown and JSON.",
        },
        {
            "event_id": "audit-0006",
            "event_type": "aimeter_export_generated",
            "actor": "vendor-exit-demo",
            "run_id": "vendor-exit-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:05Z",
            "summary": "Generated AIMeter OSS-style cost/outcome export JSON.",
        },
    ]

    previous_hash = None
    chained_events = []
    for event in base_events:
        event = dict(event)
        event["previous_hash"] = previous_hash
        canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
        event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        event["event_hash"] = event_hash
        chained_events.append(event)
        previous_hash = event_hash
    return chained_events


def route_audit_events(plan: dict) -> list[dict]:
    base_events = [
        {
            "event_id": "route-audit-0001",
            "event_type": "route_plan_started",
            "actor": "vendor-exit-demo",
            "run_id": "route-plan-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:10Z",
            "summary": "Started deterministic model routing plan generation.",
        },
        {
            "event_id": "route-audit-0002",
            "event_type": "route_plan_input_loaded",
            "actor": "vendor-exit-demo",
            "run_id": "route-plan-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:11Z",
            "summary": "Loaded deterministic ticket fixtures and comparison data.",
        },
        {
            "event_id": "route-audit-0003",
            "event_type": "routing_thresholds_evaluated",
            "actor": "vendor-exit-demo",
            "run_id": "route-plan-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:12Z",
            "summary": "Evaluated routing boundaries for candidate, baseline, review, and escalation.",
        },
    ]
    for index, decision in enumerate(plan["task_decisions"], start=4):
        base_events.append(
            {
                "event_id": f"route-audit-{index:04d}",
                "event_type": "task_route_decision_recorded",
                "actor": "vendor-exit-demo",
                "run_id": "route-plan-demo-2026-01-01",
                "system_id": "linux-of-ai-vendor-exit-demo",
                "timestamp": "2026-01-01T00:00:13Z",
                "task_id": decision["task_id"],
                "route": decision["route"],
                "summary": decision["reason"],
            }
        )
    base_events.append(
        {
            "event_id": f"route-audit-{len(base_events) + 1:04d}",
            "event_type": "route_plan_generated",
            "actor": "vendor-exit-demo",
            "run_id": "route-plan-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:14Z",
            "summary": "Generated Model Routing Plan Markdown and JSON.",
        }
    )
    base_events.append(
        {
            "event_id": f"route-audit-{len(base_events) + 1:04d}",
            "event_type": "aimeter_route_export_generated",
            "actor": "vendor-exit-demo",
            "run_id": "route-plan-demo-2026-01-01",
            "system_id": "linux-of-ai-vendor-exit-demo",
            "timestamp": "2026-01-01T00:00:15Z",
            "summary": "Generated AIMeter OSS-style route cost/outcome export JSON.",
        }
    )

    previous_hash = None
    chained_events = []
    for event in base_events:
        event = dict(event)
        event["previous_hash"] = previous_hash
        canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
        event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        event["event_hash"] = event_hash
        chained_events.append(event)
        previous_hash = event_hash
    return chained_events


def main() -> int:
    baseline = read_json(DATA_DIR / "baseline_results.json")
    candidate = read_json(DATA_DIR / "candidate_results.json")
    tickets = read_jsonl(DATA_DIR / "customer_support_tickets.jsonl")

    comparison = comparison_payload(baseline, candidate)
    report = report_payload(tickets, comparison)
    route_plan = route_plan_payload(tickets, comparison)
    events = audit_events(report)
    route_events = route_audit_events(route_plan)

    write_json(DATA_DIR / "model_comparison_results.json", comparison)
    write_json(REPORTS_DIR / "ai_vendor_exit_report.json", report)
    write_json(REPORTS_DIR / "aimeter_summary.json", aimeter_summary(report))
    write_json(REPORTS_DIR / "model_routing_plan.json", route_plan)
    write_json(REPORTS_DIR / "route_aimeter_summary.json", route_aimeter_summary(route_plan))
    write_text(REPORTS_DIR / "ai_vendor_exit_report.md", render_report(report))
    write_text(REPORTS_DIR / "model_routing_plan.md", render_route_plan(route_plan))
    write_text(REPORTS_DIR / "cost_outcome_summary.md", render_cost_summary(report))
    audit_jsonl = "".join(json.dumps(event, sort_keys=True) + "\n" for event in events)
    route_audit_jsonl = "".join(json.dumps(event, sort_keys=True) + "\n" for event in route_events)
    write_text(AUDIT_DIR / "audit_events.jsonl", audit_jsonl)
    write_text(AUDIT_DIR / "ai_audit_events.jsonl", audit_jsonl)
    write_text(AUDIT_DIR / "route_audit_events.jsonl", route_audit_jsonl)

    generated = [
        DATA_DIR / "model_comparison_results.json",
        REPORTS_DIR / "ai_vendor_exit_report.md",
        REPORTS_DIR / "ai_vendor_exit_report.json",
        REPORTS_DIR / "model_routing_plan.md",
        REPORTS_DIR / "model_routing_plan.json",
        REPORTS_DIR / "aimeter_summary.json",
        REPORTS_DIR / "route_aimeter_summary.json",
        REPORTS_DIR / "cost_outcome_summary.md",
        AUDIT_DIR / "audit_events.jsonl",
        AUDIT_DIR / "ai_audit_events.jsonl",
        AUDIT_DIR / "route_audit_events.jsonl",
    ]

    print("Linux of AI Vendor Exit Demo complete")
    print("Generated files:")
    for path in generated:
        print(f"- {path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
