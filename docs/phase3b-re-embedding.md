# Phase 3b re-embedding design

Status: **approved at checkpoint 3b-0**, with the owner's amendments applied.
This document authorizes the checkpoints listed at the end; each still needs
its own review and merge.

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
| `agentforge.hashed-bow.blake2b` | `1` | declared per store | unsigned term frequency |
| `privateaistack.hashed-bow.sha256-signed` | `1` | declared per store | signed plus/minus 1 |

These are descriptive names for schemes that already exist. They are not new
public APIs and they rename nothing.

**Model identity is the triple `id` + `revision` + `dimensions`**, not the
identifier alone. Two stores using the same scheme at different dimensions are
different models for every purpose in this phase: comparison, re-embedding
target selection and scoring.

**A dimension mismatch against the declared identity is an error, never a
default.** If the vectors a run produces do not have the declared number of
dimensions, the run fails and no store is written. Nothing in 3b ever falls
back to a backend's default dimension, which is what makes the backend
inconsistency below harmless here.

**AgentForge's own three backends disagree on default dimension** — `vector.py`
512, `sqlite.py` 64, `pgvector.py` 64 — with identical tokenizer and hash. A
store built by one backend is not readable by another at defaults. That is a
pre-existing inconsistency and is **not** fixed by this phase; it is recorded
separately in [known-issues.md](known-issues.md) for Phase 4. 3b is unaffected
because dimensions always come from the declared model identity in the
evidence, never from a backend default.

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

**AI Infrastructure Suite stays diagnostics-only, as amended in 3b-6.** It
**never runs a model or embeds text with one. It may recompute the two built-in
hash-based schemes, using the standard library only and over a bounded sample,
to verify a claim.** It opens no socket and loads no weights. The amendment
exists because condition (a) needs the scanner to reproduce a rebuild itself,
and recomputing a `hashlib` bucket sum over bytes already on disk is the same
kind of re-run as the JSON-LD round trip that earns `verified`.

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
- **A default batch size safe on a 16 GB machine.** The default is **64
  records**, chosen so the worst case stays small: 64 records at 3a's
  `MAX_SOURCE_TEXT_BYTES` of 1 MiB each is 64 MiB of text, plus 64 vectors at
  the 8192-dimension ceiling is under 5 MiB as Python floats. That is a few
  hundred megabytes with interpreter overhead, not gigabytes, and it holds
  regardless of store size because the store is never loaded whole. Operators
  with more memory can raise it; the point of the default is that nobody has to.
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

Three labels, all of which require that **the scanner itself reproduced the
re-embedding** and obtained the target store's declared digest. They differ
only in what the quality comparison found.

| Label | The scanner reproduced the rebuild, and | Score effect |
|---|---|---|
| `verified (re-embedded, quality sampled)` | the declared query set met the declared thresholds | may move 50 to 25 |
| `verified (re-embedded, quality not measured)` | no query set was supplied, or it was too small for `sufficient_evidence` | none |
| `verified (re-embedded, quality below threshold)` | the query set ran and at least one threshold was not met | **never improves the score** |

A rebuild the scanner **cannot** re-run — a live model run, most obviously —
gets none of these. It stays `attested`, exactly like any other
operator-supplied record whose bytes match its digest, and it does not move the
score. See Determinism and live models.

What the labels do **not** mean, to be stated wherever they appear:

- That retrieval is equivalent in production. It was measured on one query set.
- That the query set is representative. That is the operator's attested claim
  and appears in `attested_claims` as `query set representativeness`.
- That the new model is as good as the old one. Thresholds were met, which is a
  weaker statement and the only one the evidence supports.
- That the target model's availability, weight digest or license are true. Those
  stay attested exactly as in 3a.

`verified (re-embedded, quality below threshold)` is deliberately a *verified*
label rather than a failure to report. The rebuild really was reproduced; it is
the quality claim that failed, and saying so is more useful than discarding the
record. It simply never earns a better score than the store had without it.

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

**Approved: Option B, under four conditions that must all hold.** A store at 50
moves to 25 only when:

1. **The scanner itself reproduced the rebuild** and obtained the target
   store's declared digest. An operator's record alone is never enough.
2. **The quality check passed its declared thresholds** — the label is
   `verified (re-embedded, quality sampled)`. Both
   `quality not measured` and `quality below threshold` leave the 50 in place.
3. The target model is `open_weight_self_hostable`.
4. Retained coverage is complete: every retained record was rebuilt.

25 is "validated export with a compatible importer", and a rebuild the scanner
reproduced is precisely a validated importer. Anything short of all four
conditions leaves the 50 untouched.

