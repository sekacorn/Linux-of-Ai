# Three-profile restore demo design

Status: Phase 2a design proposal. No restore runner or exit-report verification is implemented yet.

## Purpose

The restore demo will show whether a portable, local vendor-exit bundle can be restored into three provider-shaped profiles without changing the bundle's governed behavior. It is an offline portability test, not proof that a real cloud migration, disaster-recovery process, or provider contract will behave the same way.

The demo runs both a fan-out and a chained migration. In the fan-out, the source bundle is restored independently into each profile, so a successful earlier run cannot hide an incomplete later restore. The chain is `source -> mock-azure -> export -> mock-aws -> export -> local-ollama`; it applies the content and behavior gates at every hop and compares every re-export with the original bundle.

## Provider profiles

| Profile | Default execution | Network behavior | Intended boundary |
|---|---|---|---|
| `mock-azure` | Deterministic fake Azure-shaped provider | No network access | Exercises provider-specific configuration and response normalization without Azure credentials or services. |
| `mock-aws` | Deterministic fake AWS-shaped provider | No network access | Exercises a distinct provider adapter and response envelope without AWS credentials or services. |
| `local-ollama` | Deterministic fake Ollama-shaped provider | No network access | Exercises local-provider configuration and normalized behavior. A real local Ollama request is allowed only with `--live-ollama`. |

The two hosted-shaped profiles never contact hosted services. `--live-ollama` is explicit, is outside the deterministic CI matrix, and may contact only the configured local Ollama endpoint. A live run records that it is live and never masquerades as a fake-provider result.

## Portable bundle

The demo will use a versioned, deterministic bundle under `examples/restore-demo/`. The bundle manifest will list every asset, its schema or media type, its relative path, and its SHA-256 digest. Paths are project-relative; absolute paths, traversal, links, duplicate JSON keys, oversized files, and undeclared files are rejected.

The bundle contains no credentials, provider tokens, personal identity, or live customer data. JSON and JSONL use stable key ordering and LF line endings. Generated records omit wall-clock timestamps or use a fixed fixture time so repeated fake-provider runs produce identical bytes.

## Assets and profile support

| Asset | `mock-azure` | `mock-aws` | `local-ollama` fake | Restore-specific check |
|---|---|---|---|---|
| Policies | Move | Move | Move | The restored policy routes the scripted low-risk task to a draft with human review and blocks a high-risk variant. |
| Prompts | Move | Move | Move | The restored prompt is the prompt used for the scripted task. |
| Memory | Move | Move | Move | The restored memory returns the expected support procedure used by the task. |
| Audit history | Move | Move | Move | Existing events retain order and chain validity; the task adds the expected correlated event. |
| Cost history | Move | Move | Move | Existing records retain their exact decimal values; the task produces the profile's declared deterministic usage record. |
| Ontology | Move | Move | Move | OpenOntologyLite loads and round-trips the JSON-LD export without changing its canonical ontology digest, and the task resolves the expected workload concept. |
| Embeddings | Move when the portable vector store supports the declared model and dimension | Move when the portable vector store supports the declared model and dimension | Move for the fake profile; live support depends on the configured vector store | Retrieval returns the expected memory item with deterministic tie ordering. Results are labeled `vectors copied (same model), not re-embedded`. Unsupported live embeddings are reported as unsupported, never silently regenerated or called restored. |

Fine-tunes, tool connectors, identities, and contract terms are outside this restore demo. Their existing exit-report rows remain governed by their current evidence contracts.

## Definition of restored

An asset is restored only when both gates pass:

1. **Content gate:** the bytes restored into the target profile match the declared SHA-256, or, for a normalized format such as ontology JSON-LD, the canonical content digest matches after load and serialization.
2. **Behavior gate:** the restored profile runs the common scripted agent task and returns the exact expected normalized result. The run also performs the asset-specific assertion in the table above.

The common scripted task is a fictional, low-risk internal password-reset support request. Its normalized expected result is a versioned JSON object containing the expected action, human-review requirement, policy decision, retrieved procedure identifier, and final response identifier. Fake providers must use different provider-shaped request and response envelopes. Their tool-call format, stop-reason shape, token counting fields, and native embedding dimensions are distinct, but normalization must produce the same expected result. A provider adapter that is bypassed or paired with the wrong profile must fail.

Portable vectors are not generated by those native embedding APIs. They retain one declared model, dimension, and byte representation through every hop. This proves copying and portable vector-store compatibility, not re-embedding or semantic equivalence between provider embedding models. A copied vector whose length differs from its declared dimension fails the content/behavior gates.

