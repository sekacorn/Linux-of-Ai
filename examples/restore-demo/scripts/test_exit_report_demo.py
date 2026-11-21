"""End-to-end embedding lock-in reporting over the real restore demo.

The AI Infrastructure Suite is an optional, separately installed dependency,
so every test that needs the scanner skips when it is absent. The manifest
assembly itself is tested either way.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import exit_report_demo as integration
from embedding_evidence import EVIDENCE_NAME, STORE_ID
from restore_demo import RestoreError

try:  # pragma: no cover - import availability is the point
    import ai_infrastructure_suite  # noqa: F401

    SUITE_AVAILABLE = True
except ImportError:  # pragma: no cover
    SUITE_AVAILABLE = False

SUITE_REQUIRED = unittest.skipUnless(
    SUITE_AVAILABLE, "ai-infrastructure-suite is not installed"
)


class ExitManifestTests(unittest.TestCase):
    def test_the_manifest_references_the_summary_and_the_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            manifest_path = integration.build_exit_manifest(output)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            vectors = manifest["vectors"]

            self.assertEqual(manifest["schema_version"], "exit-manifest.v1")
            self.assertEqual(vectors["embeddings"]["state"], "embedding_inventory")
            for name in integration.RESTORE_TESTED_VECTORS:
                self.assertEqual(vectors[name]["state"], "restore_tested")
            # Each referenced file must hash to what the manifest declares.
            for entry in vectors.values():
                data = (output / entry["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])

    def test_the_summary_commits_to_the_inventory_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            integration.build_exit_manifest(output)
            summary = json.loads(
                (output / integration.SUMMARY_NAME).read_text(encoding="utf-8")
            )
            evidence = output / integration.EVIDENCE_DIRECTORY / EVIDENCE_NAME

            (claim,) = summary["embedding_stores"]
            self.assertEqual(claim["store_id"], STORE_ID)
            self.assertEqual(
                claim["store_evidence_sha256"],
                hashlib.sha256(evidence.read_bytes()).hexdigest(),
            )

    def test_a_repeated_run_into_the_same_output_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            integration.build_exit_manifest(output)

            # The restore demo refuses first; the evidence copy keeps its own
            # guard so the order of those two checks is not load-bearing.
            with self.assertRaisesRegex(
                (RestoreError, integration.ExitReportDemoError), "already exists"
            ):
                integration.build_exit_manifest(output)

    def test_missing_embedding_evidence_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaisesRegex(
                integration.ExitReportDemoError, "evidence is missing"
            ):
                integration.build_exit_manifest(
                    root / "output", evidence=root / "absent"
                )


@SUITE_REQUIRED
class ExitReportTests(unittest.TestCase):
    def test_the_embeddings_row_reaches_zero_with_verified_restores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            manifest = integration.build_exit_manifest(output)

            report, markdown = integration.run_exit_report(manifest)

            row = report["vectors"]["embeddings"]
            self.assertEqual(row["score"], 0)
            self.assertEqual(row["re_embeddable"], "yes")
            self.assertEqual(
                row["verification_level"], "verified (local evidence + fake profiles)"
            )
            (store,) = report["embedding_stores"]
            self.assertEqual(store["store_id"], STORE_ID)
            self.assertEqual(store["restore_link"], "verified")
            self.assertEqual(store["coverage_pct"], 100.0)
            self.assertEqual(store["retained"], 2)
            self.assertEqual(store["missing"], 0)
            self.assertEqual(store["deleted_by_policy"], 0)
            self.assertIn("| embeddings | 0 |", markdown)
            self.assertIn("## Embedding stores", markdown)

    def test_the_unpinned_weights_note_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            manifest = integration.build_exit_manifest(output)

            report, _ = integration.run_exit_report(manifest)

            # portable-hash-v1 has no weight file, so nothing pins it.
            (store,) = report["embedding_stores"]
            self.assertIn("weights are not pinned", store["reason"])
            self.assertNotIn(
                "model weights digest", report["vectors"]["embeddings"]["reason"]
            )
            self.assertEqual(
                report["vectors"]["embeddings"]["attested_claims"],
                ["model availability", "model license"],
            )

    def test_no_source_text_or_vector_values_appear_in_either_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            manifest = integration.build_exit_manifest(output)

            report, markdown = integration.run_exit_report(manifest)

            rendered = json.dumps(report) + markdown
            self.assertNotIn("never request or expose credentials", rendered)
            self.assertNotIn("billing review", rendered)

    def test_a_tampered_inventory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            manifest = integration.build_exit_manifest(output)
            source = (
                output
                / integration.EVIDENCE_DIRECTORY
                / "sources/procedure-password-reset.txt"
            )
            source.write_bytes(b"rewritten after the digest was taken\n")

            with self.assertRaisesRegex(ValueError, "source text differs"):
                integration.run_exit_report(manifest)

    def test_a_summary_committing_elsewhere_does_not_reach_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            manifest_path = integration.build_exit_manifest(output)
            summary_path = output / integration.SUMMARY_NAME
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["embedding_stores"][0]["store_evidence_sha256"] = "c" * 64
            data = (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode()
            summary_path.write_bytes(data)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(data).hexdigest()
            for name in integration.RESTORE_TESTED_VECTORS:
                manifest["vectors"][name]["sha256"] = digest
            manifest_path.write_bytes(
                (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
            )

            report, _ = integration.run_exit_report(manifest_path)

            self.assertEqual(report["vectors"]["embeddings"]["score"], 25)
            self.assertEqual(
                report["embedding_stores"][0]["restore_link"],
                "store_id_matched_digest_mismatch",
            )


if __name__ == "__main__":
    unittest.main()
