# Linux of AI Vendor Exit Quickstart

Project workspace: **{{PROJECT_NAME}}**

## What this is

This Quickstart Kit is a deterministic offline starter workspace. It demonstrates the file and report pattern used by the Linux of AI ecosystem. Individual package CLIs can be used for deeper workflows.

Everything runs with the Python standard library. It does not call OpenAI, Anthropic, Google, Hugging Face, or any other external API. It needs no network connection, secret, or `.env` file.

## What problem it demonstrates

The fictional customer-support workload shows how to inspect a possible AI vendor exit without treating migration as one all-or-nothing decision. Low-risk tasks can use a candidate route, sensitive tasks can retain human review or the baseline route, and regulated or security-sensitive tasks can be blocked or escalated.

The fixtures are examples, not evidence that a particular model, provider, migration, or workflow is safe.

## How to run

```bash
python run.py
```

On macOS or Linux, you can also run:

```bash
./run.sh
```

If Make is available:

```bash
make run
```

The command is deterministic: rerunning it with unchanged inputs produces the same output bytes.

The fictional `Unclassified Request` intentionally uses the `unknown` risk level and stays on the baseline route. OpenOntologyLite validation reports that as a warning; strict validation continues to fail until you assess and replace the unknown risk. This is a guardrail, not a fixture error.

## Generated outputs

| File | Purpose |
|---|---|
| `reports/ai_vendor_exit_report.md` | Human-readable baseline and candidate comparison. |
| `reports/ai_vendor_exit_report.json` | Machine-readable vendor-exit report. |
| `reports/model_routing_plan.md` | Human-readable task-level routing plan. |
| `reports/model_routing_plan.json` | Machine-readable route decisions and controls. |
| `reports/aimeter_summary.json` | AIMeter OSS-style estimated cost and outcome summary. |
| `reports/route_aimeter_summary.json` | AIMeter OSS-style route summary with unknown costs preserved as `null`. |
| `audit/audit_events.jsonl` | AIAuditLog-style vendor-exit audit events. |
| `audit/route_audit_events.jsonl` | AIAuditLog-style route-decision events. |
| `outputs/ai_system_map_report.md` | Human-readable AI System Map report. |
| `outputs/ai_system_map.mmd` | Mermaid source for the system, tasks, routes, audit, and cost nodes. |

The audit files use SHA-256 hash chaining as a tamper-evident pattern. Hash chaining does not make a file immutable and does not provide legal non-repudiation.

## How the Linux of AI tools map to the files

**OpenOntologyLite** maps to `ontology/ai_system_map.yaml`. The map defines tasks, risk levels, allowed routes, human-review rules, audit expectations, and cost/outcome expectations.

**AgentPolicyPack** maps to `policies/support_policy.yaml`. The policy fixture shows governance rules for candidate use, human review, and escalation. This workspace documents rules but does not automatically enforce them.

**ModelSwapBench** maps to the AI Vendor Exit Report and Model Routing Plan under `reports/`. The comparison values are deterministic fixture values, not a live benchmark run.

**AIAuditLog** maps to `audit/*.jsonl`. These files show portable, hash-chained audit-event evidence. The pattern is tamper-evident, not immutable, and does not establish real-world identity or legal non-repudiation.

**AIMeter OSS** maps to `reports/*aimeter*.json`. Costs are estimates, not invoice-confirmed amounts. Projected savings are not realized savings. Missing human-review or escalation costs remain `null`; missing cost is never zero.

**AgentForge** could orchestrate a real workflow that consumes the task and route definitions. No live AgentForge integration runs in this quickstart.

**PrivateAIStack** could provide a controlled private or local execution pattern for an approved candidate route. No model or deployment stack runs in this quickstart.

These mappings are portable file patterns. They are not claims that the seven projects are installed together or connected through a live runtime.

## What to replace with your own data

1. Replace `input/tasks.jsonl` with your own task inventory while keeping one JSON object per line.
2. Replace `input/baseline_results.json` and `input/candidate_results.json` with measured model results.
3. Update `input/model_comparison_results.json` with your thresholds and a reviewed recommendation.
4. Update `ontology/ai_system_map.yaml` so task meaning and controls match the workload.
5. Update `policies/support_policy.yaml` with rules reviewed by the appropriate owners.
6. Run `python run.py`, inspect every route, and connect package CLIs only where deeper validation or runtime behavior is required.

Do not put credentials or unnecessary personal data in these files. Treat real workload data according to your security, privacy, retention, and governance requirements.

## Limitations

- This is not a hosted AI provider or a foundation model.
- This is not a compliance certification or legal guarantee.
- This does not prove that a model migration is automatically safe.
- This does not automatically enforce policy.
- This does not replace human review for high-risk workflows.
- This quickstart uses fictional offline fixture data.
- Model behavior can change across versions, providers, prompts, and runtime environments.
- Estimated cost is not invoice-confirmed, and projected savings are not realized savings.
- The generated evidence is a portable demonstration, not security certification.

## License

This quickstart template is available under the MIT License. See `LICENSE`.
