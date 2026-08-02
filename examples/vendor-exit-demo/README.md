# Linux of AI Vendor Exit Demo

This is a deterministic, offline-first integration-pattern demo for the Linux of AI ecosystem. It uses portable files and generated reports to show how a team could evaluate leaving an expensive or locked-in AI provider without making live provider calls.

## What this demo shows

The demo walks through a fictional customer-support workflow where a company compares an expensive hosted model against a lower-cost local/open candidate model. This demo uses a portable AI System Map to document the meaning and risk rules behind the route-plan workflow. It shows how ontology, policy, benchmark output, audit evidence, and cost/outcome measurement can support a practical vendor-exit decision.

This demo uses the same portable export pattern supported by ModelSwapBench's
AI Vendor Exit Report and Model Routing Plan:

- AIMeter OSS-style export for cost/outcome measurement.
- AIAuditLog-style export for audit evidence.

The pattern is deterministic, offline-first, and file-based. It does not claim
deep runtime integration across the packages.

## Why vendor exit matters

Vendor exit matters because AI systems often become coupled to one provider's API, pricing, model behavior, logging, and governance assumptions. A team needs a repeatable way to ask whether a replacement model is good enough for a specific workflow, what risks remain, what evidence was recorded, and what costs are estimated to change.

## Scenario

A fictional company uses a hosted AI model to draft customer-support ticket responses. The company wants to know whether a lower-cost local/open model can replace the current model for low-risk internal support workflows.

The conclusion in this fixture is intentionally narrow: the candidate is acceptable with human review for low-risk internal support workflows. It is not recommended for high-risk legal, medical, financial, security-sensitive, or external-facing use without additional evaluation.

## Model Routing Plan

The demo now shows a more realistic migration path:

- move low-risk tasks to the candidate/local model;
- keep sensitive or borderline tasks on human review;
- keep failed or unmapped tasks on the baseline/premium model;
- block or escalate tasks that are unsafe or insufficiently evaluated.

The generated route-plan files are deterministic, offline-first, and file-based.
They do not claim deep runtime integration across the packages.

## Ecosystem map

| Project | Role in this demo |
|---|---|
| OpenOntologyLite | Defines business concepts and an AI System Map for task risk, routes, review, escalation, audit, and cost expectations. |
| AgentPolicyPack | Defines governance rules for low-risk use, human review, escalation, and external response handling. |
| ModelSwapBench | Generates or represents the AI Vendor Exit Report and comparison results. |
| AIAuditLog | Records decision events, benchmark events, and recommendation events in a tamper-evident style. |
| AIMeter OSS | Measures estimated usage, cost, efficiency, and outcome boundaries. |
| AgentForge | Could orchestrate the workflow in a real system. |
| PrivateAIStack | Could run the private/local controlled candidate deployment in a real system. |

## Files in this demo

| Path | Purpose |
|---|---|
| `data/customer_support_tickets.jsonl` | Fictional customer-support tickets. |
| `data/baseline_results.json` | Deterministic hosted-model fixture. |
| `data/candidate_results.json` | Deterministic local/open-model fixture. |
| `data/model_comparison_results.json` | Generated comparison output. |
| `ontology/support_ontology.yaml` | OpenOntologyLite-style business meaning. |
| `ontology/ai_system_map.yaml` | OpenOntologyLite AI System Map for portable workload routing and control meaning. |
| `policies/support_agent_policy.yaml` | AgentPolicyPack-style governance rules. |
| `reports/ai_vendor_exit_report.md` | Human-readable AI Vendor Exit Report. |
| `reports/ai_vendor_exit_report.json` | Machine-readable report. |
| `reports/model_routing_plan.md` | Human-readable Model Routing Plan. |
| `reports/model_routing_plan.json` | Machine-readable route plan. |
| `reports/aimeter_summary.json` | AIMeter OSS-style portable cost/outcome export. |
| `reports/route_aimeter_summary.json` | AIMeter OSS-style route cost/outcome export. |
| `reports/cost_outcome_summary.md` | AIMeter OSS-style cost and outcome summary. |
| `audit/audit_events.jsonl` | AIAuditLog-style portable audit-event export with hash chaining. |
| `audit/ai_audit_events.jsonl` | AIAuditLog-style audit-event examples with hash chaining. |
| `audit/route_audit_events.jsonl` | AIAuditLog-style route-plan audit events with hash chaining. |
| `scripts/run_demo.py` | Offline deterministic generator. |
| `Makefile` | Convenience target for running the demo. |

