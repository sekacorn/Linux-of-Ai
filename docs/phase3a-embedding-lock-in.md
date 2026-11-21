# Phase 3a embedding lock-in detection design

Status: design updated for approval (checkpoint 3a-1). No manifest, scanner,
schema, CLI, scoring, or runtime implementation is authorized by this document.
Re-embedding is Phase 3b and is explicitly out of scope.

This revision applies five approved changes: a score cap of 25 without verified
restore evidence, an optional attested weight digest, sharded JSONL vector
files, a `deleted_by_policy` source status, and an attested model license.

## Objective

Phase 3a answers two narrower questions without calling an embedding API:

1. Can every stored vector be traced to retained source text whose content
   still matches the vector record?
2. Is the declared embedding model portable enough to reproduce locally, or
   would migration require a different model and a potentially expensive full
   index rebuild?

The scanner verifies local files, hashes, dimensions, counts, and coverage. It
does not verify a vendor's licensing or model availability claim. Model
availability, weight digests, and license text are always operator-declared and
labeled `attested`.

## Exit-manifest reference

The `embeddings` vector in `exit-manifest.v1` gains the evidence state
`embedding_inventory`:

```json
{
  "state": "embedding_inventory",
  "path": "evidence/embedding-portability.json",
  "sha256": "<sha256 of the evidence document>"
}
```

The outer reference retains the existing bounded, project-relative path and
SHA-256 checks. Other vector entries remain compatible and unchanged.

The evidence document keeps `schema_version: embedding-portability.v1`. The
version is not bumped because no implementation has shipped it.

## Evidence contract

The referenced document uses `embedding-portability.v1` and contains one or
more vector stores. A store declares its vectors in exactly one of two layouts.

### Single-file layout

Valid for small stores. Every vector file is deterministic JSON with exactly one
`values` array of finite numbers.

```json
{
  "schema_version": "embedding-portability.v1",
  "stores": [
    {
      "store_id": "support-memory",
      "embedding_model": {
        "id": "portable-hash-v1",
        "revision": "1",
        "dimensions": 8,
        "availability": "open_weight_self_hostable",
        "availability_verification": "attested",
        "weights_sha256": "<optional attested digest of the model weights>",
        "license": "<optional attested license identifier or text>"
      },
      "vectors": {
        "layout": "single_file",
        "records": [
          {
            "record_id": "procedure-password-reset",
            "vector": {
              "path": "vectors/procedure-password-reset.json",
              "sha256": "<sha256 of the vector file>"
            },
            "source_text_sha256_in_vector_record": "<source hash stored with the vector record>",
            "source_text": {
              "status": "retained",
              "path": "source/procedure-password-reset.txt",
              "sha256": "<sha256 of the source text bytes>"
            }
          }
        ]
      }
    }
  ]
}
```

### Sharded JSONL layout

Valid for larger stores. Each shard is a JSONL file whose every non-empty line
is one JSON object carrying the record identifier, the source hash recorded with
the vector, and the vector values.

```json
{
  "vectors": {
    "layout": "sharded_jsonl",
    "shards": [
      {
        "path": "vectors/shard-0001.jsonl",
        "sha256": "<sha256 of the shard file bytes>",
        "record_count": 2
      }
    ],
    "source_text": [
      {
        "record_id": "procedure-password-reset",
        "source_text": {
          "status": "retained",
          "path": "source/procedure-password-reset.txt",
          "sha256": "<sha256 of the source text bytes>"
        }
      }
    ]
  }
}
```

One shard line:

```json
{"record_id": "procedure-password-reset", "source_text_sha256": "<hash>", "values": [1, 0, 0, 0, 0, 0, 0, 0]}
```

Shards are hashed over their exact file bytes and then parsed as a stream, one
line at a time, so a large store is never loaded whole. A shard whose
recomputed digest differs from its declaration invalidates the entire store;
the scanner does not accept the surviving shards as a partial inventory. A
shard whose parsed record count differs from `record_count` is invalid. A
`record_id` repeated within or across shards is invalid. Every shard line must
carry a `values` array whose length equals the store's declared `dimensions`
and whose members are finite numbers.

