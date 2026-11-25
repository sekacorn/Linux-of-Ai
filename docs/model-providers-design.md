# The `model_providers` lock-in vector: design

Status: **proposed, awaiting approval.** Revised after the first review with the
owner's decisions applied (listed below). No code exists yet. Each checkpoint
at the end still needs its own review and merge.

Eleven vectors measure what it would take to leave a vendor: prompts,
embeddings, memory and so on. None measures the most direct dependency of all:
**which model provider the system calls, and whether anything else could take
its place.** This document adds that as the twelfth vector.

## Decisions recorded

| Question | Decision |
|---|---|
| Can a benchmark whose execution is only attested reach 0? | **No.** It caps the provider at **25**. 0 is reserved for scanner-verified evidence. |
| Report shape | **`exit-report.v2`, rubric 2**, released as **suite 0.2.0b1**. |
| Manifest states for this vector | **`provider_inventory` and `inapplicable` only.** |
| Reason text for a 50 | **Must say which case applied**: a tested hosted alternative, an untested declared fallback, or a feature in use the benchmark did not exercise. When more than one applies, each is named. |
| Rubric-2 review item (not changed now) | `restore_tested` reaches 0 on *attested* evidence today, which conflicts with the rule above. To be resolved when rubric 2 is reviewed. |

## 1. `provider-inventory.v1`

The suite owns the JSON Schema and packages it, as it does
`re-embed-record.v1`. AgentForge is the natural writer, from the provider
description it already computes for every model call (provider, preset,
hosting, jurisdiction, endpoint origin). An operator may also write one by hand.

```json
{
  "schema_version": "provider-inventory.v1",
  "generated_by": {"tool": "agentforge-oss", "version": "0.5.6"},
  "providers": [
    {
      "provider_id": "gateway_a",
      "kind": "openai_compatible",
      "preset": "vendor_a_preset",
      "preset_source": "built_in",
      "endpoint_origin": "https://llm.vendor-a.example",
      "hosting_declared": "hosted",
      "jurisdiction": "XA",
      "models": [{"model": "model-large"}],
      "openai_compatible_fallback": {"available": true, "provider_id": "local_vllm"},
      "features": {
        "tool_calling": true,
        "streaming": false,
        "vendor_only": [{"feature": "server_side_prompt_cache", "reconstruction": "documented"}]
      }
    }
  ]
}
```

- **`endpoint_origin`** is scheme, host and optional port only. The pattern
  forbids `@`, any path, query or fragment, so a credential cannot be
  represented. It may be `null` only for a provider kind whose SDK supplies its
  own hosted default; `ollama` and `openai_compatible` must state one.
- **`hosting_declared`** is optional. The scanner derives hosting itself (§2).
- **`jurisdiction`** is ISO 3166-1 alpha-2, `unknown` or `not_applicable`, and
  is always reported as attested. It is shown, never scored: it is a policy
  question, which AgentPolicyPack answers.
- **`openai_compatible_fallback.provider_id`**, when given, must name another
  entry in the same inventory.
- `generated_by` is a producer string and is not trusted.

**Bounded parsing:**
- at most 256 KiB, read through the suite's bounded reader;
- duplicate keys and NaN/Infinity refused; every object closed;
- at most 64 providers, 64 models per provider, 16 vendor-only features per
  provider; strings at most 256 characters;
- `provider_id` matches `^[a-z0-9_]{1,64}$` and is unique.

Fixtures use placeholder hosts and names only (`*.example`, `vendor_a`, `XA`).

## 2. The ladder

Each provider is scored; **the vector takes the worst provider's score.** No
evidence available today is scanner-verified for this vector: the suite never
runs a model, so it cannot itself show that an alternative works. **0 is
therefore unreachable in rubric 2, by design,** and stays reserved for a
future check the scanner can run itself.

