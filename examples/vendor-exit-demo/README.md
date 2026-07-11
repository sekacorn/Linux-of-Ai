# Linux of AI Vendor Exit Demo

This is a deterministic, offline-first integration-pattern demo for the Linux of AI ecosystem. It uses portable files and generated reports to show how a team could evaluate leaving an expensive or locked-in AI provider without making live provider calls.

## What this demo shows

The demo walks through a fictional customer-support workflow where a company compares an expensive hosted model against a lower-cost local/open candidate model. It shows how ontology, policy, benchmark output, audit evidence, and cost/outcome measurement can support a practical vendor-exit decision.

## Why vendor exit matters

Vendor exit matters because AI systems often become coupled to one provider's API, pricing, model behavior, logging, and governance assumptions. A team needs a repeatable way to ask whether a replacement model is good enough for a specific workflow, what risks remain, what evidence was recorded, and what costs are estimated to change.

## Scenario

A fictional company uses a hosted AI model to draft customer-support ticket responses. The company wants to know whether a lower-cost local/open model can replace the current model for low-risk internal support workflows.

The conclusion in this fixture is intentionally narrow: the candidate is acceptable with human review for low-risk internal support workflows. It is not recommended for high-risk legal, medical, financial, security-sensitive, or external-facing use without additional evaluation.

## Ecosystem map

| Project | Role in this demo |
|---|---|
| OpenOntologyLite | Defines business concepts such as Customer, SupportTicket, RiskLevel, Response, and Escalation. |
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
| `policies/support_agent_policy.yaml` | AgentPolicyPack-style governance rules. |
| `reports/ai_vendor_exit_report.md` | Human-readable AI Vendor Exit Report. |
| `reports/ai_vendor_exit_report.json` | Machine-readable report. |
| `reports/cost_outcome_summary.md` | AIMeter OSS-style cost and outcome summary. |
| `audit/ai_audit_events.jsonl` | AIAuditLog-style audit-event examples with hash chaining. |
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

OpenOntologyLite defines portable organizational meaning outside model prompts or vendor tooling. In this demo, it captures Customer, SupportTicket, RiskLevel, Response, and Escalation.

AgentPolicyPack defines portable governance rules. In this demo, low-risk internal tickets can use candidate model drafts with human review, high-risk tickets require human review and escalation, legal/medical/financial questions require escalation, and external responses require stronger review.

ModelSwapBench represents the model-replacement evaluation and AI Vendor Exit Report. In this demo, the benchmark data is deterministic fixture data rather than a live benchmark run.

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
- reports/cost_outcome_summary.md
- audit/ai_audit_events.jsonl
```

Example report language:

```text
Estimated cost reduction: 91.20%
Quality retained: 90.22%
Decision: Candidate acceptable with human review
Recommended use: low-risk internal support workflows
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