The `source_text` list is keyed by `record_id`. Every vector record must have
exactly one matching source-text entry and every source-text entry must match a
vector record; any unmatched identifier on either side is invalid evidence.

### Source-text status

`source_text.status` is exactly one of:

| Status | Meaning | Coverage effect | Verification |
|---|---|---|---|
| `retained` | Local source bytes exist and are referenced by path and digest. | Counts toward coverage when both digests match. | Scanner verified: the bytes are hashed. |
| `missing` | Source text is not retained. | Counts against coverage. | Scanner verified by absence of a reference. |
| `deleted_by_policy` | Source text was deliberately deleted under a retention or privacy policy. | Excluded from coverage entirely. | **Attested.** The scanner cannot distinguish a policy deletion from an accidental loss. |

`deleted_by_policy` is an operator declaration. The scanner sees only that no
source reference was supplied, so the report labels every
`deleted_by_policy` count and the coverage derived from it as attested, never
as verified.

A `retained` entry supplies `path` and `sha256`. A `missing` entry supplies
neither. A `deleted_by_policy` entry may supply a bounded free-text `reason`
and supplies no path or digest.

`source_text_sha256_in_vector_record` (single-file layout) and
`source_text_sha256` (shard lines) may retain the historical digest for a
`missing` or `deleted_by_policy` record. A digest alone is not source text and
does not make re-embedding possible.

Every retained source file is local UTF-8 text. The scanner hashes its exact
bytes and requires both the evidence reference and the hash recorded with the
vector to match. This detects a vector record that points at different source
content even when every outer evidence digest has been updated.

### Model fields

`id`, `revision`, `dimensions`, `availability`, and
`availability_verification` are required and non-empty. `dimensions` is a
bounded positive integer. `availability` is exactly one of:

- `open_weight_self_hostable`
- `vendor_only`

`availability_verification` must be `attested`. The scanner validates that the
declaration is present but does not convert it into verified evidence.

`weights_sha256` is optional and, when present, is a lowercase 64-character
SHA-256 string. It is **attested only**. The scanner never downloads, hashes,
or otherwise confirms model weights. Its purpose is to let an operator pin the
exact weights a future re-embedding run must use.

`license` is optional and, when present, is a bounded attested string. It is
reported and never scored. The report states that it is an operator
declaration, is not verified, and is not legal advice.

## Coverage calculation

Coverage is scanner-computed, not trusted from an operator percentage:

```text
coverage = retained and hash-matched records / (total records - deleted_by_policy records) * 100
```

The scanner enforces the counting invariant:

```text
retained + missing + deleted_by_policy == total valid vector records
```

A store whose counts do not reconcile is invalid evidence, not a low score.

The report includes the retained count, missing count, `deleted_by_policy`
count, total count, and coverage percentage for every store. Percentages are
rendered with at most two decimal places and are derived from integer counts to
avoid false precision. A store with no vector records is invalid evidence
rather than 100% coverage.

When every record is `deleted_by_policy` the denominator is zero. Coverage is
then reported as null and the store is `re_embeddable: not_applicable`. Such a
store is excluded from the worst-store aggregation because a deliberate
retention decision is not vendor lock-in, and the report must state the full
record count and the policy-deletion count so the exclusion is visible rather
than silent. If every store in the document is `not_applicable`, the embeddings
vector itself is reported as inapplicable with no score, using the report's
existing applicability flag.

**Accepted risk.** This rule means an operator who deletes all source text
receives no lock-in score for embeddings instead of 100. The alternative,
scoring a fully deleted store 100, would attribute the operator's own retention
policy to the vendor. The design accepts the visible exclusion and compensates
with the attested labelling, the majority warning, and the retained-vector
finding below.

### Attested-deletion warning

When `deleted_by_policy` records are a majority of a store, so