| Score | Condition, per provider |
|---|---|
| **0** | Reserved for scanner-verified evidence. Nothing reaches it in rubric 2. |
| **25** | Every model in use has an **accepted tested alternative** whose candidate is **local**; every feature in use was exercised by the benchmark; no vendor-only feature is in use. |
| **50** | One of: an accepted alternative exists for every model, but some candidate is **hosted** (it moves the workload between vendors, not off them); or a **feature in use was not exercised** by the benchmark (streaming always, today); or there is no accepted alternative for every model, no vendor-only feature, and an OpenAI-compatible fallback is declared. |
| **75** | A vendor-only feature is in use, with `reconstruction: documented`. |
| **100** | No inventory; or a vendor-only feature with no reconstruction path; or no fallback and no accepted alternative. |

**A 50 always says why.** The row's reason names which case applied: a
tested alternative that is hosted, an untested declared fallback, or a feature
in use that the benchmark did not exercise (named). If several apply, each is
listed. A reader must never have to guess which of three different situations
a 50 stands for.

**Accepted** is the suite's own rule, recomputed from the benchmark's numbers
(§4). Cost is deliberately ignored: a more expensive alternative still proves
the workload can leave.

**What the scanner verifies itself:**
- the inventory's digest, shape and bounds;
- hosting, derived from each `endpoint_origin` by the suite's own copy of the
  no-DNS local rule; a declaration can only add hosted-ness, and `local` on a
  public host is refused;
- fallback references;
- that each benchmark document binds by digest to an inventory provider and model;
- the candidate's hosting, derived from its endpoint origin;
- acceptance and feature coverage, recomputed from the benchmark's summary numbers.

**What stays attested:** that any model was actually run, and every measured
number; features in use, vendor-only features and reconstruction paths;
jurisdiction; producer strings.

**Levels.** A provider scored from a benchmark gets `verified (benchmark
arithmetic)`; one scored from declarations alone gets `attested`. The vector
takes the level of the provider that sets its score, the weaker on a tie. The
new level is for the owner to add to the vocabulary table in CLAUDE.md:

| Level | Means | Does not mean |
|---|---|---|
| `verified (benchmark arithmetic)` | The scanner derived hosting from each endpoint, bound the benchmark evidence by digest, and recomputed acceptance and feature coverage from its summary numbers. | That any model was run, that the measurements are real, or that the alternative works in production. |

## 3. How exit-report ingests it

```json
"model_providers": {
  "state": "provider_inventory",
  "path": "evidence/provider-inventory.json",
  "sha256": "...",
  "tested_alternatives": [{"path": "evidence/swap-a.json", "sha256": "..."}]
}
```

- Only `provider_inventory` and `inapplicable` are accepted for this vector.
- At most 64 `tested_alternatives`. One that binds to no provider and model in
  the inventory is **refused, not skipped**, as re-embed records are.
- The manifest stays `exit-manifest.v1`; the vector name is additive. Suite
  0.1.0b4 and earlier refuse a manifest that declares it, which goes in the
  compatibility note.
- The vector table keeps one row per vector. Per-provider detail goes in a
  top-level `model_providers` section, as `embedding_stores` does.
- A manifest without the vector always gets the row `unknown | 100 |
  unverified | No evidence supplied.` It is never omitted.

**Report shape: `exit-report.v2`, rubric 2.** v1 requires exactly eleven
vectors and is closed, so a twelfth breaks every v1 validator.
- Rubric 2 is rubric 1 plus this vector; the ladder for the other eleven is unchanged.
- The v1 schema stays packaged, so existing reports still validate.
- The Markdown header reads "Rubric 2". The docs say a rubric-1 report did not
  assess model providers, meaning "not assessed", never 0 or 100.
- A test pins that the original eleven rows are identical for identical evidence.
- The `VECTORS` constant grows to twelve, which the changelog states.
- The suite's every-report schema net (added in 0.1.0b4) validates every
  report against v2 once v2 ships.

## 4. ModelSwapBench results as evidence, without importing it

