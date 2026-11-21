# Phase 7 release plan

Status: planning only. This document does not authorize version changes,
tags, pushes, package publication, or a CI bypass.

## Feature-branch inventory

The following repositories have commits on `feature/vendor-exit-evidence`
relative to `main`.

| Repository | Feature commits | Current version | Phase 7 version | Release action |
|---|---|---:|---:|---|
| AgentForge | `6b0fbd6` | `0.5.4` | No bump | Merge the `.gitignore` change after CI. It does not change the distribution, so do not publish an otherwise identical `agentforge-oss` artifact. |
| AIAuditLog | `0f43ec4` | `0.2.0b1` | `0.2.0b2` | Publish the bounded privacy-profile loading fix and regression test. |
| OpenOntologyLite | `63b89cc` | `0.2.0b2` | `0.2.0b3` | Publish the lossless OpenOntologyLite JSON-LD transfer and round-trip API used by restore verification. |
| ModelSwapBench | `52e6a71` | `0.1.0b1` | `0.1.0b2` | Publish explicit Ollama opt-in and the unintended-network regression test. |
| AI Infrastructure Suite | `9007a8f`, `18ef614`, `ea9db42`, `08879be`, the Phase 2 close-out commits, plus Phase 3a `5efbf3e`, `c5c5745`, `792ebed` | `0.1.0b1` | `0.1.0b2` | Publish the 11-vector exit report, restore-summary verification, profile-level drift reporting, embedding lock-in detection, schemas, CLI mode, and tests after its dependencies are available. |
| linux-ai-repo | `e101fda`, `5585f77`, `3fe3d9f`, `7cff992`, `42d1c0e`, the Phase 7 planning commit, plus Phase 3a `c67f5f9`, `974a2d5`, `bb25459`, `41e2fa9`, `abe7ce7` | Not packaged | No bump | Merge the demos, evidence contracts, embedding evidence, documentation, and CI workflow after the released OpenOntologyLite pin replaces the temporary branch checkout. |

AgentPolicyPack, AIMeter OSS, and PrivateAIStack do not have commits on this
feature branch and require no Phase 7 version bump for this work.

## restore-summary.v1 forward compatibility

Phase 3a adds an optional `embedding_stores` block to `restore-summary.v1`
without renaming the schema, because no implementation had shipped the block
and existing summaries stay valid without it.

The compatibility is one-directional. A restore summary produced by the updated
`linux-ai-repo` demo carries `embedding_stores`, and the schema sets
`additionalProperties: false`, so an **older installed**
`ai-infrastructure-suite==0.1.0b1` rejects that newer summary as invalid input
rather than ignoring the unknown block. Both artifacts are pre-release, and the
publication order below already releases the suite after the umbrella work, so
no released pair is affected.

Two consequences for Phase 7:

1. Release `ai-infrastructure-suite==0.1.0b2` before advertising the updated
   restore summary, and keep the umbrella merge last so the newer summary never
   reaches an older installed suite.
2. State in the suite changelog that `0.1.0b2` is required to read a restore
   summary containing `embedding_stores`.

## OpenOntologyLite dependency floor is now load-bearing

Phase 3a verified this by installing the suite wheel outside any checkout.
Ontology verification needs the OpenOntologyLite JSON-LD transfer API, which
the released `openontologylite==0.2.0b2` does not provide, so with that
version `ai-suite exit-report --verify-restores` cannot check the ontology
vector at all. It now exits 2 naming `openontologylite>=0.2.0b3` rather than
printing a traceback, but the check still cannot run.

The existing publication order already handles this, since `openontologylite`
is released before the suite. Two things must not be skipped:

1. Raising the suite's floor to `openontologylite>=0.2.0b3,<0.3.0` (already
   listed below) is a correctness requirement, not housekeeping. Releasing
   `ai-infrastructure-suite==0.1.0b2` against the `0.2.0b2` floor would ship a
   suite whose restore verification cannot complete on a clean install.
2. The release gate for the suite must install the wheel into a fresh
   environment outside the checkout and run `exit-report --verify-restores`
   end to end, not only `exit-report`. A sibling checkout on `sys.path` hides
   this failure completely.

## Phase 3a additions to the suite release

`ai-infrastructure-suite==0.1.0b2` now also publishes embedding lock-in
detection. Three things follow for its release gate.

- A new packaged schema, `embedding-portability.schema.json`, must be present
  in both the wheel and the sdist, alongside the four existing schemas.
- The new `docs/examples/embedding-portability/` fixture must resolve through
  `importlib.resources` from the installed package, the way the existing
  example does.
- `exit-report` output gained a top-level `embedding_stores` section and two
  `verification_level` values, `verified (local evidence)` and
  `verified (local evidence + fake profiles)`. A consumer pinned to
  `0.1.0b1`'s `exit-report.v1` schema will reject a report containing them,
  because that schema sets `additionalProperties: false` and constrains the
  level enum. This is the same one-directional compatibility as
  `restore-summary.v1` below: no released pair is affected, since both
  artifacts are pre-release, but the changelog must state that reading a
  report with an embedding inventory requires `0.1.0b2`.

