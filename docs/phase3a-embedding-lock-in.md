# Phase 3a embedding lock-in detection design

Status: design for approval. No manifest, scanner, schema, CLI, scoring, or
runtime implementation is authorized by this document. Re-embedding is Phase
3b and is explicitly out of scope.

## Objective

Phase 3a answers two narrower questions without calling an embedding API:

1. Can every stored vector be traced to retained source text whose content
   still matches the vector record?
2. Is the declared embedding model portable enough to reproduce locally, or
   would migration require a different model and a potentially expensive full
   index rebuild?

The scanner verifies local files, hashes, dimensions, counts, and coverage. It
does not verify a vendor's licensing or model availability claim. Model
availability is always operator-declared and labeled `attested`.

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

## Evidence contract

The referenced document uses `embedding-portability.v1` and contains one or
more vector stores:

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
        "availability_verification": "attested"
      },
      "records": [
        {
          "record_id": "procedure-password-reset",
          "vector": {
            "path": "vectors/procedure-password-reset.json",
            "sha256": "<sha256 of the vector file>"
          },
          "source_text": {
            "path": "source/procedure-password-reset.txt",
            "sha256": "<sha256 of the source text bytes>"
          },
          "source_text_sha256_in_vector_record": "<source hash stored with the vector record>"
        }
      ]
    }
  ]
}
```

`source_text` is `null` when the original source is not retained. In that case,
`source_text_sha256_in_vector_record` may retain the historical digest, but a
digest alone is not source text and does not make re-embedding possible.

Every vector file is deterministic JSON with exactly one `values` array of
finite numbers. The scanner hashes the file bytes, parses the array, and checks
its length against the store's declared dimensions. It never sends the vector
to a provider-native embedder.

Every retained source file is local UTF-8 text. The scanner hashes its exact
bytes and requires both the evidence reference and
`source_text_sha256_in_vector_record` to match. This detects a vector record
that points at different source content even when every outer evidence digest
has been updated.

The model fields are required and non-empty. `dimensions` is a bounded positive
integer. `availability` is exactly one of:

- `open_weight_self_hostable`
- `vendor_only`

`availability_verification` must be `attested`. The scanner validates that the
declaration is present but does not convert it into verified evidence.

## Coverage calculation

Coverage is scanner-computed, not trusted from an operator percentage:

```text
retained and hash-matched source records / valid vector records * 100
```

The report includes the retained count, total count, and coverage percentage
for every store. Percentages are rendered with at most two decimal places and
are derived from integer counts to avoid false precision. An empty store is
invalid evidence rather than 100% coverage.

## Re-embeddable status and scoring

Each store receives an independent result:

| Source coverage | Model declaration | Re-embeddable | Lock-in score | Reason |
|---:|---|---|---:|---|
| 0% | either | `no` | 100 | No source text is available; re-embedding cannot reproduce the index. |
| More than 0% but less than 100% | either | `partial` | 75 | Only the retained subset can be re-embedded. |
| 100% | `vendor_only` | `yes` | 50 | Source is complete, but migration requires a replacement model and full index rebuild; cost and quality may change. |
| 100% | `open_weight_self_hostable` | `yes` | 0 | Source is complete and the operator attests that the same model can be self-hosted. |

The score measures migration lock-in, not embedding quality. A score of zero
does not certify the model, weights, license, runtime, or numerical equivalence.

For multiple stores, the embeddings vector uses the highest per-store lock-in
score so one portable store cannot hide another locked store. Aggregate
`re-embeddable` is:

- `yes` when every store is `yes`;
- `no` when every store is `no`;
- `partial` for every mixed result or when any store is `partial`.

## Exit-report output

The embeddings vector row adds:

- aggregate `re_embeddable`: `yes`, `no`, or `partial`;
- the worst per-store score;
- a reason naming the limiting store and source-coverage condition;
- verification text that distinguishes scanner-verified content from attested
  model availability.

A top-level `embedding_stores` section preserves per-store evidence:

- store ID;
- model ID and revision;
- dimensions;
- model availability;
- `availability_verification: attested`;
- vector count;
- retained source count;
- source-text coverage percentage;
- `re_embeddable` result;
- lock-in score and reason.

Markdown and JSON output show the same facts. Reports never print retained
source text or vector values.

## Negative tests

Required risk-outcome tests use otherwise valid evidence:

1. Missing source text produces 0% coverage, `re_embeddable: no`, and score
   100.
2. Partial source retention produces the exact scanner-computed coverage,
   `re_embeddable: partial`, and score 75.

Required validation tests confirm that the scanner rejects invalid evidence
and the CLI exits with input-error status instead of producing a trusted score:

1. Retained source-text bytes do not match
   `source_text_sha256_in_vector_record`.
2. The embedding model ID is missing or empty.
3. A vector-file digest does not match.
4. A vector dimension differs from the store declaration.
5. Store IDs or record IDs are duplicated.
6. JSON keys are duplicated, vector values are non-finite, files are oversized,
   counts or dimensions exceed limits, or paths use traversal, links, or
   Windows reparse points.

## Resource and privacy boundaries

- Evidence and referenced files are local only; URLs and remote loading are
  unsupported.
- Inputs use bounded reads after file-size checks.
- Paths are project-relative and reject traversal, absolute paths, links, and
  reparse points.
- Store count, record count, vector dimensions, vector-file size, and source
  text size are bounded before expensive processing.
- Duplicate JSON keys and duplicate identifiers are rejected.
- Inputs are never modified.
- Source text and vector values remain local and are omitted from reports.
- No package import, provider SDK, Ollama probe, HTTP request, model download,
  embedding call, or arbitrary code execution occurs.

## Compatibility

Existing `embeddings` evidence states remain readable. Only
`embedding_inventory` receives Phase 3a's structured checks and scoring.
Portable vectors used by the Phase 2 restore demo remain labeled `vectors
copied (same model), not re-embedded`; Phase 3a describes their portability but
does not regenerate them.

The model availability claim is a portable/offline operator contract, not a
live integration. Hash, dimension, path, count, and coverage checks are scanner
verified. The report must keep those verification levels separate.

## Approval boundary

After approval, implementation may update the AI Infrastructure Suite manifest
and report schemas, scanner, CLI output, fixtures, tests, and documentation.
It must remain on `feature/vendor-exit-evidence`, use the current package
versions, and create local commits only. Phase 3b re-embedding remains deferred.