The same independence rule as 3b-6: the suite reads a versioned JSON document
and reimplements the arithmetic itself, and a cross-repo test proves the two
sides agree.

ModelSwapBench's current outputs carry no version field, so it writes a new
**`model-swap-evidence.v1`** document (for example `modelswapbench exit-report
--format evidence`). The suite owns the schema; the format gets fixtures.
Contents:
- run binding: `run_id`, `manifest_hash`, `created_at`, `generated_by`;
- baseline and candidate: provider kind, model, endpoint origin (credentials
  already refused at load since ModelSwapBench 0.1.0b4), declared deployment;
- raw summary numbers: sample, success, failure, error and timeout counts;
  quality score; `tool_accuracy`; `policy_pass_rate`; `evidence_sufficient`;
- declared thresholds and ModelSwapBench's own verdict.

The suite's reader:
- never imports `model_swap_bench`;
- recomputes acceptance and **refuses** a document whose stated verdict
  disagrees;
- requires `evidence_sufficient` and at least the run's
  `minimum_recommended_sample_size` (default 20), not ModelSwapBench's exit
  floor of 3;
- derives the candidate's hosting itself; a fake candidate (`deterministic`,
  `echo`, or a replay run) is reported but moves nothing;
- uses a suite copy of the endpoint rule, pinned to ModelSwapBench's and
  AgentForge's by a shared table of cases.

ModelSwapBench and AgentForge each get a `suite-contract` CI job, like
PrivateAIStack's, that installs the suite and validates every variant they emit.

## 5. Negative tests

**Inventory:**
- wrong or missing `schema_version`; an unknown key at any level;
- duplicate keys; NaN or Infinity; larger than 256 KiB; any bound exceeded;
- a duplicate `provider_id`;
- an `endpoint_origin` with userinfo, a path, query or fragment, a non-http(s)
  scheme, an empty host or a bad port;
- a `null` origin on `ollama` or `openai_compatible`;
- `hosting_declared: local` on a public host refused; `hosted` on loopback honoured;
- a fallback naming a missing provider or itself;
- a jurisdiction that is not two uppercase letters or one of the two literals;
- an empty `providers` list (use `inapplicable`);
- a digest mismatch, an empty file, a symlink or path escape.

**Benchmark evidence:**
- no or unknown `schema_version`;
- a stated verdict that disagrees with the recomputation;
- a baseline matching no inventory provider and model;
- one document bound to two providers;
- a fake, echo or replay candidate (reported, moves nothing);
- a hosted candidate presented as local;
- too few samples, `evidence_sufficient: false`, or a null quality score (no move);
- tool calling in use with a null `tool_accuracy`, or streaming in use (50, not 25);
- each of the three 50 cases produces a reason naming that case, and a provider
  hitting two cases names both;
- inconsistent counts or out-of-range rates;
- more than 64 alternatives; a digest mismatch;
- a more expensive candidate still accepted (cost ignored);
- **nothing ever scores 0** on this vector in rubric 2.

**Report:**
- an absent vector gives an `unknown`/100/`unverified` row, never a missing one;
- the worst provider governs;
- the eleven original rows unchanged by adding the vector;
- v2 reports validate against v2, v1 reports against v1;
- a manifest declaring `model_providers` refused by the v1 reader;
- jurisdiction never changes a score;
- no credentials or full URLs anywhere in the report.

## Checkpoints

Each is its own PR and stops for review.

1. **Suite:** `provider-inventory.v1` schema, fixtures and bounded reader. No
   scoring yet.
2. **ModelSwapBench:** `model-swap-evidence.v1` writer, plus its
   `suite-contract` job once the suite reader exists.
3. **Suite:** the benchmark-evidence reader and the acceptance recomputation,
   with the cross-repo agreement test.
4. **Suite:** the `model_providers` vector, `exit-report.v2` and rubric 2;
   released as 0.2.0b1.
5. **AgentForge:** `forge providers inventory`, plus its `suite-contract` job.
