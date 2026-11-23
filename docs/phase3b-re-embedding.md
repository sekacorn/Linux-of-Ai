# Phase 3b re-embedding design

Status: design for approval (checkpoint 3b-0). No pipeline, schema, CLI or
scoring implementation is authorized by this document.

Phase 3a answers "can this store be rebuilt?" from retained source text,
digests and coverage. It deliberately stops there: it never calls an embedding
model. Phase 3b answers the next question — "rebuild it with a different model,
and measure whether retrieval still behaves acceptably" — and the honest
difficulty is that the answer cannot be proved by a digest. A rebuilt index is
a *different* artifact by construction. Everything below is shaped by that.

## Audit: where the pipeline belongs

### The two built-in embedding schemes are incompatible

Both AgentForge and PrivateAIStack ship a deterministic hashing bag-of-words
embedder with cosine similarity. They agree on the idea and on nothing else.

| | AgentForge `forge/memory/vector.py` | PrivateAIStack `memory/embeddings.py` |
|---|---|---|
| Default dimension | 512 | 64 |
| Tokenizer | regex `[a-z0-9]+` over lowercased text | `text.lower().split()` |
| Hash | `blake2b`, `digest_size=8` | `sha256`, first 4 bytes |
| Value per token | unsigned term frequency (`+= 1.0`) | signed plus/minus 1, sign from `digest[4] % 2` |
| Normalisation | L2 | L2 |
| Record | `MemoryItem(id, text, metadata, score)` | `DocumentChunk(document_id, chunk_id, source_name, text, content_hash, embedding, metadata, created_at)` |

A vector from one is meaningless in the other's space **even at equal
dimension**: the hash family changes which bucket a token lands in, and the
signed-versus-unsigned choice changes the geometry. Reducing AgentForge to 64
dimensions would not make its vectors comparable to PrivateAIStack's.

**3b therefore treats them as two distinct declared models, not one model with
a dimension parameter.** Each gets a stable identifier, and a re-embed from one
to the other is a genuine model migration, exercising the same code path as a
migration to any third-party model.

Two findings from the audit change the design rather than merely colouring it.

**No embedding model identifier exists anywhere in either project.** This was
searched for, not assumed. `embedding-portability.v1` requires
`embedding_model.id` and `revision`, and both are operator-attested free text
today. A re-embed record has to name what it rebuilt *from* and *to*, so 3b
must define stable identifiers for the built-in schemes before anything else is
useful. Proposed, as attested values an operator may copy rather than invent:

| Identifier | Revision | Dimensions | Scheme |
|---|---|---|---|
| `agentforge.hashed-bow.blake2b` | `1` | as configured, default 512 | unsigned term frequency |
| `privateaistack.hashed-bow.sha256-signed` | `1` | as configured, default 64 | signed plus/minus 1 |

These are descriptive names for schemes that already exist. They are not new
public APIs and they rename nothing.

**AgentForge's own three backends disagree on default dimension** — `vector.py`
512, `sqlite.py` 64, `pgvector.py` 64 — with identical tokenizer and hash. A
store built by one backend is not readable by another at defaults. That is a
pre-existing inconsistency, reported separately, and 3b must not paper over it:
dimensions come from the declared model in the evidence, never from a default.

### Placement

**Re-embedding execution: PrivateAIStack.** It owns the chunk and vector store
(`MemoryStore.ingest`, `chunk_text`, `search`, `export_jsonl`), the
`DocumentChunk` record with `content_hash`, and both persistence modes. Its
embedder docstring already states the intent: "The boundary is intentionally
narrow so a stronger local embedding model can replace it." That is the seam.

**Quality check: ModelSwapBench.** It already has what a quality gate needs,
and all of it is standard-library only:

- `statistics.py` — `percentile`, `wilson_interval`, `bootstrap_mean_interval`,
  `describe`, and `paired_comparison(baseline, candidate, ...)` returning
  `sufficient_evidence` and `warnings`. It imports `math` and `random`, nothing
  else.
- `gates.py` — `GateThresholds` already carries `minimum_sample_size`,
  `minimum_quality` and `maximum_quality_drop`, plus
  `GateCheck(name, passed, category, actual, threshold, detail)` and
  `GateStatus`.
