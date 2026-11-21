# AI Vendor Exit Report

Demo: Linux of AI Vendor Exit Demo

Generated: 2026-01-01T00:00:00Z

This is deterministic example data for an offline integration-pattern demo. No OpenAI, Anthropic, Google, Hugging Face, or other hosted provider API was called.

## Scenario

A fictional company evaluates whether a lower-cost local/open model can replace an expensive hosted model for low-risk internal customer-support drafting.

## Model Comparison

| Measure | Baseline | Candidate |
|---|---:|---:|
| Provider | hosted-example | local-example |
| Model | premium-model | local-small-model |
| Quality score | 0.92 | 0.83 |
| Average latency | 1.20 seconds | 1.55 seconds |
| Estimated cost | $12.50 | $1.10 |

Estimated cost reduction: 91.20%

Quality retained: 90.22%

Thresholds: quality retained >= 90.00%, estimated cost reduction >= 15.00%, latency increase <= 30.00%

Decision: Candidate acceptable with human review

Recommended use: low-risk internal support workflows

## Governance Result

Candidate acceptable with human review. High-risk legal, medical, financial, security-sensitive, or external-facing use requires additional evaluation and escalation.

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