## How to run

From this directory:

```bash
python scripts/run_demo.py
```

Or:

```bash
make demo
```

The script has no external network dependency and does not call real OpenAI, Anthropic, Google, Hugging Face, or other provider APIs.

## What each package contributes

OpenOntologyLite defines portable organizational meaning outside model prompts or vendor tooling. In this demo, `support_ontology.yaml` captures Customer, SupportTicket, RiskLevel, Response, and Escalation, while `ai_system_map.yaml` maps ten workloads to the exact `candidate_model`, `baseline_model`, `human_review`, and `blocked_or_escalate` route vocabulary.

The AI System Map also records review and escalation requirements, expected audit events, expected cost metrics, and ecosystem integration meaning. Those entries are integration patterns. They do not prove that the packages are installed together or connected in a live runtime.

AgentPolicyPack defines portable governance rules. In this demo, low-risk internal tickets can use candidate model drafts with human review, high-risk tickets require human review and escalation, legal/medical/financial questions require escalation, and external responses require stronger review.

ModelSwapBench represents the model-replacement evaluation and AI Vendor Exit Report. In this demo, the benchmark data is deterministic fixture data rather than a live benchmark run.

The Model Routing Plan extends that fixture by showing which tasks can move to
the candidate model, which require human review, and which should be escalated
or blocked.

AIAuditLog records decision events, benchmark events, and recommendation events. Hash chaining is tamper-evident, not immutable. Signatures do not prove real-world identity. These events do not create legal non-repudiation or automatic compliance.

AIMeter OSS measures estimated usage, cost, efficiency, and outcome. This demo uses Decimal-based money calculations. Missing pricing is never zero, calculated cost is not invoice-confirmed, projected savings are not realized savings, API success is not automatically business success, and budgets are evaluated, not automatically enforced.

AgentForge could orchestrate the ontology load, policy evaluation, benchmark execution, routing decision, audit logging, and reporting flow in a real deployment.

PrivateAIStack could provide the controlled local/private model environment for the candidate model path in a real deployment.

## Example output

```text
Linux of AI Vendor Exit Demo complete
Generated files:
- data/model_comparison_results.json
- reports/ai_vendor_exit_report.md
- reports/ai_vendor_exit_report.json
- reports/model_routing_plan.md
- reports/model_routing_plan.json
- reports/aimeter_summary.json
- reports/route_aimeter_summary.json
- reports/cost_outcome_summary.md
- audit/audit_events.jsonl
- audit/ai_audit_events.jsonl
- audit/route_audit_events.jsonl
```

Example report language:

```text
Estimated cost reduction: 91.20%
Quality retained: 90.22%
Decision: Candidate acceptable with human review
Recommended use: low-risk internal support workflows
Model Routing Plan: move low-risk tasks first, review sensitive tasks, and escalate blocked tasks.
Do not use as proof of legal, regulatory, safety, or security compliance.
```

## Limitations

This demo is file-based and deterministic. It demonstrates an integration pattern using compatible input and output files. It does not claim deep runtime integration across all packages.

The model outputs and scores are fixtures, not live model evaluations. The estimated costs are example values, not invoices. The generated report is not proof of legal, regulatory, safety, or security compliance.

No real customer data, personal emails, phone numbers, addresses, account numbers, API keys, tokens, or secrets are included.

## Next integration steps

- Replace fixture scores with a real ModelSwapBench evaluation run.
- Connect AgentPolicyPack policy evaluation directly to the workflow decision.
- Emit AIAuditLog events through the package API or CLI.
- Capture AIMeter OSS measurements from real request and outcome data.
- Use AgentForge to orchestrate the full workflow.
- Use PrivateAIStack to host the candidate local/private model path.
- Add CI checks that regenerate the reports and compare deterministic output.
