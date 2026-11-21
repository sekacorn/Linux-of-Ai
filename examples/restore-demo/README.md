# Offline three-profile restore demo

This demo restores one portable fixture bundle through deterministic Azure-, AWS-, and Ollama-shaped fake providers. It runs an independent fan-out and this chained migration:

```text
source -> mock-azure -> export -> mock-aws -> export -> local-ollama
```

Every supported asset must preserve its digest, pass an asset-specific check, produce the expected scripted agent result, and survive re-export. The adapters deliberately use different tool-call envelopes, stop-reason fields, usage fields, and native embedding dimensions.

Retrieval runs in the portable vector store over the copied eight-dimensional
vectors. Provider-native embedding calls receive task text only and are a
separate adapter-capability check; copied vectors are never passed to them.

Run the offline demo:

```bash
python examples/restore-demo/scripts/run_restore_demo.py --output restore-output
```

The output directory must not already exist. No provider credentials or network access are used. The result labels portable embeddings as `vectors copied (same model), not re-embedded`.

An optional live Ollama check requires deliberate opt-in and never falls back to the fake provider:

```bash
python examples/restore-demo/scripts/run_restore_demo.py \
  --output restore-output \
  --live-ollama \
  --ollama-endpoint http://127.0.0.1:11434 \
  --ollama-model qwen2.5:3b
```

Only loopback Ollama endpoints are accepted. Live behavior is outside the deterministic CI matrix and may fail when the model does not produce the exact scripted result.

The detailed design and evidence boundaries are documented in [`../../docs/restore-demo.md`](../../docs/restore-demo.md).