```text
deleted_by_policy * 2 > total vector records
```

the store emits a warning stating that its coverage depends on attested
deletions that the scanner cannot verify. The all-deleted case satisfies this
condition and always carries the warning. The warning appears in both Markdown
and JSON output and does not change the score.

### Retained-vector finding

For every `deleted_by_policy` record whose vector record is still present in
the inventory, the store emits the finding `vector retained after source
deletion`. Under this contract every record is enumerated by its vector, so the
finding reports each policy-deleted record whose vector was kept.

The finding is reported and never scored. It exists because a vector derived
from deleted source text may still carry information about that text, which is a
retention and privacy question for the operator rather than a vendor lock-in
measurement. The finding carries the store ID and the affected record count.
JSON additionally lists up to 20 affected record identifiers with a truncation
flag; it never prints source text or vector values.

## Restore linkage

A score of 0 requires Phase 2 restore evidence that the scanner itself re-ran
and that commits to this exact store. `restore-summary.v1` gains one optional
block:

```json
{
  "embedding_stores": [
    {
      "store_id": "support-memory",
      "store_evidence_sha256": "<sha256 of the embedding-portability evidence document>"
    }
  ]
}
```

The field is optional and additive, so existing restore summaries remain valid
and simply cannot reach a score of 0. `restore-summary.v1` is not renamed. An
older installed suite would reject a newer summary carrying the block; both
artifacts are pre-release and are coordinated in the Phase 7 release order.

The link is accepted only when all of the following hold:

1. The manifest's `embeddings` vector declares `embedding_inventory`, and a
   `restore_tested` entry supplies a `restore-summary.v1` record.
2. `ai-suite exit-report --verify-restores` ran, rebuilt the fake profiles, and
   the embeddings asset row passed. An attested-only restore record is not
   sufficient.
3. The verified summary lists an `embedding_stores` entry whose `store_id`
   equals this store's `store_id`.
4. That entry's `store_evidence_sha256` equals the actual SHA-256 of the
   evidence-document bytes the manifest references.

A matching `store_id` with a differing `store_evidence_sha256` is a name match
against different content. It never earns 0; the store stays at 25 and the
reason names the digest mismatch. The identifier selects which claim to check;
the digest is what binds the claim to content.

**Approved scope.** Option A: the `linux-ai-repo` restore demo adopts the block
so a score of 0 is reachable end to end in the real demo rather than only in
fixtures. The demo's `portable-embeddings.v1` asset carries no `store_id`
today, and adding one changes that asset's digest, the bundle manifest, the
source bundle digest, all six profile-record digests, the restore-summary
digest, and the suite fixtures that embed them.

The adoption lands as two separate commits:

1. **Runner change.** `portable-embeddings.v1` accepts an optional `store_id`
   together with a required companion `store_evidence_sha256`, and the runner
   emits `embedding_stores` when they are present. With neither field in the
   bundle the block is omitted, so this commit changes no digest and every
   existing test stays green.

   The two fields are required together. The evidence document the digest
   refers to lives outside the restore bundle, so the runner cannot compute it
   and must relay an operator declaration; a `store_id` with no digest would
   name a claim without binding it to any content, which is exactly the case
   the scoring rules refuse to count. Declaring one field without the other is
   therefore an error, not a partial claim.
2. **Digest regeneration.** The demo bundle declares its `store_id` and every
   affected digest and fixture is regenerated from the runner's own output.

Both commits must leave the complete Phase 2d suite green, including the
per-profile and per-hop corruption attribution tests, the unattributed
behaviour-drift tests, the adapter-swap and wrong-dimension failures, and the
repeated-run byte comparison. A regenerated digest must never be hand-edited:
it comes from running the demo.

## Re-embeddable status and scoring

Each store receives an independent result:

| Source coverage | Model availability | Verified restore link | Re-embeddable | Lock-in score | Reason |
|---:|---|---|---|---:|---|
| 0% | either | any | `no` | 100 | No source text is available; re-embedding cannot reproduce the index. |
| More than 0% but less than 100% | either | any | `partial` | 75 | Only the retained subset can be re-embedded. |
| 100% | `vendor_only` | any | `yes` | 50 | Source is complete, but migration requires a replacement model and full index rebuild; cost and quality may change. |
| 100% | `open_weight_self_hostable` | absent or unverified | `yes` | 25 | Source is complete and the attested model is self-hostable: a validated export with a compatible importer. No restore of this store was verified. |
| 100% | `open_weight_self_hostable` | verified, matching `store_id` and evidence digest | `yes` | 0 | Source is complete, the attested model is self-hostable, and the scanner re-ran a restore that commits to this store's evidence digest. |
| n/a, every record `deleted_by_policy` | either | any | `not_applicable` | none | Source text was deleted under policy; the store is excluded from aggregation and the counts are reported. |

A `vendor_only` model never reaches 0 even with a verified restore. Restoring
copied vectors does not demonstrate that the index can be rebuilt with a model
the operator cannot host.

When `availability` is `open_weight_self_hostable` and `weights_sha256` is
absent, the reason must add that the exact weights are not pinned and that
re-embedding may not reproduce identical vectors. This text is required at both
25 and 0. It does not change the score.

The score measures migration lock-in, not embedding quality. A score of zero
does not certify the model, weights, license, runtime, or numerical
equivalence.

For multiple stores, the embeddings vector uses the highest per-store lock-in
score, excluding `not_applicable` stores, so one portable store cannot hide
another locked store. Aggregate `re-embeddable` is computed over the same
scored stores:

- `yes` when every scored store is `yes`;
- `no` when every scored store is `no`;
- `partial` for every mixed result or when any scored store is `partial`;
- `not_applicable` when no store is scored.

## Exit-report output

The embeddings vector row adds:

- aggregate `re_embeddable`: `yes`, `no`, `partial`, or `not_applicable`;
- the worst per-store score across scored stores;
- a reason naming the limiting store and source-coverage condition, the
  unpinned-weights note when it applies, and the restore-link outcome;
- verification text that distinguishes scanner-verified content from attested
  model availability, weight digest, and license.

A top-level `embedding_stores` section preserves per-store evidence:

- store ID;
- model ID and revision;
- dimensions;
- model availability and `availability_verification: attested`;
- `weights_sha256` presence and value when supplied, labeled attested;
- `license` when supplied, labeled attested;
- vector layout (`single_file` or `sharded_jsonl`) and shard count;
- vector count;
- retained, missing, and `deleted_by_policy` counts, which must sum to the
  vector count, with the `deleted_by_policy` count labeled attested;
- source-text coverage percentage, or null;
- warnings, including the attested-deletion majority warning;
- findings, including `vector retained after source deletion` with its
  affected record count;
- restore-link state: `verified`, `absent`, `unverified`, or
  `store_id_matched_digest_mismatch`;
- `re_embeddable` result;
- lock-in score and reason.

Markdown and JSON output show the same facts. Reports never print retained
source text, vector values, shard lines, or license text beyond the bounded
declared string.

## Negative tests

Required risk-outcome tests use otherwise valid evidence:

1. Missing source text produces 0% coverage, `re_embeddable: no`, and score
   100.
2. Partial source retention produces the exact scanner-computed coverage,
   `re_embeddable: partial`, and score 75.
3. Full coverage with an `open_weight_self_hostable` model and no restore
   evidence produces score 25, not 0.
4. Full coverage with an `open_weight_self_hostable` model and a verified
   restore whose `store_id` and `store_evidence_sha256` both match produces
   score 0.
5. A verified restore whose `store_id` matches but whose
   `store_evidence_sha256` differs produces score 25 and a reason naming the
   digest mismatch.
6. An `open_weight_self_hostable` model with no `weights_sha256` produces a
   reason stating that weights are not pinned and re-embedding may not
   reproduce identical vectors.