- `privacy.py` — `provider_data_preflight(..., allow_hosted=...)` returning
  `content_leaves_machine`, `hosted_execution_confirmed` and `warnings`. This is
  almost exactly the egress gate 3b needs, already written.
- `pricing/registry.py` and the `evaluators/` registry.

**AI Infrastructure Suite stays diagnostics-only.** It reads a re-embed record
in `exit-report` and never runs an embedder, loads weights or opens a socket. No
argument for changing that was found.

**No new package.** Nothing here needs a distribution of its own.

### The seam between the two repositories

PrivateAIStack and ModelSwapBench must not import each other. The contract is
the re-embed record itself: PrivateAIStack writes it, ModelSwapBench reads it
and writes the quality block back, and the suite reads the result. Neither takes
a code dependency on the other.

**The schema ships in the AI Infrastructure Suite**, alongside
`embedding-portability.schema.json` and the four existing evidence schemas. This
is the established pattern: `restore-summary.v1` is written by linux-ai-repo's
demo and read by the suite, with no dependency in either direction. The
alternative — the umbrella repository owning it — would put the schema somewhere
neither producer nor consumer installs.

This is the one placement decision worth contesting, because it means the suite
ships a schema for a record it does not produce. It already does exactly that
for `restore-summary.v1`.

## Input and output

### Input

An `embedding-portability.v1` document whose store has retained source text. 3b
requires nothing new in that format. The fields it consumes are the ones 3a
already validates: `store_id`, `embedding_model` (`id`, `revision`,
`dimensions`, `availability`, `availability_verification`, optional
`weights_sha256` and `license`), and per-record `source_text` with status
`retained`, `missing` or `deleted_by_policy`.

Records with `missing` or `deleted_by_policy` source text have no text to send
to a model and are never re-embedded. See Partial coverage and Privacy.

### Output

Two artifacts.

**A new store for the target model**, in the same `embedding-portability.v1`
format, with its own `store_id` and an `embedding_model` block describing the
target. It is an ordinary 3a input, so `exit-report` scores it with no new code:
the rebuilt store can itself be scanned, and its own coverage and model
availability are assessed exactly as any other store's.

**A re-embed record**, a new versioned document, `re-embed-record.v1`, with a
JSON Schema and fixtures. It links:

- `source_store`: `store_id` plus `store_evidence_sha256`, the digest of the
  input `embedding-portability.v1` document. Same binding discipline as
  `embedding_stores` in `restore-summary.v1`: an identifier selects the claim, a
  digest binds it to content.
- `target_store`: `store_id` plus `store_evidence_sha256` of the produced
  document.
- `target_model`: `id`, `revision`, `dimensions`, `availability`,
  `availability_verification`, optional `weights_sha256` and `license` — the
  same shape as `embedding_model` in 3a, so the two documents agree field for
  field.
- `batch_log`: the resumable run's accounting, below.
- `quality`: the comparison result, or an explicit absence.
- `egress`: what left the machine, if anything.
- `coverage`: what was rebuilt and what was not, with reasons.

A re-embed record carrying `quality` is not evidence that quality is good. It is
evidence that a stated comparison was run, and what it returned.

## Batching, resumability and idempotence

A re-embedding run over a large store is long and interruptible, so the pipeline
is a resumable batch job rather than a single pass.

- **Checkpoint file.** A separate document recording the target store, the
  source digest, the batch size and, for each completed batch, its index, the
  record identifiers it covered, and a digest over the vectors produced. It is
  written and flushed to disk after each batch, before that batch counts as
  done.
- **Resume.** On restart the pipeline validates that the checkpoint's source
  digest matches the input document; a mismatch is a hard error, never a partial
  resume against different input. It then skips completed batches by record
  identifier, not by count, so a reordered input cannot cause a silent skip.
- **Idempotence.** Re-running a completed job produces a byte-identical target
  store and the same record identifiers. Re-running a partially completed job
  finishes it without re-embedding completed records and without duplicating
  them.
