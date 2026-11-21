"""Tests for the deterministic embedding-portability evidence generator."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import embedding_evidence as evidence
import restore_demo as demo

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
COMMITTED = ROOT / "evidence"


def _build(root: Path) -> tuple[Path, str]:
    digest = evidence.build_embedding_evidence(BUNDLE, root)
    return root / evidence.EVIDENCE_NAME, digest


def _bundle_copy(root: Path) -> Path:
    target = root / "bundle"
    shutil.copytree(BUNDLE, target)
    return target


def _replace_asset(bundle: Path, name: str, document: object) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    data = (json.dumps(document, indent=2) + "\n").encode()
    (bundle / manifest["assets"][name]["path"]).write_bytes(data)
    manifest["assets"][name]["sha256"] = hashlib.sha256(data).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


class EmbeddingEvidenceTests(unittest.TestCase):
    def test_regenerating_twice_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_path, first_digest = _build(root / "first")
            second_path, second_digest = _build(root / "second")

            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            self.assertEqual(first_digest, second_digest)
            for relative in ("sources", "vectors"):
                first_files = sorted((root / "first" / relative).iterdir())
                second_files = sorted((root / "second" / relative).iterdir())
                self.assertEqual(
                    [item.name for item in first_files],
                    [item.name for item in second_files],
                )
                for left, right in zip(first_files, second_files, strict=True):
                    self.assertEqual(left.read_bytes(), right.read_bytes())

    def test_the_committed_evidence_matches_a_fresh_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "regenerated"
            path, _ = _build(root)

            self.assertEqual(
                path.read_bytes(),
                (COMMITTED / evidence.EVIDENCE_NAME).read_bytes(),
            )
            for item in sorted(root.rglob("*")):
                if item.is_file():
                    mirrored = COMMITTED / item.relative_to(root)
                    self.assertTrue(mirrored.is_file(), item)
                    self.assertEqual(item.read_bytes(), mirrored.read_bytes(), item)

    def test_the_evidence_declares_the_digests_of_its_own_files(self) -> None:
        document = json.loads(
            (COMMITTED / evidence.EVIDENCE_NAME).read_text(encoding="utf-8")
        )
        (store,) = document["stores"]
        records = store["vectors"]["records"]
        self.assertEqual(len(records), 2)
        for record in records:
            for reference in (record["vector"], record["source_text"]):
                data = (COMMITTED / reference["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), reference["sha256"])
            # The retained file must still match what produced the vector.
            self.assertEqual(
                record["source_text"]["sha256"],
                record["source_text_sha256_in_vector_record"],
            )

    def test_the_evidence_holds_no_digest_of_the_bundle_or_the_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            demo.run_demo(BUNDLE, output)
            summary_bytes = (output / "restore-summary.json").read_bytes()
            manifest_bytes = (BUNDLE / "manifest.json").read_bytes()
            forbidden = {
                "restore summary": hashlib.sha256(summary_bytes).hexdigest(),
                "bundle manifest": hashlib.sha256(manifest_bytes).hexdigest(),
            }
            text = (COMMITTED / evidence.EVIDENCE_NAME).read_text(encoding="utf-8")

            # The restore summary commits to the evidence digest, so evidence
            # that committed back would make neither document reproducible.
            for label, digest in forbidden.items():
                with self.subTest(digest=label):
                    self.assertNotIn(digest, text)

    def test_mismatched_memory_and_embedding_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = _bundle_copy(root)
            document = json.loads(
                (bundle / "assets/memory.json").read_text(encoding="utf-8")
            )
            document["items"][0]["id"] = "procedure-unknown"
            _replace_asset(bundle, "memory", document)

            with self.assertRaisesRegex(
                evidence.EvidenceError, "matching memory source text"
            ):
                evidence.build_embedding_evidence(bundle, root / "out")

    def test_a_changed_embedding_dimension_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = _bundle_copy(root)
            document = json.loads(
                (bundle / "assets/embeddings.json").read_text(encoding="utf-8")
            )
            document["dimension"] = 4
            for item in document["items"]:
                item["vector"] = item["vector"][:4]
            _replace_asset(bundle, "embeddings", document)

            with self.assertRaisesRegex(
                evidence.EvidenceError, "dimension does not match"
            ):
                evidence.build_embedding_evidence(bundle, root / "out")

    def test_duplicate_record_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = _bundle_copy(root)
            document = json.loads(
                (bundle / "assets/embeddings.json").read_text(encoding="utf-8")
            )
            document["items"][1]["id"] = document["items"][0]["id"]
            _replace_asset(bundle, "embeddings", document)

            with self.assertRaisesRegex(
                evidence.EvidenceError, "Duplicate embedding item id"
            ):
                evidence.build_embedding_evidence(bundle, root / "out")

    def test_an_empty_memory_asset_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = _bundle_copy(root)
            _replace_asset(
                bundle, "memory", {"schema_version": "restore-memory.v1", "items": []}
            )

            with self.assertRaisesRegex(evidence.EvidenceError, "memory has no items"):
                evidence.build_embedding_evidence(bundle, root / "out")


if __name__ == "__main__":
    unittest.main()