The umbrella repository has no package version and gains no release step from
Phase 3a. Its demo now declares a vector store in the restore bundle and
carries derived evidence under `examples/restore-demo/evidence/`, which the
existing merge step covers.

## Publication order

Every repository must pass its complete configured Python 3.11-3.13 CI before
its release tag is created. Trusted Publishing must use the existing GitHub
OIDC workflow; no API token or manual artifact upload is part of this plan.

1. Merge AgentForge commit `6b0fbd6` after CI. Do not tag or publish because the
   package contents and runtime are unchanged.
2. Prepare, verify, tag, and publish `aiauditlog==0.2.0b2`.
3. Prepare, verify, tag, and publish `openontologylite==0.2.0b3`.
4. Prepare, verify, tag, and publish `modelswapbench==0.1.0b2`.
5. Update the AI Infrastructure Suite dependency floors listed below. Prepare,
   verify, tag, and publish `ai-infrastructure-suite==0.1.0b2` only after the
   three exact dependency releases install successfully from PyPI.
6. Replace linux-ai-repo's temporary feature-branch checkout with the released
   OpenOntologyLite pin, run its Python 3.11-3.13 workflow, and merge it. This
   repository has no package publication step.

Release steps 2-4 are independent at runtime, but the fixed sequence makes the
evidence trail and rollback point unambiguous. AI Infrastructure Suite remains
last among packages because it consumes all three releases.

## Required version and dependency changes

### AIAuditLog

- Change package and public version references from `0.2.0b1` to `0.2.0b2`.
- Do not change dependency floors for this fix.

### OpenOntologyLite

- Change package and public version references from `0.2.0b2` to `0.2.0b3`.
- Do not add an AI Infrastructure Suite dependency; JSON-LD remains an
  independently usable OpenOntologyLite API.

### ModelSwapBench

- Change package and public version references from `0.1.0b1` to `0.1.0b2`.
- Keep `agentforge-oss>=0.5.1,<0.6.0`. The Ollama opt-in change does not depend
  on the AgentForge `.gitignore` commit or a new AgentForge package.

### AI Infrastructure Suite

- Change package and public version references from `0.1.0b1` to `0.1.0b2`.
- Raise `aiauditlog>=0.2.0b1,<0.3.0` to
  `aiauditlog>=0.2.0b2,<0.3.0` in `core`, `privacy`, and `all`.
- Raise `openontologylite>=0.2.0b2,<0.3.0` to
  `openontologylite>=0.2.0b3,<0.3.0` in `core`, `privacy`, and `all`. This one
  is a correctness requirement; see the dependency-floor section above.
- Raise `modelswapbench>=0.1.0b1,<0.2.0` to
  `modelswapbench>=0.1.0b2,<0.2.0` in `benchmarking` and `all`.
- Keep `agentforge-oss>=0.5.4,<0.6.0` unchanged because Phase 7 does not publish
  a new AgentForge artifact.
- Keep AgentPolicyPack, AIMeter OSS, and PrivateAIStack pins unchanged.

### AgentForge and linux-ai-repo

- AgentForge remains `0.5.4`; no tag or package publication is needed.
- linux-ai-repo has no package version.

## CI reference switch

During Phase 2, `.github/workflows/offline-demos.yml` checks out
OpenOntologyLite at `feature/vendor-exit-evidence`. After
`openontologylite==0.2.0b3` is published and independently installable, Phase 7
must:

1. Remove the OpenOntologyLite repository checkout step and its mutable Git
   branch reference.
2. Remove `OpenOntologyLite/pyproject.toml` from the pip cache key.
3. Install exactly `openontologylite==0.2.0b3` from PyPI in the workflow.
4. Run the restore-demo and vendor-exit-demo tests, Ruff, strict mypy, and
   Bandit on Python 3.11, 3.12, and 3.13. The suite-dependent exit-report demo
   keeps its own `mypy --strict --ignore-missing-imports` step, because this
   workflow does not install the suite and its five scanner tests skip.
5. Confirm the ontology round trip resolves from installed `site-packages`, not
   from a sibling checkout.

After the umbrella workflow is green against the released dependency, normal
maintenance may widen the exact CI test pin to the declared compatible range.
The release-validation commit itself should retain the exact pin for
reproducibility.

## Release gates

For every package release, verify the version, changelog, metadata, wheel,
sdist, Twine validation, isolated wheel and sdist installs, CLI/import smoke
tests, artifact scans, and the configured lint, formatting, typing, security,
audit, and test checks. Confirm Trusted Publishing and PyPI installation before
moving to the next dependent release. Never reuse a failed or already-published
version, bypass branch protection, force-push, or claim a live integration that
was not exercised.
