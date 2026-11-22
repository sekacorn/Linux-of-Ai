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

## Dependabot merge order

Approved order, per repository: merge `feature/vendor-exit-evidence`, publish,
then merge Dependabot. The reason is not conflicts. Every open Dependabot
branch touches only `.github/workflows/`, both feature branches touch only
source, tests and docs, and merge tests in both directions are clean, so the
order is free of conflicts either way. The reason is that these bumps modify
`release.yml`, which is the Trusted Publishing workflow the publication order
below depends on. Changing the publishing path in the same step that uses it
removes the only evidence that the path works.

The cost is carrying slightly older actions for one release. These are version
bumps, not advisories, so that is the cheaper risk.

Open Dependabot state as verified for this plan:

| Repository | Open branches | Notes |
|---|---:|---|
| OpenOntologyLite | 1 | A grouped bump carrying 8 action updates in one commit, current with `main`. Cannot self-conflict. |
| ModelSwapBench | 5 | `download-artifact`, `upload-artifact` and `scorecard-action` are current and mutually independent. `checkout-7.0.1` and `setup-python-7.0.0` are 10 commits behind `main` and conflict **with each other** across four workflows; each is clean against `main` alone, so whichever merges second conflicts. |

Do not hand-resolve that conflict. Rebase the two stale branches, or let the
grouping change below make the conflict impossible.

After the ModelSwapBench release is published, enable `github_actions`
grouping in its `.github/dependabot.yml`, matching what OpenOntologyLite
already does, **as its own commit**. It must not be part of any release
commit, version bump, or feature merge. Grouped action bumps arrive as one
commit and cannot conflict with each other the way the two stale branches do.

## release.yml provenance

Verified for all four packages: `release.yml` is byte-identical between the
commit of each package's last successful PyPI publish and both current `main`
and `feature/vendor-exit-evidence`. No feature branch changes any file under
`.github/`. The workflow about to be used for Phase 7 is the same one that
last published successfully.

| Package | Last published | Tag commit | Last successful `release.yml` run | `release.yml` since then |
|---|---|---|---|---|
| aiauditlog | 0.2.0b1 | `364cb0d` | `364cb0d`, success | unchanged |
| openontologylite | 0.2.0b2 | `279f3b0` | `279f3b0`, success | unchanged |
| modelswapbench | 0.1.0b1 | `59fec14` | `59fec14`, success | unchanged |
| ai-infrastructure-suite | 0.1.0b1 | `4af0486` | `4af0486`, success | unchanged |

Each PyPI release was confirmed present with its upload date, so a successful
workflow run is matched by an actual published artifact rather than assumed.

One historical note that the version plan already respects: an
`openontologylite` 0.2.0b1 release run failed at `7102cc4` and that version is
absent from PyPI. It is a burned version number. Publishing 0.2.0b3 next skips
it correctly, and the release gate forbidding reuse of a failed or published
version must keep 0.2.0b1 out of scope permanently.

## Release triggers and accident surface

Audited at checkpoint 7-1 by reading each `release.yml` and querying each
repository's GitHub environments. The four repositories are **not** symmetric.

| Repository | Trigger | Tag push publishes? | Gate before upload |
|---|---|---|---|
| AIAuditLog | `on: push: tags: ["v*"]` | **Yes** | tag/version equality check only |
| OpenOntologyLite | `on: push: tags: ["v*"]` | **Yes** | tag/version equality check only |
| ModelSwapBench | `on: push: tags: ["v*"]` | **Yes** | tag/version equality check only |
| AI Infrastructure Suite | `on: workflow_dispatch` (`tag` input) | No | manual dispatch, then tag/version equality check |

Every repository gates its publish job on the `pypi` GitHub environment. **No
`pypi` environment in any of the four carries a protection rule**: no required
reviewers, no wait timer, no deployment branch policy. This was queried
directly. The AI Infrastructure Suite workflow's own header comment says the
environment "should carry required reviewers" — it does not.

The consequence is blunt: in three of the four repositories, **pushing a `v*`
tag publishes to PyPI with no further human step.** The suite is protected only
because a tag push cannot start its workflow at all.

Things that could publish by accident:

1. **Pushing the version tag early.** The versions are already bumped locally,
   so a tag matching the new version passes the equality check and publishes
   immediately in three repositories. This is the main risk and the reason
   tagging stays a separate, explicitly approved step.