- **Bounded memory.** One batch of source text and one batch of vectors are held
  at a time. Vectors are appended to sharded JSONL as each batch completes,
  which is the layout 3a already streams and digests per shard. Nothing holds
  the whole store.
- **Crash safety.** The target store is only ever appended to in whole batches,
  and the checkpoint is written after the shard. A crash between the two leaves
  a shard whose records are not yet claimed; resume detects the mismatch between
  shard contents and checkpoint and truncates the unclaimed tail rather than
  trusting it.

The invariant to test, not assert: after any number of interruptions at any
point, the finished store contains every retained record exactly once, in a
deterministic order, with no duplicates and no omissions.

## Cost estimation, before any run

A re-embedding run has a real cost — compute time locally, tokens and money
remotely — and the operator must see an estimate before committing to it.
`--estimate-only` performs the estimate and exits without embedding anything
beyond the calibration sample below.

**AIMeter supplies the arithmetic but not a forecast.** The audit found that
`calculate_local_inference_cost(record, profile)` requires
`performance.latency_ms` greater than zero: it derives cost from an *observed*
duration, so it cannot be called before a run. `calculate_provider_cost(record,
pricing)` is likewise token-driven. Neither is a pre-run estimator.

The honest construction is therefore a **calibration sample**: embed a small,
configurable number of retained records, measure real latency and real token
counts, then extrapolate to the full retained count and feed the result through
AIMeter's existing functions. The estimate reports its own method and limits:

- `records_to_embed`, from the actual retained count, which is exact.
- `calibration_sample_size`, and the measured per-record latency and tokens.
- `estimated_tokens` and `estimated_cost`, with currency, marked
  `status: "estimated"` as AIMeter already does.
- `local_cost_profile`, naming whose assumptions were used.
  `local_cost_profile_catalog()` templates say on their face that they are
  examples to be replaced with organisation-specific figures.

An estimate derived from a sample is not a quotation. The record states the
sample size so a reader can judge it, and a calibration sample of zero means no
estimate is reported rather than a fabricated one.

Remote cost estimation requires the same explicit egress opt-in as a remote run,
because the calibration sample itself transmits source text.

## Quality: old versus new retrieval

Digests cannot prove retrieval quality, so 3b measures it and is explicit about
the measurement's reach.

**Input.** An operator-supplied golden query set: queries, optionally with
expected record identifiers. Representativeness is the operator's claim, never
the scanner's, and is reported as attested.

**Metrics**, all computable with the standard library, following the precedent
already set in `statistics.py`:

- **Top-k overlap.** For each query, the size of the intersection of the old and
  new top-k result sets divided by k. Answers "does the new index surface the
  same material?" without needing expected answers.
- **Rank correlation.** Spearman's rho over the ranks the two indexes assign to
  the union of their top-k. Answers "does it order that material the same way?"
  and distinguishes a reordering from a substitution, which overlap alone cannot.
- **Hit rate and MRR**, only when expected answers are supplied. Hit rate is the
  fraction of queries whose expected record appears in the top-k; MRR is the
  mean of 1/rank of the first expected record, zero when absent. These are the
  only metrics here that speak to correctness rather than agreement.

Reported both as the new store's absolute values and as the change from the old
store, because a small absolute MRR that is unchanged is a different finding
from a large one that halved.

`paired_comparison(baseline, candidate, minimum_sample_size=...)` already
returns `sufficient_evidence` and `warnings`. A query set too small to support a
conclusion must report that, rather than a confident number.

**Thresholds** are configurable in the shape `gates.py` already uses:
`minimum_sample_size`, a floor on each metric, and a cap on the drop from the
old store, for which `GateThresholds.maximum_quality_drop` is the existing
precedent. Each check reports as a `GateCheck(name, passed, category, actual,
threshold, detail)`, so a failure says which metric, what it was, and what was
required.

### The verification label

The existing vocabulary does not cover this, and stretching it would be
dishonest. 3a's `verified (local evidence)` means digests and coverage were
re-checked; a quality result is not a digest check.

**Proposed: `verified (re-embedded, quality sampled)`.**

What it means, precisely: the scanner re-ran the re-embedding on the declared
target model and reproduced the target store's digest, **and** ran the declared
query set against both stores and found the declared thresholds met.