The rejected alternative, recorded so the choice is legible later: Option A
would have reported the record and changed no score. It is defensible if one
wants scores to move only on digest-checkable facts, and the honest objection to
B is that part of its basis — the query set's representativeness — is attested
rather than verified. Condition 1 is what makes B defensible anyway: the
scanner's own reproduction is digest-checkable, and the attested part is
confined to `attested_claims` where a reader can see it.

The row gains the re-embed record's reference, the label, and the attested
claims it rests on, including `query set representativeness`. No existing level,
state or score changes meaning.

### Reason wording for deterministic schemes, to be decided in 3b-6

A store rebuilt with one of the built-in hashing schemes currently gets the
generic note "Model weights are not pinned, so re-embedding may not reproduce
identical vectors". For these schemes the "weights" are source code, so the
sentence reads as doubt about reproducibility that does not apply. Softer
wording is worth considering in 3b-6, under a rule narrow enough that it cannot
be claimed rather than earned:

**Softer wording applies only when both hold.** The scanner recognises the
exact built-in model identity — `id`, `revision` *and* `dimensions`, the whole
triple — **and** the scanner reproduces a sample of that store's vectors
itself. A declared "deterministic" label, a recognised `id` alone, or a
matching `revision` at a different dimension never changes the wording.

The reason is that the first condition is a claim about which code ran and the
second is the only offline check that the code actually ran. Recognising an
identity proves the scanner knows a scheme by that name; it proves nothing
about the bytes on disk, which an operator could have produced with anything.
Without the reproduction, the generic note is the honest one.

This is a wording change only. It moves no score, creates no label, and nothing
in 3b-3 through 3b-5 may assume it.

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

## 3b-6 approved design

### How `exit-report` ingests a record

The `embeddings` manifest entry is unchanged — `state: embedding_inventory`
with the `embedding-portability.v1` document's path and digest — and gains one
optional additive field:

```json
"embeddings": {
  "state": "embedding_inventory",
  "path": "embeddings/embedding-portability.json",
  "sha256": "...",
  "re_embed_records": [{ "path": "rebuilt/re-embed-record.json", "sha256": "..." }]
}
```

An array, capped at 64 to match `stores`: one store may be rebuilt more than
once and a document may hold several stores. `exit-manifest.v1`'s
`additionalProperties: false` widens by exactly this one property; the version
does not change.

**The binding is checkable, which is the point.** A record's
`source_store.store_evidence_sha256` must equal the manifest's
`embeddings.sha256`, and its `source_store.store_id` must name a store in that
document. A record that does not bind is **refused**, not ignored: otherwise an
operator could attach a record produced from a different, more flattering
store.

The target store's bytes are found beside the record, as the pipeline writes
them, and trusted only by digest: the sibling `embedding-portability.json` must
hash to the record's `target_store.store_evidence_sha256`. Convention locates
the file and the digest decides whether to believe it. A missing or mismatched
target document means no reproduction, so the record stays `attested`.

### Scoring

Per the 3a ladder: no retained text is 100, partial retention 75, a
non-self-hostable model 50, a verified restore link 0, and otherwise 25.

A qualifying record moves a store **only from exactly 50 to 25**. That rung is
the right one because a store scores 50 precisely when *its own* model is
`vendor_only`; a reproduced rebuild onto a self-hostable model is the
demonstration that the store can be left, which is what 25 means. The other
rungs are unreachable anyway: 75 and 100 fail `coverage.complete`, and 0 is
strictly stronger evidence than any rebuild. So the gate is "if and only if the
3a score is 50". A record can never lower a score and can never produce 0,
which needs a verified restore and a functional check.

Worst-store aggregation needs no change. The aggregate already takes the
limiting per-store score, so improving one store cannot hide a worse one; the
improvement is applied per store before aggregation and the existing logic
runs. The `re_embeddable` aggregate is about retention, not models, and is
untouched.

### Older records

Absence is read two ways, deliberately. **For scoring it is conservative**: no
`anchor_selection` means no score movement, and no `quality` block means
`not_measured`. **For display it is never rendered as the safe value**: a
record without `executor_kind` prints `not stated`, never `local_builtin`,
because printing a default nobody wrote is how an older record comes to look
like a verified local run.

### Reproduction for condition (a)

The scanner reimplements the two built-in hash-based schemes itself and
recomputes a bounded sample of the target store's vectors from the target
store's own retained source text.

Three options were weighed. An optional import of PrivateAIStack's embedders
was **rejected**: the scanner would be using the audited party's code to verify
the audited party's claim, which is not independent verification whatever the
arithmetic says; it also inverts the layering and makes a verification level
depend on what happens to be installed, so the same evidence would score
differently on two machines. Doing no reproduction at all was **rejected**
because condition (a) could then never hold, every record would stay
`attested`, and the label ladder would be dead code.