7. A sharded store with one corrupted shard is rejected as invalid evidence;
   the uncorrupted shards do not produce a partial inventory or a score.
8. A store mixing `retained`, `missing`, and `deleted_by_policy` reports all
   three counts, excludes the deleted records from coverage, computes coverage
   over the remaining records, and never penalizes the deleted records.
9. Full coverage with a `vendor_only` model and a verified matching restore
   link still produces score 50.
10. A store whose `deleted_by_policy` records are a majority emits the
    attested-deletion warning, and a store whose deletions are a minority does
    not.
11. A store with `deleted_by_policy` records whose vectors are still present
    emits the `vector retained after source deletion` finding with the correct
    affected count, and the finding changes no score.
12. The report labels the `deleted_by_policy` count as attested and never as
    verified.

Required validation tests confirm that the scanner rejects invalid evidence
and the CLI exits with input-error status instead of producing a trusted score:

1. Retained source-text bytes do not match the hash recorded with the vector.
2. The embedding model ID is missing or empty.
3. A vector-file or shard digest does not match.
4. A vector dimension differs from the store declaration, in either layout.
5. Store IDs or record IDs are duplicated, including a `record_id` repeated
   across two shards.
6. A shard's parsed record count differs from its declared `record_count`.
7. The counting invariant fails, so retained plus missing plus
   `deleted_by_policy` does not equal the vector count.
8. A source-text entry has no matching vector record, or a vector record has no
   matching source-text entry.
9. A `retained` entry omits its path or digest, or a `missing` or
   `deleted_by_policy` entry supplies one.
10. `weights_sha256` or `license` is present but malformed or oversized.
11. JSON keys are duplicated, vector values are non-finite, files are
    oversized, shard lines are overlong, store counts, shard counts, record
    counts, or dimensions exceed limits, or paths use traversal, links, or
    Windows reparse points.

A restore summary with no `embedding_stores` block is not an error. It caps the
score at 25 and the reason says the restore evidence does not name this store.

## Resource and privacy boundaries

- Evidence and referenced files are local only; URLs and remote loading are
  unsupported.
- Inputs use bounded reads after file-size checks. Shards are streamed line by
  line with a bounded maximum line length.
- Paths are project-relative and reject traversal, absolute paths, links, and
  reparse points.
- Store count, shard count, record count, vector dimensions, vector-file size,
  shard-file size, source text size, and declared string lengths are bounded
  before expensive processing.
- Duplicate JSON keys and duplicate identifiers are rejected.
- Inputs are never modified.
- Source text, vector values, and shard contents remain local and are omitted
  from reports.
- No package import, provider SDK, Ollama probe, HTTP request, model download,
  embedding call, or arbitrary code execution occurs.

## Compatibility

Existing `embeddings` evidence states remain readable. Only
`embedding_inventory` receives Phase 3a's structured checks and scoring.
Portable vectors used by the Phase 2 restore demo remain labeled `vectors
copied (same model), not re-embedded`; Phase 3a describes their portability but
does not regenerate them.

The model availability, weight digest, and license claims are portable, offline
operator contracts, not live integrations. Hash, dimension, path, count,
coverage, and restore-link digest checks are scanner verified. The report must
keep those verification levels separate.

## Approval boundary

After approval, implementation may update the AI Infrastructure Suite manifest,
restore-summary, and report schemas, the scanner, CLI output, fixtures, tests,
and documentation. Under option A above it may also update the `linux-ai-repo`
restore demo's portable embedding asset, runner, bundle digests, and affected
fixtures. It must remain on `feature/vendor-exit-evidence`, use the current
package versions, add no runtime dependency, and create local commits only.
Phase 3b re-embedding remains deferred.

Checkpoints: 3a-1 is this document. 3a-2 is schemas, scanner, and fixtures with
tests. 3a-3 is report output, documentation, and the full matrix. Every
checkpoint runs the package tests, Ruff lint, Ruff format, strict mypy, and
Bandit on Python 3.11, 3.12, and 3.13.
