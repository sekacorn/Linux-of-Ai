"""Tests for the deterministic three-profile restore demo."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import restore_demo as demo

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"


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

    def test_repeated_fake_runs_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            demo.run_demo(BUNDLE, root / "first")
            demo.run_demo(BUNDLE, root / "second")
            first = (root / "first" / "restore-demo-result.json").read_bytes()
            second = (root / "second" / "restore-demo-result.json").read_bytes()
            self.assertEqual(first, second)

    def test_bypassing_provider_adapter_is_rejected(self) -> None:
        adapter = demo.AzureAdapter(demo.FakeBackend(demo.AWS))
        with self.assertRaisesRegex(demo.RestoreError, "non-AWS request envelope"):
            adapter.request_tool("prompt", "message")

    def test_copied_embedding_dimension_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            altered = root / "bundle"
            shutil.copytree(BUNDLE, altered)
            embedding_path = altered / "assets" / "embeddings.json"
            embeddings = json.loads(embedding_path.read_text(encoding="utf-8"))
            embeddings["items"][0]["vector"].pop()
            embedding_path.write_text(
                json.dumps(embeddings, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["assets"]["embeddings"]["sha256"] = hashlib.sha256(
                embedding_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            with self.assertRaisesRegex(demo.RestoreError, "dimension mismatch"):
                demo.run_demo(altered, root / "output")


if __name__ == "__main__":
    unittest.main()