Two implementations agreeing is evidence. One implementation agreeing with
itself is not.

**Drift is handled by a test, not by discipline.** The nightly
`suite-contract` job already installs both packages, so it asserts that
PrivateAIStack's embedders and the suite's reimplementation produce identical
vectors for the same inputs, across both schemes and several dimensions. Each
repository keeps its own golden fixture for its own unit tests; the cross-repo
agreement test is what makes them one contract. The dependency stays
one-directional: the job lives in PrivateAIStack and installs the suite, and
the suite imports nothing from PrivateAIStack.

### The diagnostics-only invariant, amended

The suite **never runs a model or embeds text with one. It may recompute the
two built-in hash-based schemes, using the standard library only and over a
bounded sample, to verify a claim.**

Recomputing a hashed bag-of-words vector is arithmetic over `hashlib` across
bytes already on disk: no weights, no socket, no provider SDK. It is the same
kind of re-run as the JSON-LD round trip that earns `verified`, or re-hashing
retained source text. Scope is narrow by construction — standard library only,
the two built-in schemes only, a bounded sample, and any other identity is
refused rather than approximated.

### Seeds are derived, never accepted

An operator who chooses the seed can grind it: draw set after set until the
quality numbers clear the bar, then publish the one that passed. So the scanner
does not take a seed from the record.

- **Anchor seed** = `sha256` over the source and target store digests.
- **Reproduction-sample seed** = `sha256` over the target store digest.

Both are functions of content the record already commits to, so neither party
can steer them, and a third party recomputes the same sets from the record
alone.

A record whose `anchor_seed` is anything other than the derived value is
treated as `anchor_selection: operator`: reported in full, with its label,
metrics and checks, and **never moving a score**. That is the same treatment a
hand-picked query set gets, for the same reason — an operator who may choose
the queries may choose the result, and no offline check can tell a fair choice
from a flattering one.

The scanner's reproduction sample is derived independently of anything in the
record, so a seed written into a record cannot influence which vectors get
checked.

### What the report shows

Per record, in JSON: the label, `rebuild_reproduced`, the score effect,
`quality.status`, the declared `thresholds`, `metrics`, `mode`,
`metric_basis`, `anchor_selection`, `attested_claims`, and the whole `egress`
block.

In Markdown, the verdict and the bar appear together, never apart, because a
report that prints "quality sampled" without the bar that was cleared has told
the reader the verdict and withheld the standard. Record-anchored results are
labelled `neighborhood_agreement` and explicitly not a measure of search
quality.

**External execution and hosted data are impossible to miss.** A record with
`executor_kind: external_unverified` or `hosting_mode: hosted` emits a block
above the detail *and* in the summary table's reason, so a reader skimming only
the summary still sees it: which executor ran, that its network behaviour is
attested and unverified, how many records were handed over, that delivery is
`unverified`, and which consents were given. A registry-owned run gets one
quiet line. The asymmetry is deliberate: the alarming case should be loud and
the ordinary case should not compete with it.

### Reason wording for deterministic schemes

The generic sentence — "Model weights are not pinned, so re-embedding may not
reproduce identical vectors" — is replaced only when **both** conditions hold:
the scanner recognises the exact identity triple (`id`, `revision` *and*
`dimensions`), **and** the scanner recomputed a sample of that store's vectors
and they matched. A declared "deterministic" label, a recognised `id` alone, or
a matching `revision` at a different dimension never qualifies.

Those two conditions coincide with reproduction succeeding, so the softer
sentence appears exactly when reproduction happened and never on a claim. It
moves no score and creates no label.

### Labels

Four new levels, carried by the re-embed record rather than the `embeddings`
row:

| Level | Means | Does not mean |
|---|---|---|
| `verified (re-embedded, quality sampled)` | The scanner recomputed a sample of N vectors that matched the target store's recorded vectors, and every declared threshold was met. | That the whole store was reproduced — a sample is not a whole-store digest. That the thresholds were adequate, that any provider received anything, or that retrieval is good. |
| `verified (re-embedded, quality below threshold)` | The sample matched; the comparison ran and at least one declared threshold was not met. | Still a verified rebuild. Never improves a score. |
| `verified (re-embedded, quality unjudged)` | The sample matched; the comparison produced metrics and no agreement floor was declared, so there is no verdict. | Not a pass. Never improves a score. |
| `verified (re-embedded, quality not measured)` | The sample matched; no usable query set, or too few queries for sufficient evidence. | Never improves a score. |

