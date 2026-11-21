"""Build `embedding-portability.v1` evidence from the restore demo bundle.

The restore bundle already carries the two things an embedding inventory needs:
`assets/embeddings.json` holds one copied vector per record, and
`assets/memory.json` holds the source text those vectors were produced from.
This module writes them out as the per-record files an exit report can verify.

Two rules keep the evidence usable:

* **Deterministic.** The same bundle bytes always produce byte-identical
  evidence, so a regenerated document can be compared rather than trusted.
* **No digest cycle.** The evidence references only its own vector and source
  files. It never contains a digest of the bundle manifest or of a restore
  summary, because those digests depend on this document: the restore summary
  commits to the evidence digest, so the evidence must not commit back.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "embedding-portability.v1"
STORE_ID = "support-memory"
EVIDENCE_NAME = "embedding-portability.json"
# portable-hash-v1 is a deterministic local function defined in this Apache-2.0
# repository, so it is self-hostable by construction. It has no weight file, so
# no weights digest is declared and the report says the weights are not pinned.
MODEL: dict[str, Any] = {
    "id": "portable-hash-v1",
    "revision": "1",
    "dimensions": 8,
    "availability": "open_weight_self_hostable",
    "availability_verification": "attested",
    "license": "Apache-2.0",
}

Record = dict[str, Any]


class EvidenceError(RuntimeError):
    """Raised when the bundle cannot produce a usable embedding inventory."""


def _read_json(path: Path) -> Record:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Cannot read {path.name}") from exc
    if not isinstance(document, dict):
        raise EvidenceError(f"Expected a JSON object in {path.name}")
    return document


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _json_bytes(document: object) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def _sources(bundle_root: Path) -> dict[str, bytes]:
    memory = _read_json(bundle_root / "assets/memory.json")
    items = memory.get("items")
    if not isinstance(items, list) or not items:
        raise EvidenceError("Bundle memory has no items")
    sources: dict[str, bytes] = {}
    for item in items:
        if not isinstance(item, dict):
            raise EvidenceError("Bundle memory item is invalid")
        name, text = item.get("id"), item.get("text")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(text, str)
            or not text
        ):
            raise EvidenceError("Bundle memory item id or text is invalid")
        if name in sources:
            raise EvidenceError(f"Duplicate memory item id: {name}")
        sources[name] = (text + "\n").encode()
    return sources


def _vectors(bundle_root: Path) -> dict[str, list[float]]:
    document = _read_json(bundle_root / "assets/embeddings.json")
    dimension = document.get("dimension")
    items = document.get("items")
    if dimension != MODEL["dimensions"]:
        raise EvidenceError(
            "Bundle embedding dimension does not match the declared model"
        )
    if not isinstance(items, list) or not items:
        raise EvidenceError("Bundle embeddings have no items")
    vectors: dict[str, list[float]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise EvidenceError("Bundle embedding item is invalid")
        name, vector = item.get("id"), item.get("vector")
        if not isinstance(name, str) or not name:
            raise EvidenceError("Bundle embedding item id is invalid")
        if not isinstance(vector, list) or len(vector) != dimension:
            raise EvidenceError(f"Bundle embedding vector for {name} is invalid")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in vector
        ):
            raise EvidenceError(f"Bundle embedding vector for {name} is not numeric")
        if name in vectors:
            raise EvidenceError(f"Duplicate embedding item id: {name}")
        vectors[name] = [float(value) for value in vector]
    return vectors


def build_embedding_evidence(bundle_root: Path, output_root: Path) -> str:
    """Write the evidence document and its files, returning the document digest."""
    sources = _sources(bundle_root)
    vectors = _vectors(bundle_root)
    if sources.keys() != vectors.keys():
        raise EvidenceError(
            "Every embedding record requires matching memory source text"
        )
    records: list[Record] = []
    # Sorted so the document does not depend on dictionary insertion order.
    for name in sorted(vectors):
        source_digest = _write(output_root / f"sources/{name}.txt", sources[name])
        vector_bytes = _json_bytes({"values": vectors[name]})
        records.append(
            {
                "record_id": name,
                "vector": {
                    "path": f"vectors/{name}.json",
                    "sha256": _write(
                        output_root / f"vectors/{name}.json", vector_bytes
                    ),
                },
                "source_text_sha256_in_vector_record": source_digest,
                "source_text": {
                    "status": "retained",
                    "path": f"sources/{name}.txt",
                    "sha256": source_digest,
                },
            }
        )
    document = {
        "schema_version": SCHEMA_VERSION,
        "stores": [
            {
                "store_id": STORE_ID,
                "embedding_model": dict(MODEL),
                "vectors": {"layout": "single_file", "records": records},
            }
        ],
    }
    return _write(output_root / EVIDENCE_NAME, _json_bytes(document))