What it does **not** mean, to be stated wherever the label appears:

- That retrieval is equivalent in production. It was measured on one query set.
- That the query set is representative. That is the operator's attested claim,
  and it belongs in `attested_claims`.
- That the new model is as good as the old one. Thresholds were met, which is a
  weaker statement and the only one the evidence supports.
- That the target model's availability, weight digest or license are true. Those
  stay attested exactly as in 3a.

When the re-embedding was reproduced but the quality comparison was absent or
inconclusive, the label is `verified (re-embedded)` with no quality claim, and
the reason says why the comparison did not run.

## Privacy and data egress

Re-embedding sends source text to a model, which 3a never did. This is the
sharpest new risk in the phase.

- **Local and offline by default.** The default target is a local embedder. No
  socket is opened unless a remote provider is explicitly requested.
- **Remote providers are opt-in and reported.** A remote target requires an
  explicit flag, equivalent to `allow_hosted` in `provider_data_preflight`, and
  the record's `egress` block states that content left the machine: the
  provider, the record count, and whether raw source text was transmitted.
  Reusing the existing preflight means the warnings an operator sees are the
  ones ModelSwapBench already writes.
- **`deleted_by_policy` records are never re-embedded and never resurrected.**
  They are excluded from the input set before any batch is formed, excluded from
  the target store, and counted in `coverage` as deliberately skipped. A
  pipeline that rebuilt a vector for text an operator declared deleted would
  undo the deletion, which is worse than failing.
- **Vectors retained after source deletion are reported, never rebuilt.** 3a's
  `vector retained after source deletion` finding carries forward unchanged into
  the re-embed record, still reported and still unscored.
- **Reports print no source text and no vector values**, matching 3a.

## Partial coverage

Only retained records are re-embedded, and the record says exactly what was not
rebuilt and why:

- `retained_rebuilt`: embedded successfully.
- `missing_skipped`: no source text to embed.
- `deleted_by_policy_skipped`: excluded by policy, never sent to a model.
- `failed`: source text present but embedding failed, with the reason and the
  record identifiers, bounded the way 3a bounds finding identifiers.

The four counts plus any failures must reconcile with the input's record count —
the same invariant 3a enforces for retained, missing and deleted. A rebuilt
store covering a subset is a real and reportable outcome; silently shipping a
smaller index is not.

## exit-report integration

The rubric is unchanged. A re-embed record is additional evidence about an
existing store, not a new vector.

A re-embed record **never** produces a score of 0. Zero requires a verified
restore with a functional check, and a successful rebuild on a different model
is neither. If the *rebuilt* store is itself restore-tested later, it reaches 0
through the ordinary 3a path, on its own merits.

The one score change worth proposing concerns the 50 case, and it is a judgment
call.

A store at 50 has complete source coverage and a `vendor_only` model. 3a's
reason says migration "requires a replacement model and full index rebuild; cost
and quality may change." A re-embed record showing a completed rebuild onto an
`open_weight_self_hostable` target, with quality thresholds met, answers that
objection with evidence.

- **Option A, conservative.** The record is reported and changes no score. The
  50 stands. Simple, and never overstates.
- **Option B, recommended.** A store at 50 moves to 25 when a re-embed record
  shows a reproduced rebuild onto a self-hostable target, with quality
  thresholds met and full retained coverage. 25 is "validated export with a
  compatible importer", and a demonstrated rebuild is precisely a validated
  importer. Anything short of all of those conditions leaves the 50 in place.

Option B is recommended because it lets the rubric say something true that it
currently cannot: that this particular vendor-only store has a demonstrated
escape path. Option A is defensible if the preference is for scores to move only
on digest-checkable facts, and the honest objection to B is that part of its
basis — the query set's representativeness — is attested, not verified.

Under either option the row gains the re-embed record's reference, the label
above, and the attested claims it rests on. No existing level, state or score
changes meaning.

## Determinism and live models

- **Every test uses fake embedders.** Deterministic, offline, no sockets. The
  two built-in hashing schemes are themselves deterministic, which makes them
  usable as fakes with no mocking at all.