`attested` widens to cover a re-embed record whose rebuild the scanner did not
reproduce, including every real-model run however good its numbers look.

Combined levels such as `verified (local evidence + re-embedded, ...)` are
deliberately **not** introduced. The `embeddings` row keeps its existing
levels and the record carries its own; multiplying four re-embedding states by
the existing two buys nothing.

A re-embed record can only ever move a store from 50 to 25.

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

8. **A ground seed.** A record whose `anchor_seed` is not the derived value is
   reported with its full label and metrics and moves no score, labelled
   `anchor_selection: operator`. An operator who can choose the seed can grind
   it, so a seed that was chosen is treated as a query set that was chosen.
9. **Sample independence.** The scanner's reproduction sample is derived from
   the target store digest alone, so a seed written into a record cannot
   influence which vectors are checked. Asserted by changing the record's seed
   and showing the sampled record identifiers do not move.
10. **Reproduction failure.** A target store whose vectors do not match the
    recomputation earns no verified level, moves no score, and the mismatch is
    reported rather than swallowed.
11. **Unrecognised identity.** A target identity the scanner does not
    implement, and the same `id` and `revision` at a different `dimensions`,
    both stay `attested` with no softer wording and no score movement.
12. **Binding refusal.** A record whose `source_store` digest or `store_id`
    does not match the manifest's embeddings entry is refused, not ignored.

Plus, following 3a's discipline: an input with zero retained records, a golden
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

**3b-6 — exit-report integration.** The four new labels, the manifest entry,
the 50-to-25 move, derived seeds, scanner reproduction of a bounded vector
sample, and the reason wording for deterministic schemes under the
two-condition rule above. The approved design is in "3b-6 approved design"
below. Deliverable: a re-embed record changes the report in exactly the
approved way and in no other.

**3b-7 — Live verification, opt-in.** A `--live` run against a local Ollama
embedding model, recording its digest. Never in CI. Deliverable: evidence the
pipeline works against a real model, with its irreproducibility stated.

The model must be a **small** local embedding model, well under 1 GB —
`all-minilm` or `nomic-embed-text` are the candidates. Its download size is to
be checked and confirmed with the owner **before** anything is pulled; disk is
finite and a stray multi-gigabyte pull is not recoverable attention. A live run
produces an `attested` record, never a `verified (re-embedded, ...)` one, so
3b-7 proves the pipeline works and deliberately earns no score.

### Idea for 3b-7, not approved and not implemented

An **optional spot-check** could narrow the gap between "the scanner re-ran
everything" and "the scanner re-ran nothing". If the declared local model is
present on the machine and its weights digest matches the one in the record,
the scanner re-embeds a random sample of records, compares each vector against
the stored one within a stated numeric tolerance, and reports the sample size,
the seed, the tolerance and the agreement rate. It would carry its own label,
`verified (re-embedded, spot-checked)`, sitting between `attested` and the
fully reproduced levels.

This is recorded only so the thought is not lost. It is **not approved**, it
does not exist, and nothing in 3b-1 through 3b-6 may assume it. It raises
questions a design has to answer before any code: what tolerance is honest for
floating-point embedding output across hardware, whether a sample can support
any claim about the records it did not touch, whether a matching weights digest
really establishes the same model, and what the label must refuse to imply. It
will be designed and put to the owner for approval during 3b-7. Until then the
rule from 3b-0 stands unchanged: only a rebuild the scanner can re-run in full
reaches a verified level, and a real-model rebuild stays `attested` and moves
no score.

Phase 3b releases nothing and bumps no versions.

**Housekeeping, every checkpoint.** Temporary virtual environments and
smoke-test directories are deleted when the checkpoint finishes, and the disk
freed is reported. Only `C:\lai-venvs` persists between checkpoints.

## Decisions taken at 3b-0

All four are settled; this section records them so later checkpoints do not
reopen them.

1. **Placement** as proposed: execution in PrivateAIStack, quality in
   ModelSwapBench, the schema shipped in the suite, the suite diagnostics-only,
   no new package.
2. **Scoring: Option B**, gated on all four conditions above — scanner-reproduced
   rebuild, thresholds met, self-hostable target, complete retained coverage. A
   rebuild the scanner cannot re-run stays `attested` and moves nothing.
3. **Model identity is `id` + `revision` + `dimensions`**, using the two
   proposed identifiers. A dimension mismatch against the declared identity is
   an error; no backend default is ever consulted.
4. **Three labels**, as tabulated above. The workspace vocabulary table is the
   owner's to extend; this phase does not edit it.

The AgentForge backend default-dimension inconsistency is out of scope and is
recorded in [known-issues.md](known-issues.md) for Phase 4.