2. **`git push --tags` or `git push --follow-tags`.** These push tags the
   remote does not have. ModelSwapBench currently has one local-only tag,
   `v0.1.0a1`; it would fail the equality check against `0.1.0b2`, so it would
   produce a failed run rather than a publish, but it would also consume the
   already-published `0.1.0a1` version number in the run history. Push tags
   one at a time by name.
3. **The `v*` pattern is broader than a version.** Any tag beginning with `v`
   starts the workflow. A non-version tag fails the equality check, so it
   cannot publish, but it does start a run.
4. **A merge cannot publish.** No workflow triggers on `push` to a branch, so
   merging the feature branch is safe on its own.

Recommended hardening, not required for this release and not performed:
add required reviewers to each `pypi` environment, and narrow the tag pattern
to `v[0-9]*`. Both are repository settings rather than code.

## Checkpoint 7-1: local preparation

Completed locally. No tag, push, publish, or registry contact beyond read-only
public metadata queries.

| Package | From | To | Distributions | `twine check` |
|---|---|---|---|---|
| aiauditlog | 0.2.0b1 | 0.2.0b2 | wheel + sdist | pass |
| openontologylite | 0.2.0b2 | 0.2.0b3 | wheel + sdist | pass |
| modelswapbench | 0.1.0b1 | 0.1.0b2 | wheel + sdist | pass |
| ai-infrastructure-suite | 0.1.0b1 | 0.1.0b2 | wheel + sdist | pass |

All four were installed at those exact versions into a fresh virtual
environment outside every checkout, from the local wheels only. None of those
versions exists on PyPI, so the installed artifacts are provably the local
ones. From that environment, the restore demo and the vendor-exit demo both
pass, and `ai-suite exit-report --verify-restores` reports the embeddings
vector at **0**, `verified (local evidence + fake profiles)`, with all six fake
profiles passing and `suite_version: 0.1.0b2`.

The suite's artifact scanner reports
`name=ai-infrastructure-suite version=0.1.0b2 author=sekacorn license=Apache-2.0 python=<3.14,>=3.11 script=ai-suite`.

### The openontologylite floor is deferred, deliberately

The suite's `openontologylite` floor was **not** raised to `>=0.2.0b3` at 7-1.
It cannot be, truthfully, before that version is published. Raising it forces a
chain through the suite's own packaged manifest:

1. `test_manifest_ranges_match_requirements` requires the manifest's
   `version_specifier` to equal a `pyproject.toml` requirement, so the manifest
   range must move to `>=0.2.0b3,<0.3.0` too.
2. `test_range_admits_the_declared_minimum` then forces
   `minimum_version` to `0.2.0b3`.
3. `test_minimum_never_exceeds_latest_published` then forces
   `latest_published_version` to `0.2.0b3` — a statement that the version is on
   PyPI, which is false until step 3 of the publication order runs.
4. `test_every_range_admits_its_latest_published_version` fails meanwhile,
   because a `>=0.2.0b3` range excludes the published `0.2.0b2`.

Those tests are correct and must not be weakened. The honest sequence is
therefore the one the publication order below already implies: publish
`openontologylite==0.2.0b3` first, then raise the floor and the three manifest
fields in **one commit**, re-run the full matrix, and only then build and
publish the suite. That commit is listed as step 4a below.

**The suite's pull request stays open until `openontologylite==0.2.0b3` is on
PyPI, and the step 4a commit lands in that same pull request.** This is a
deliberate change from treating 4a as a post-merge commit. Confirmed against a
real CI run on the suite's branch: with the published `0.2.0b2` installed,
strict mypy reports three `attr-defined` errors for the missing JSON-LD names
and every test that touches the ontology path fails, because the API genuinely
is not there. The suite's pull request therefore **cannot go green before step
3 publishes**, and merging it earlier would put a knowingly red commit on
`main`. Keeping 4a inside the pull request means one review sees the floor
raise and the CI run that the floor raise is what fixes.

The jobs that do not exercise the ontology path pass meanwhile — build and
verify artifacts, fresh install from wheel, fresh install from sdist, and the
security scan — so the red is attributable rather than general.

The same deferral applies to the `aiauditlog` and `modelswapbench` floors
listed under required dependency changes. Those two are hygiene rather than
correctness: the suite works against the currently published versions of both.
Raising them is optional and was not requested at 7-1.

