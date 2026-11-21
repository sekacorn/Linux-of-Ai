"""Tests for the deterministic three-profile restore demo."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import restore_demo as demo

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"


def copied_bundle(root: Path) -> Path:
    target = root / "bundle"
    shutil.copytree(BUNDLE, target)
    return target


def replace_asset(bundle: Path, name: str, data: bytes) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset_path = bundle / manifest["assets"][name]["path"]
    asset_path.write_bytes(data)
    manifest["assets"][name]["sha256"] = hashlib.sha256(data).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


class RecordingBackend(demo.FakeBackend):
    def __init__(self, profile: demo.Profile) -> None:
        super().__init__(profile)
        self.embedding_inputs: list[str] = []

    def embed(self, text: str) -> demo.Record:
        self.embedding_inputs.append(text)
        return super().embed(text)


class DriftingAzureBackend(demo.FakeBackend):
    def invoke(self, payload: demo.Record) -> demo.Record:
        response = super().invoke(payload)
        choices = response.get("choices")
        if isinstance(choices, list) and choices[0].get("finish_reason") == "stop":
            choices[0]["message"]["content"] = '{"action":"changed"}'
        return response


class UnsupportedPortableAzureAdapter(demo.AzureAdapter):
    portable_embedding_dimensions = (4,)


class RestoreDemoTests(unittest.TestCase):
    def test_fanout_and_chained_reexports_pass_every_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result"
            with mock.patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("offline demo attempted network access"),
            ) as contact:
                report = demo.run_demo(BUNDLE, output)
            contact.assert_not_called()
            self.assertEqual(report["status"], "passed")
            self.assertEqual(
                report["chain_order"],
                ["mock-azure", "mock-aws", "local-ollama"],
            )
            self.assertEqual(
                report["embedding_transfer"],
                "vectors copied (same model), not re-embedded",
            )
            for migration in [*report["fanout"], *report["chain"]]:
                self.assertEqual(migration["status"], "passed")
                self.assertTrue(
                    all(
                        value == "matched"
                        for value in migration["reexport_gate"].values()
                    )
                )
                self.assertTrue(
                    all(
                        value == "matched"
                        for value in migration["original_reexport_gate"].values()
                    )
                )
                self.assertEqual(migration["behavior_gate"]["status"], "passed")
            dimensions = [
                item["behavior_gate"]["native_embedding_dimension"]
                for item in report["fanout"]
            ]
            self.assertEqual(dimensions, [4, 6, 8])
            tool_input_counts = [
                item["behavior_gate"]["tool_usage"]["input_tokens"]
                for item in report["fanout"]
            ]
            self.assertEqual(tool_input_counts, [41, 43, 47])
            summary_path = output / report["restore_summary"]["path"]
            summary_bytes = summary_path.read_bytes()
            self.assertEqual(
                hashlib.sha256(summary_bytes).hexdigest(),
                report["restore_summary"]["sha256"],
            )
            summary = json.loads(summary_bytes)
            self.assertEqual(summary["schema_version"], "restore-summary.v1")
            self.assertEqual(len(summary["fanout"]), 3)
            self.assertEqual(len(summary["chain"]), 3)
            for reference in [*summary["fanout"], *summary["chain"]]:
                record = output / reference["path"]
                self.assertEqual(
                    hashlib.sha256(record.read_bytes()).hexdigest(),
                    reference["sha256"],
                )

    def test_repeated_fake_runs_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            demo.run_demo(BUNDLE, root / "first")
            demo.run_demo(BUNDLE, root / "second")
            first = (root / "first" / "restore-demo-result.json").read_bytes()
            second = (root / "second" / "restore-demo-result.json").read_bytes()
            self.assertEqual(first, second)
            self.assertEqual(
                (root / "first" / "restore-summary.json").read_bytes(),
                (root / "second" / "restore-summary.json").read_bytes(),
            )

    def test_bypassing_provider_adapter_is_rejected(self) -> None:
        adapter = demo.AzureAdapter(demo.FakeBackend(demo.AWS))
        with self.assertRaisesRegex(demo.RestoreError, "non-AWS request envelope"):
            adapter.request_tool("prompt", "message")

    def test_copied_embedding_dimension_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            altered = copied_bundle(root)
            embedding_path = altered / "assets" / "embeddings.json"
            embeddings = json.loads(embedding_path.read_text(encoding="utf-8"))
            embeddings["items"][0]["vector"].pop()
            replace_asset(
                altered,
                "embeddings",
                (json.dumps(embeddings, indent=2) + "\n").encode(),
            )
            with self.assertRaisesRegex(demo.RestoreError, "dimension mismatch"):
                demo.run_demo(altered, root / "output")

    def test_behavior_drift_fails_with_unchanged_content(self) -> None:
        bundle = demo.Bundle.load(BUNDLE)
        adapter = demo.AzureAdapter(DriftingAzureBackend(demo.AZURE))
        before = bundle.content_digests()
        with self.assertRaisesRegex(demo.RestoreError, "scripted task result changed"):
            demo.run_behavior(bundle, adapter)
        self.assertEqual(bundle.content_digests(), before)

    def test_profile_rejects_unsupported_copied_embedding_dimension(self) -> None:
        adapter = UnsupportedPortableAzureAdapter(demo.FakeBackend(demo.AZURE))
        with self.assertRaisesRegex(demo.RestoreError, "does not support"):
            demo.run_behavior(demo.Bundle.load(BUNDLE), adapter)

    def test_duplicate_json_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            altered = copied_bundle(root)
            replace_asset(
                altered,
                "policies",
                b'{"schema_version":"restore-policy.v1",'
                b'"schema_version":"duplicate","decisions":{}}',
            )
            with self.assertRaisesRegex(demo.RestoreError, "Duplicate JSON field"):
                demo.run_demo(altered, root / "output")

    def test_oversized_asset_is_rejected_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            altered = copied_bundle(root)
            replace_asset(altered, "prompts", b"x" * (demo.MAX_ASSET_BYTES + 1))
            with self.assertRaisesRegex(demo.RestoreError, "bounded regular file"):
                demo.Bundle.load(altered)

    def test_manifest_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = copied_bundle(Path(directory))
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["assets"]["prompts"]["path"] = "../prompt.txt"
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            with self.assertRaisesRegex(demo.RestoreError, "traversal"):
                demo.Bundle.load(altered)

    def test_linked_asset_is_rejected(self) -> None:
        prompt = (BUNDLE / "assets" / "prompt.txt").absolute()
        original_lstat = Path.lstat
        cases = (
            (stat.S_IFLNK, 0, "symbolic-link"),
            (
                stat.S_IFREG,
                stat.FILE_ATTRIBUTE_REPARSE_POINT,
                "windows-reparse-point",
            ),
        )
        for mode, attributes, label in cases:
            with self.subTest(link_type=label):

                def linked_lstat(
                    path: Path,
                    marker_mode: int = mode,
                    marker_attributes: int = attributes,
                ) -> os.stat_result | SimpleNamespace:
                    result = original_lstat(path)
                    if path.absolute() == prompt:
                        return SimpleNamespace(
                            st_mode=marker_mode,
                            st_file_attributes=marker_attributes,
                        )
                    return result

                with (
                    mock.patch.object(Path, "lstat", linked_lstat),
                    self.assertRaisesRegex(demo.RestoreError, "Linked bundle path"),
                ):
                    demo.Bundle.load(BUNDLE)

    def test_live_ollama_failure_never_falls_back_to_fake(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_profiles: list[str] = []
            original_invoke = demo.FakeBackend.invoke

            def record_fake(
                backend: demo.FakeBackend, payload: demo.Record
            ) -> demo.Record:
                fake_profiles.append(backend.profile.name)
                return original_invoke(backend, payload)

            with (
                mock.patch.object(demo.FakeBackend, "invoke", record_fake),
                mock.patch(
                    "urllib.request.urlopen", side_effect=OSError("offline")
                ) as contact,
                self.assertRaisesRegex(demo.RestoreError, "Live Ollama request failed"),
            ):
                demo.run_demo(BUNDLE, Path(directory) / "output", live_ollama=True)
            contact.assert_called_once()
            self.assertNotIn("local-ollama", fake_profiles)

    def test_native_embedders_receive_text_not_copied_vectors(self) -> None:
        bundle = demo.Bundle.load(BUNDLE)
        task_message = str(bundle.task()["message"])
        profiles_and_adapters = (
            (demo.AZURE, demo.AzureAdapter),
            (demo.AWS, demo.AwsAdapter),
            (demo.OLLAMA, demo.OllamaAdapter),
        )
        for profile, adapter_type in profiles_and_adapters:
            with self.subTest(profile=profile.name):
                backend = RecordingBackend(profile)
                result = demo.run_behavior(bundle, adapter_type(backend))
                self.assertEqual(backend.embedding_inputs, [task_message])
                self.assertEqual(result["native_embedding_input"], "task text only")
                self.assertEqual(result["portable_embedding_dimension"], 8)
                self.assertEqual(
                    result["native_embedding_dimension"],
                    profile.native_embedding_dimension,
                )
                self.assertEqual(result["retrieval_engine"], "portable vector store")


DIGEST_OK = "a" * 64


class EmbeddingStoreClaimTests(unittest.TestCase):
    """The optional vector-store claim a bundle may declare for its embeddings."""

    STORE_ID = "support-memory"
    DIGEST = DIGEST_OK

    CLAIM_FIELDS = ("store_id", "store_evidence_sha256")

    def _bundle_with(self, root: Path, **claim: object) -> Path:
        """Copy the bundle and make its claim exactly ``claim``.

        The shipped bundle declares a real claim, so every field is cleared
        first; passing nothing produces a bundle with no claim at all.
        """
        bundle = copied_bundle(root)
        document = json.loads(
            (bundle / "assets/embeddings.json").read_text(encoding="utf-8")
        )
        for field in self.CLAIM_FIELDS:
            document.pop(field, None)
        document.update(claim)
        replace_asset(
            bundle,
            "embeddings",
            (json.dumps(document, indent=2) + "\n").encode(),
        )
        return bundle

    def test_the_shipped_bundle_declares_its_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            demo.run_demo(BUNDLE, output)
            summary = json.loads(
                (output / "restore-summary.json").read_text(encoding="utf-8")
            )

            (claim,) = summary["embedding_stores"]
            self.assertEqual(claim["store_id"], self.STORE_ID)
            self.assertRegex(claim["store_evidence_sha256"], r"\A[0-9a-f]{64}\Z")

    def test_a_bundle_without_a_claim_omits_the_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self._bundle_with(root)
            output = root / "output"
            demo.run_demo(bundle, output)
            summary = json.loads(
                (output / "restore-summary.json").read_text(encoding="utf-8")
            )

            self.assertNotIn("embedding_stores", summary)

    def test_a_declared_claim_is_relayed_into_the_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self._bundle_with(
                root, store_id=self.STORE_ID, store_evidence_sha256=self.DIGEST
            )
            output = root / "output"
            demo.run_demo(bundle, output)
            summary = json.loads(
                (output / "restore-summary.json").read_text(encoding="utf-8")
            )

            self.assertEqual(
                summary["embedding_stores"],
                [{"store_id": self.STORE_ID, "store_evidence_sha256": self.DIGEST}],
            )
            self.assertEqual(summary["status"], "passed")

    def test_a_claim_does_not_change_the_restore_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self._bundle_with(
                root, store_id=self.STORE_ID, store_evidence_sha256=self.DIGEST
            )
            plain = root / "plain"
            claimed = root / "claimed"
            demo.run_demo(self._bundle_with(root / "bare"), plain)
            demo.run_demo(bundle, claimed)
            before = json.loads(
                (plain / "restore-demo-result.json").read_text(encoding="utf-8")
            )
            after = json.loads(
                (claimed / "restore-demo-result.json").read_text(encoding="utf-8")
            )

            # The claim rides along with the bundle, so bundle digests differ,
            # but every behaviour gate must report exactly the same result.
            self.assertEqual(
                [item["behavior_gate"] for item in before["fanout"]],
                [item["behavior_gate"] for item in after["fanout"]],
            )
            self.assertEqual(before["chain_order"], after["chain_order"])

    def test_a_claim_is_still_deterministic_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self._bundle_with(
                root, store_id=self.STORE_ID, store_evidence_sha256=self.DIGEST
            )
            demo.run_demo(bundle, root / "first")
            demo.run_demo(bundle, root / "second")

            self.assertEqual(
                (root / "first" / "restore-summary.json").read_bytes(),
                (root / "second" / "restore-summary.json").read_bytes(),
            )

    def test_a_store_id_without_a_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self._bundle_with(root, store_id=self.STORE_ID)

            with self.assertRaisesRegex(demo.RestoreError, "store evidence digest"):
                demo.run_demo(bundle, root / "output")

    def test_a_digest_without_a_store_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self._bundle_with(root, store_evidence_sha256=self.DIGEST)

            with self.assertRaisesRegex(demo.RestoreError, "store_id is invalid"):
                demo.run_demo(bundle, root / "output")

    def test_a_malformed_claim_is_rejected(self) -> None:
        cases = (
            {"store_id": "", "store_evidence_sha256": DIGEST_OK},
            {"store_id": "x" * 129, "store_evidence_sha256": DIGEST_OK},
            {"store_id": 7, "store_evidence_sha256": DIGEST_OK},
            {"store_id": "support-memory", "store_evidence_sha256": "A" * 64},
            {"store_id": "support-memory", "store_evidence_sha256": "a" * 63},
            {"store_id": "support-memory", "store_evidence_sha256": 7},
        )
        for claim in cases:
            with self.subTest(claim=claim), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                bundle = self._bundle_with(root, **claim)

                with self.assertRaises(demo.RestoreError):
                    demo.run_demo(bundle, root / "output")


if __name__ == "__main__":
    unittest.main()
