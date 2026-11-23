# Known issues

Pre-existing defects found while working on something else, recorded rather
than fixed in place. Each says which phase is expected to pick it up, so a
later reader can tell a deferral from an oversight.

## AgentForge memory backends disagree on default embedding dimension

**Found during:** Phase 3b-0 audit, 2026-11-22. **Deferred to:** Phase 4.
**Not a regression:** present since the backends were written.

AgentForge ships three vector memory backends that use an identical tokenizer
(regex `[a-z0-9]+` over lowercased text) and an identical hash
(`blake2b`, `digest_size=8`), but disagree on the default dimension:

| Backend | Default |
|---|---|
| `forge/memory/vector.py` (`InMemoryVectorStore`) | `dim = 512` |
| `forge/memory/sqlite.py` | `embedding_dim = 64` |
| `forge/memory/pgvector.py` | `embedding_dim = 64` |

Because the bucket a token lands in is `hash(token) % dim`, two stores built at
different dimensions are not comparable and not interchangeable. A caller who
ingests through the in-memory store and later reads through the SQLite or
pgvector backend, at defaults, gets a store whose vectors cannot be searched
against new queries in any meaningful way. Nothing warns.

**Why it has not bitten:** the backends are normally chosen once per
deployment and the dimension is explicit in most call sites, so the mismatch
only surfaces when a store is moved between backends while relying on defaults.

**Why Phase 3b is unaffected:** 3b never consults a backend default. Model
identity there is the triple `id` + `revision` + `dimensions`, dimensions always
come from the declared model in the evidence document, and a mismatch between
declared and produced dimensions is a hard error. See
[phase3b-re-embedding.md](phase3b-re-embedding.md).

**Candidate fixes**, for Phase 4 to choose between:

1. **One shared default.** Pick a single value and use it in all three
   backends. Smallest change, but it silently alters the dimension for existing
   callers of whichever backends move, which changes every vector they produce.
2. **No default at all.** Make `dim` a required argument in all three. Honest
   and loud, but a breaking API change that needs a deprecation shim under the
   project's semver rules.
3. **Record the dimension in the store and refuse a mismatch on read.** The
   most useful of the three: it makes the incompatibility detectable rather than
   silent, and it is additive. Also the most work, and it needs a migration path
   for stores already written without the field.

Option 3 is the one that matches how Phase 3a and 3b treat dimensions, so it is
the suggested starting point rather than a settled answer.