## Checkpoint 7-2: TestPyPI is not currently possible

Verified at 7-1: **no release workflow supports TestPyPI**. None of the four
contains a `repository-url`, a `repository_url`, or any reference to
`test.pypi.org`; every publish step targets PyPI implicitly. And none of the
four distributions exists on TestPyPI at all, so no pending publisher can have
been registered there. TestPyPI is a separate registry with its own accounts
and its own Trusted Publishing configuration; a PyPI publisher does not apply
to it.

So 7-2 requires a decision before it can be a step at all:

- **Option A — skip TestPyPI.** Rely on the suite's existing post-publish
  verification, which installs the exact published wheel and sdist from PyPI
  into clean environments and smoke-tests both before the run is considered
  successful. Cost: a defective artifact is permanent, because a PyPI version
  can never be re-uploaded. Cheapest, and the local wheel install at 7-1
  already exercised the same install path.
- **Option B — add TestPyPI support.** Add a `workflow_dispatch` input to each
  `release.yml` selecting the target registry, pass it as `repository-url`, and
  register four pending publishers at `test.pypi.org` under the same owner,
  repository, workflow filename and environment. Cost: a workflow change to
  all four repositories immediately before a release, which is exactly the
  release-path churn the Dependabot ordering above exists to avoid, plus
  four manual account setup steps. Highest confidence, highest churn.
- **Option C — upload to TestPyPI manually** with a TestPyPI API token. This
  contradicts the "no API token is used or referenced anywhere" property the
  workflows document, and reintroduces a long-lived credential. Not
  recommended.

**Recommendation: Option A for this release**, with Option B scheduled as its
own post-release change alongside the Dependabot merges, so the next release
gets a real TestPyPI rehearsal without changing the publishing path during a
publish.

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

## Checkpoint 7-3: exact command sequence

Each numbered block is a separate approval. Nothing below has been run. In
three of the four repositories the `git push origin <tag>` line is the
irreversible step: it publishes, with no further gate. A published version can
never be re-uploaded.

**0. Merge the feature branches (no publish possible).**

```bash
# Per repository. Branch protection may require a PR instead of a direct push.
git -C <repo> push origin feature/vendor-exit-evidence
gh pr create --repo sekacorn/<repo> --base main --head feature/vendor-exit-evidence --fill
# After review and green CI. Note the absence of --delete-branch:
gh pr merge --repo sekacorn/<repo> --merge
```

Never pass `--delete-branch` for OpenOntologyLite, and decline GitHub's
offer to delete the head branch on that merge. Umbrella CI checks that branch
out by name until 7-4. See the branch-retention section below.

The suite's pull request is **not** merged in this step. It stays open until
step 4a; see the deferral section.

Repositories, in order: `AgentForge` (merge only, no release), `AIAuditLog`,
`OpenOntologyLite`, `ModelSwapBench`, `AI-Infrastructure-Suite`.

**1. Confirm CI is green on `main` before any tag.**

```bash
gh run list --repo sekacorn/<repo> --branch main --limit 5
```

**2. Publish `aiauditlog==0.2.0b2`.** The tag push publishes.

```bash
git -C AIAuditLog fetch origin
git -C AIAuditLog tag v0.2.0b2 origin/main
git -C AIAuditLog push origin v0.2.0b2
gh run watch --repo sekacorn/AIAuditLog
```

**3. Publish `openontologylite==0.2.0b3`.** The tag push publishes.

```bash
git -C OpenOntologyLite fetch origin
git -C OpenOntologyLite tag v0.2.0b3 origin/main
git -C OpenOntologyLite push origin v0.2.0b3
gh run watch --repo sekacorn/OpenOntologyLite
# Confirm the artifact actually landed before continuing:
curl -s https://pypi.org/pypi/openontologylite/json | python -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
```

**4. Publish `modelswapbench==0.1.0b2`.** The tag push publishes.

```bash
git -C ModelSwapBench fetch origin
git -C ModelSwapBench tag v0.1.0b2 origin/main
git -C ModelSwapBench push origin v0.1.0b2
gh run watch --repo sekacorn/ModelSwapBench
```

**4a. Raise the suite's dependency floor — only now that 0.2.0b3 is on PyPI.**
This commit goes **into the still-open suite pull request**, not onto `main`
after it. Its CI run is what first turns that pull request green; see the
deferral section above.