Retrieval runs inside the demo's portable vector store over the copied
`portable-hash-v1` vectors. It does not pass those vectors to a provider-native
embedder. The separate native embedding call receives only the scripted task
text and checks the adapter's declared 4-, 6-, or 8-dimensional response. The
portable store currently declares dimension 8 support for all three fake
profiles; a profile that does not declare that copied dimension fails before
retrieval rather than silently sending the vectors to its native embedder.

A content match without the behavior gate is not restored. A behavioral match produced from undeclared or mismatched content is not restored. A profile passes only when every supported required asset passes both gates.

## Demo flow

The proposed command is:

```text
python examples/restore-demo/run_restore_demo.py --output PATH
```

The runner will:

1. Validate the portable bundle and all declared digests before constructing a provider.
2. Create an empty profile-specific restore directory.
3. Restore only declared assets with bounded, non-linking file operations.
4. validate the restored content independently of the source validation.
5. Construct the profile's deterministic fake provider and agent.
6. Run the common scripted task and asset-specific checks.
7. Re-export the restored assets and compare their digests with the input bundle.
8. Repeat independently for fan-out and in order for the chained migration.
9. Write one profile restore record and a deterministic aggregate restore record.
10. Exit nonzero if any required content, behavior, or re-export check fails.

`--live-ollama` changes only the `local-ollama` provider. It requires explicit endpoint and model configuration, records the endpoint hosting mode, applies finite connect/read timeouts, and never falls back silently to the fake after a live failure.

## Restore record contract

Each profile emits `restore-profile-record.v1` with:

- profile and provider mode (`fake` or `live`)
- bundle schema version and bundle digest
- runner version and reproducibility settings
- supported, unsupported, passed, and failed assets
- for each asset: declared digest, restored digest, content result, behavior result, and failure reason
- scripted task ID, expected-result digest, actual-result digest, and behavior result
- aggregate pass/fail status
- deterministic record digest
- machine sign-off stating that the runner completed every declared check

The machine sign-off is integrity metadata, not a person, legal signature, certificate, or external attestation. It contains no personal identity. The three profile records are referenced by `restore-summary.v1`, which also has a deterministic digest and is the artifact consumed by `ai-suite exit-report`.

## Exit-report verification model

An operator-supplied `restore-summary.v1` whose outer digest matches remains `attested`. A producer string inside the record is not trusted.

`ai-suite exit-report` will gain an explicit restore verification mode. During that invocation it will validate the bundle, reconstruct each fake profile in a temporary directory, rerun the scripted task and asset checks, and compare its results with the referenced records. Only asset rows successfully rechecked by the scanner become `verified (fake profiles)` with the `restore_tested` score.

The existing `exit-manifest.v1` behavior remains compatible. Restore evidence uses `state: restore_tested`; the vector name selects the corresponding asset row from the summary. Ontology restore evidence receives the same content and behavioral checks rather than relying only on its current importer check. Contract terms remain `attested` and are not affected by restore verification.

If verification is not requested or the scanner cannot run the verifier, a valid record remains `attested`. The report states why it was not independently checked.

If the scanner runs the verifier and detects corruption or behavior drift, the affected vector is reported as a verified restore failure with a conservative lock-in score and a specific reason. It is not silently converted into success, and unaffected vectors retain their own results.

## Negative tests

For each profile, tests will corrupt one restored asset after record creation. The runner must exit nonzero and name the profile and asset. Exit-report verification must detect the mismatch, downgrade that vector, and preserve the results of unaffected vectors. Tests also replace a profile adapter with another profile's adapter and supply a vector with the wrong dimension; both operations must fail loudly.

Additional tests cover behavior drift with unchanged content, unsupported embeddings, duplicate JSON keys, oversized input, path traversal, links or Windows reparse points, deterministic repeated runs, fake-provider network isolation, and failure of live Ollama without fallback.

## Verification plan

The fake-provider demo and its tests run on Python 3.11, 3.12, and 3.13. Required checks are Ruff lint, Ruff formatting, strict mypy, Bandit, the existing package tests, the umbrella quickstart checks, repeated-run byte comparison, and artifact safety scans.

Live Ollama is optional manual evidence. It is never required for CI and is reported separately from the deterministic fake-provider matrix.

## Non-goals

This phase does not claim a real Azure or AWS integration, cloud restore, legal portability, provider equivalence, production disaster recovery, cryptographic signer identity, or deterministic live-model output. It does not change package versions, publish packages, or contact PyPI.