- **A real model runs only behind an explicit `--live` flag**, never in CI, in
  the shape ModelSwapBench already uses for Ollama
  (`MODELSWAPBENCH_RUN_OLLAMA_INTEGRATION=1`). A live run records the model
  digest it actually used, so the record says what produced the vectors.
- **Live runs are not reproducible and must not claim to be.** A record from a
  live run carries the model digest and the label, and the scanner cannot
  re-derive its vectors without the same model. That is reported, not hidden.

## Negative tests

Each must fail for the stated reason, not merely fail.

1. **Crash and resume.** Interrupt mid-run at several points, including between
   shard write and checkpoint write; resume; assert the finished store has every
   retained record exactly once, byte-identical to an uninterrupted run.
2. **Corrupted checkpoint.** Truncated, mutated digest, mutated record list, and
   a checkpoint whose source digest does not match the input. Each rejected, no
   partial resume.
3. **Dimension mismatch.** The target model declares a dimension the produced
   vectors do not have. Rejected before the store is written.
4. **Quality below threshold.** Thresholds not met; the run reports failure with
   the failing metric, its actual value and the requirement, and the record
   carries no passing quality claim.
5. **`deleted_by_policy` record in input.** Never embedded, never present in the
   target store, counted as deliberately skipped.
6. **Remote provider without opt-in.** Refused before any network call, with an
   assertion that no socket was opened.
7. **Model ID mismatch.** The declared target model does not match the model
   that produced the vectors. Rejected.

Plus, following 3a's discipline: a re-embed record whose `source_store` digest
does not match the input document, an input with zero retained records, a golden
query set too small for `sufficient_evidence`, and a quality block present on a
record whose rebuild was not reproduced.

## Proposed checkpoints

Each lands on a fresh branch off `origin/main` and merges by PR, with the
3.11-3.13 matrix and linters green, each verified in a freshly created virtual
environment.

**3b-1 — Model identity and the record format.** Stable identifiers for the two
built-in schemes. `re-embed-record.v1`, its JSON Schema shipped in the suite,
and fixtures. A reader and validator with the bounded, offline discipline of
`_evidence.py`. No embedding yet. Deliverable: a record can be written, read,
validated and rejected.

**3b-2 — The re-embedding pipeline, offline.** Batching, the checkpoint file,
resume, idempotence and bounded memory in PrivateAIStack, against the built-in
embedders only. Negative tests 1, 2, 3, 5 and 7. Deliverable: a store rebuilt
from retained source text, reproducibly, with crash safety demonstrated rather
than claimed.

**3b-3 — Cost estimation.** Calibration sample, extrapolation through AIMeter,
`--estimate-only`. Deliverable: an operator sees records, tokens and estimated
cost, with the sample size stated, before committing to a run.

**3b-4 — Quality comparison.** Golden query sets, top-k overlap, rank
correlation, hit rate and MRR, thresholds in the `gates.py` shape, in
ModelSwapBench. Negative test 4 and the `sufficient_evidence` case. Deliverable:
an old-versus-new comparison with a pass or fail and a reason.

**3b-5 — Privacy and egress.** Local-only default, the remote opt-in through
`provider_data_preflight`, the `egress` block. Negative test 6. Deliverable: a
remote run is impossible without an explicit flag and impossible to hide.

**3b-6 — exit-report integration.** The new label, the row and store fields, and
whichever scoring option is approved. Deliverable: a re-embed record changes the
report in exactly the approved way and in no other.

**3b-7 — Live verification, opt-in.** A `--live` run against a local Ollama
embedding model, recording its digest. Never in CI. Deliverable: evidence the
pipeline works against a real model, with its irreproducibility stated.

Phase 3b releases nothing and bumps no versions.

## Decisions needed before 3b-1

1. **Placement**, as above: execution in PrivateAIStack, quality in
   ModelSwapBench, schema in the suite, suite diagnostics-only, no new package.
2. **The scoring option**, A or B, for the 50 case. B is recommended.
3. **The model identifiers** in the table above, which become attested values
   operators copy.
4. **The verification label** wording, and that a quality-less record carries
   `verified (re-embedded)` instead.