```bash
# In AI-Infrastructure-Suite, on feature/vendor-exit-evidence, in one commit:
#   pyproject.toml           openontologylite>=0.2.0b2  ->  >=0.2.0b3   (3 places)
#   ecosystem-manifest.json  openontologylite version_specifier, minimum_version,
#                            latest_published_version -> 0.2.0b3
# Then, on 3.11, 3.12 and 3.13:
python -m pytest && python -m ruff check . && python -m ruff format --check . \
  && python -m mypy && python -m bandit -c pyproject.toml -r src
git push origin feature/vendor-exit-evidence
gh pr checks 1 --repo sekacorn/AI-Infrastructure-Suite   # expect all green now
```

Only then merge the suite's pull request, and only then tag it.

**5. Publish `ai-infrastructure-suite==0.1.0b2`.** The tag push does **not**
publish here; the dispatch does.

```bash
git -C AI-Infrastructure-Suite fetch origin
git -C AI-Infrastructure-Suite tag v0.1.0b2 origin/main
git -C AI-Infrastructure-Suite push origin v0.1.0b2        # safe: no trigger
gh workflow run release.yml --repo sekacorn/AI-Infrastructure-Suite -f tag=v0.1.0b2
gh run watch --repo sekacorn/AI-Infrastructure-Suite
```

**6. Switch the umbrella CI off the feature-branch checkout.** See the CI
reference switch section. No publication step.

**7. Post-release, each as its own commit:** the Dependabot merges in the order
recorded above, then `github_actions` grouping in ModelSwapBench's
`.github/dependabot.yml`, then optionally TestPyPI support (Option B).

### Rollback

A published version cannot be replaced. If an artifact is wrong after upload,
the only forward path is to yank it on PyPI and publish the next pre-release
number; the burned number is never reused. If a tag was pushed but the run
failed before upload, delete the remote tag, fix, and re-tag the corrected
commit with a **new** version:

```bash
git -C <repo> push origin :refs/tags/<tag>   # only safe while nothing was uploaded
```

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

## Do not delete `feature/vendor-exit-evidence` on merge

**When the OpenOntologyLite pull request is merged, keep its
`feature/vendor-exit-evidence` branch.** The umbrella repository's
`offline-demos.yml` checks OpenOntologyLite out at that branch by name, so
deleting it breaks umbrella CI immediately and stays broken until the CI
reference switch below replaces the checkout with the released pin at 7-4.

GitHub offers to delete the head branch on merge, and repositories can be set
to do it automatically. Decline it for that merge. The branch may be deleted
only after 7-4 is merged and the umbrella workflow is green against
`openontologylite==0.2.0b3` from PyPI.

The same caution applies to any repository whose branch another repository's
CI names directly. Today that is OpenOntologyLite only.

## CI reference switch

**Status: done at checkpoint 7-4.** All five steps below are applied. Instead
of removing `cache: pip` keyed on the sibling checkout and repointing it, the
pip cache was dropped entirely: this repository ships no dependency manifest,
so `setup-python` has nothing stable to key a cache on, and a wrong key is
worse than no cache for a four-package install.

Step 5 is enforced rather than merely checked once: a workflow step asserts the
installed version is exactly `0.2.0b3` and that `open_ontology_lite` resolves
from a path containing `site-packages`. Both assertions were confirmed to fail
against `0.2.0b2` before being relied on, so a sibling checkout or a drifted
version cannot satisfy the import silently again.

During Phase 2, `.github/workflows/offline-demos.yml` checked out
OpenOntologyLite at `feature/vendor-exit-evidence`. After
`openontologylite==0.2.0b3` was published and independently installable, Phase 7
had to:

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

## Release dry runs

Every release workflow takes a `dry_run` boolean input, **default true**. A dry
run performs the tag/version check, the tests, the build, `twine check` and the
artifact checks, then stops before the PyPI upload. Jobs that depend on the
publish job skip with it.

Default true means an accidental dispatch rehearses instead of publishing. The
cost is that a real release has to say so explicitly, which is the right way
round for something that cannot be undone: a published version can never be
re-uploaded.

### A real release

AIAuditLog, OpenOntologyLite and ModelSwapBench publish on a tag push, and a
push carries no inputs, so nothing changes for them:

