# Linux of AI Quickstart Kit

## Why it exists

The Linux of AI ecosystem contains focused tools for ontology, policy, model comparison, audit evidence, cost and outcome measurement, orchestration, and private deployment. A new developer still needs one small path that shows how those concerns fit together before choosing package-specific workflows.

The Quickstart Kit creates that path as an editable, deterministic workspace. It does not create an eighth package and does not require any of the seven package CLIs for its default run.

## Generate and run a workspace

From the central Linux-of-AI repository:

```bash
python scripts/create_vendor_exit_project.py my-ai-exit-check
cd my-ai-exit-check
python run.py
```

On macOS or Linux, the generated workspace also supports:

```bash
./run.sh
```

If Make is installed:

```bash
make run
```

The generator refuses to write into an existing non-empty directory unless `--force` is supplied. With `--force`, it replaces template-owned files but does not delete unrelated files already in the target directory.

No external API, model provider, network connection, secret, or `.env` file is required. The default path uses only the Python standard library.

## Generated workspace

```text
my-ai-exit-check/
  README.md
  LICENSE
  run.py
  run.sh
  Makefile
  input/
    tasks.jsonl
    baseline_results.json
    candidate_results.json
    model_comparison_results.json
  ontology/
    ai_system_map.yaml
  policies/
    support_policy.yaml
  reports/
  audit/
  outputs/
```

Running `python run.py` writes:

```text
reports/
  ai_vendor_exit_report.md
  ai_vendor_exit_report.json
  model_routing_plan.md
  model_routing_plan.json
  aimeter_summary.json
  route_aimeter_summary.json
audit/
  audit_events.jsonl
  route_audit_events.jsonl
outputs/
  ai_system_map_report.md
  ai_system_map.mmd
```

All default inputs are fictional customer-support fixtures. Generated timestamps are fixed fixture metadata so unchanged inputs produce byte-for-byte stable outputs.

The `Unclassified Request` fixture intentionally retains an `unknown` risk level and a baseline-only escalation path. OpenOntologyLite reports one warning for that task, and strict validation will not pass until the developer assigns a reviewed risk. This demonstrates how unknown work remains gated rather than silently moving to a candidate model.

## Ecosystem file map

| Project | Quickstart contribution |
|---|---|
| OpenOntologyLite | `ontology/ai_system_map.yaml` records task meaning, risk, allowed routes, review, audit, and measurement expectations. |
| AgentPolicyPack | `policies/support_policy.yaml` demonstrates candidate, review, baseline, and escalation rules. |
| ModelSwapBench | Vendor Exit Report and Model Routing Plan files demonstrate model comparison and task-level migration decisions. |
| AIAuditLog | `audit/*.jsonl` demonstrates portable hash-chained audit-event evidence. |
| AIMeter OSS | `reports/*aimeter*.json` demonstrates estimated cost and outcome measurement. |
| AgentForge | A real deployment could orchestrate the mapped workflow after the file pattern is replaced with reviewed runtime logic. |
| PrivateAIStack | A real deployment could run an approved route in a controlled private or local environment. |

These are file-based integration patterns, not verified live integrations. The generated runner does not import or invoke the seven projects.

Hash chaining in the JSONL files is a tamper-evident pattern. It does not make evidence immutable, prove real-world identity, or provide legal non-repudiation. Estimated cost is not invoice-confirmed, projected savings are not realized savings, and unknown review or escalation costs remain `null` rather than being treated as zero.

## Replace fixtures with project data

1. Inventory real AI tasks without placing unnecessary personal or confidential data in the starter files.
2. Replace `input/tasks.jsonl`, preserving one JSON object per line and reviewing every risk and route.
3. Replace the baseline and candidate result files with measured results and documented measurement conditions.
4. Replace comparison thresholds and recommendation text with reviewed project criteria.
5. Update the AI System Map and policy fixture so they agree with the task inventory.
6. Run the workspace and review every Markdown, JSON, JSONL, and Mermaid output.
7. Use individual package CLIs where stronger schema validation, benchmarking, policy evaluation, audit handling, measurement, orchestration, or deployment behavior is needed.

Do not place provider credentials in the workspace. Handle real data according to your security, privacy, retention, and governance requirements.

## Quickstart Kit versus flagship demo

The [flagship Vendor Exit Demo](../examples/vendor-exit-demo/) is an example maintained inside the central repository. It is useful for inspecting the ecosystem's reference pattern in place.

The Quickstart Kit is a generator. It creates a new standalone workspace intended for experimentation and replacement with project-specific inputs. The two experiences share file concepts, but the generated workspace remains self-contained and standard-library-only.

## Verify the kit

Repository maintainers can run:

```bash
python -m compileall scripts quickstart/vendor-exit-template/run.py
python scripts/verify_quickstart.py
git diff --check
```

The verifier creates a temporary workspace, tests overwrite protection, runs the project twice, checks deterministic output, parses every JSON and JSONL file, validates audit hash chains and risk routes, checks expected report and Mermaid content, and scans generated files for common credential, email, and absolute user-path patterns.

## Limitations

- This is a deterministic offline starter, not a hosted AI provider or foundation model.
- It is not a compliance certification, legal guarantee, or security certification.
- It does not prove that a model migration or workflow is safe.
- It does not automatically enforce policy or replace qualified human review.
- It does not run a real model benchmark or connect the seven projects through a live runtime.
- Model behavior can change across versions, providers, prompts, and runtime environments.
- The fictional decisions and estimates must not be treated as production evidence.
