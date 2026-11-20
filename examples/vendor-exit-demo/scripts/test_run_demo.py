import json
import tempfile
import unittest
from pathlib import Path

import run_demo as demo


class RecommendationTests(unittest.TestCase):
    def test_metric_gates_propagate_to_decision_and_routing(self) -> None:
        baseline = demo.read_json(demo.DATA_DIR / "baseline_results.json")
        candidate = demo.read_json(demo.DATA_DIR / "candidate_results.json")
        tickets = demo.read_jsonl(demo.DATA_DIR / "customer_support_tickets.jsonl")
        self.assertEqual(
            demo.comparison_payload(baseline, candidate)["decision"], demo.ACCEPT
        )
        for key, value in (
            ("quality_score", "0.5"),
            ("estimated_cost_usd", "12"),
            ("average_latency_seconds", "3"),
        ):
            with self.subTest(metric=key):
                comparison = demo.comparison_payload(
                    baseline, {**candidate, key: value}
                )
                report = demo.report_payload(tickets, comparison)
                self.assertEqual(comparison["decision"], demo.RETAIN)
                self.assertNotIn(demo.ACCEPT, demo.render_report(report))
                self.assertEqual(
                    demo.route_plan_payload(tickets, comparison)["summary"]["routes"][
                        "candidate_model"
                    ],
                    0,
                )
                self.assertEqual(
                    demo.aimeter_summary(report)["outcome"]["decision"], demo.RETAIN
                )

    def test_zero_baseline_fails_before_generating_recommendation(self) -> None:
        baseline = demo.read_json(demo.DATA_DIR / "baseline_results.json")
        with self.assertRaisesRegex(ValueError, "positive baseline"):
            demo.comparison_payload({**baseline, "estimated_cost_usd": "0"}, baseline)

    def test_manifest_defaults_and_cli_overrides(self) -> None:
        defaults = demo.resolve_thresholds([])
        self.assertEqual(defaults.minimum_estimated_cost_reduction_pct, 15)
        custom = demo.resolve_thresholds(
            [
                "--minimum-quality-retention-pct",
                "95",
                "--minimum-estimated-cost-reduction-pct",
                "92",
                "--maximum-latency-increase-pct",
                "5",
            ]
        )
        baseline = demo.read_json(demo.DATA_DIR / "baseline_results.json")
        candidate = demo.read_json(demo.DATA_DIR / "candidate_results.json")
        lower_savings = demo.comparison_payload(
            baseline, {**candidate, "estimated_cost_usd": "10.00"}, defaults
        )
        self.assertEqual(lower_savings["decision"], demo.ACCEPT)
        comparison = demo.comparison_payload(baseline, candidate, custom)
        self.assertEqual(comparison["decision"], demo.RETAIN)
        self.assertEqual(comparison["thresholds"], custom.to_record())

        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "config.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "linux-of-ai.vendor-exit-demo-config.v1",
                        "thresholds": {
                            "minimum_quality_retention_pct": "80",
                            "minimum_estimated_cost_reduction_pct": "10",
                            "maximum_latency_increase_pct": "40",
                        },
                    }
                ),
                encoding="utf-8",
            )
            configured = demo.resolve_thresholds(["--manifest", str(manifest)])
        self.assertEqual(configured.minimum_estimated_cost_reduction_pct, 10)
        self.assertEqual(
            demo.comparison_payload(baseline, candidate, configured)["decision"],
            demo.ACCEPT,
        )