```bash
git -C <repo> tag -a <tag> origin/main -m "<message>"
git -C <repo> push origin refs/tags/<tag>:refs/tags/<tag>
```

AI Infrastructure Suite publishes by dispatch, so with `dry_run` defaulting to
true its real release **must pass the flag explicitly**:

```bash
gh workflow run release.yml --repo sekacorn/AI-Infrastructure-Suite   -f tag=<tag> -f dry_run=false
```

Omitting `dry_run=false` there produces a rehearsal, not a release. That is the
intended failure mode.

### A rehearsal

```bash
gh workflow run release.yml --repo sekacorn/<repo> -f tag=<existing tag>
```

The three tag-triggered workflows gained a required `tag` input for this. Their
version check previously read `github.ref_name`, which on a dispatch is the
branch name, so it would have compared `main` against the package version and
failed. Both jobs now check out the resolved ref and the check compares against
the same value.

### Why the condition is written the way it is

```yaml
if: ${{ github.event_name == 'push' || inputs.dry_run == false }}
```

`inputs.dry_run` is empty on a push event. The event check comes first and
settles a push before the input is consulted.

| event | `inputs.dry_run` | publish |
|---|---|---|
| `push` (tag) | empty | runs |
| `workflow_dispatch` | `false` | runs |
| `workflow_dispatch` | `true` (default) | skipped |

Two safeguards keep this honest. The first job prints the event, the raw input
and the resolved mode, so every run states on its face whether it will upload.
And the publish job re-derives the mode immediately before the upload step and
fails if it is a dry run, so a mistake in the job condition produces a failed
run rather than an unintended upload.

Attestation generation happens inside the publish action, so a dry run cannot
exercise it. Everything before it is exercised in full.

## Post-release backlog

Deliberately deferred. None of these is required for this release, and none
should be done during it: each changes repository settings or CI configuration,
which is exactly the churn the Dependabot ordering above exists to avoid
during a publish. Each is its own commit or settings change afterwards.

**1. Branch protection on the other five repositories.** Observed during the
7-3 merges: only OpenOntologyLite had any protection on `main`. The other five
had none, so their merges passed no enforced gate at all — they happened to be
green, but nothing required it.

| Repository | `main` protection at 7-3 |
|---|---|
| OpenOntologyLite | required checks, strict, conversation resolution |
| AIAuditLog | none |
| ModelSwapBench | none |
| AgentForge | none |
| Linux-of-Ai | none |
| AI Infrastructure Suite | none |

Apply OpenOntologyLite's shape to the other five: the repository's own
per-version test contexts as required checks, `strict` so a branch must be up
to date before merging, and **`required_approving_review_count: 0`**. Zero is
deliberate and is not a weakening: GitHub forbids a pull request author from
approving their own pull request, so on a single-maintainer project any
non-zero count makes `main` unmergeable without an administrator bypass, and
bypassing protection is forbidden by the release gates below. The required
checks are what actually carry the enforcement. Revisit the review count if a
second maintainer joins.

OpenOntologyLite itself was changed from 1 to 0 during 7-3 for exactly this
reason; its four required checks and `strict` mode were kept.

**2. The pre-existing OpenSSF Scorecard failures on AIAuditLog.** Its
`schedule`-triggered Scorecard runs have been failing against commit
`364cb0d2` since at least 2026-09-22, well before this work. No run on the
7-3 merge commit failed, so this is not a regression and did not block the
release. Worth diagnosing separately, especially since the same workflow
passes on OpenOntologyLite and ModelSwapBench, which suggests a repository
setting or a missing permission rather than a code problem.

**3. The tag-pattern narrowing and TestPyPI support**, both already described
above: `v[0-9]*` in place of `v*` in the three tag-triggered workflows, and
Option B for TestPyPI.

**4. `github_actions` grouping in ModelSwapBench's `.github/dependabot.yml`**,
as its own commit, as recorded in the Dependabot section.

## Release gates

For every package release, verify the version, changelog, metadata, wheel,
sdist, Twine validation, isolated wheel and sdist installs, CLI/import smoke
tests, artifact scans, and the configured lint, formatting, typing, security,
audit, and test checks. Confirm Trusted Publishing and PyPI installation before
moving to the next dependent release. Never reuse a failed or already-published
version, bypass branch protection, force-push, or claim a live integration that
was not exercised.
