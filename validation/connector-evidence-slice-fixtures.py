#!/usr/bin/env python3
"""Focused disposable-manifest tests for connector evidence projection."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMAND = ROOT / "lib" / "connector-evidence-slice.py"


class ConnectorEvidenceSliceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manifest = pathlib.Path(self.tmp.name) / "manifest.json"
        self.manifest.write_text(json.dumps({"connectors": [
            {"id": "cloudflare-api", "tier": "OPTIONAL", "surfaces": {
                "codex-cli": {"support": "UNQUALIFIED", "health": "UNAVAILABLE"},
                "local-shell": {"support": "UNKNOWN"}}},
            {"id": "other", "tier": "OPTIONAL", "surfaces": {"codex-cli": {"secret": "not-selected"}}}
        ], "padding": "x" * 100000}))

    def call(self, *extra):
        return subprocess.run([sys.executable, str(COMMAND), "--manifest", str(self.manifest),
            "--id", "cloudflare-api", "--surface", "codex-cli", *extra],
            capture_output=True, text=True)

    def test_bounded_projection_and_unknown_transport(self):
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stderr)
        result_json = json.loads(result.stdout)
        self.assertLess(len(result.stdout.encode()), 48 * 1024)
        self.assertEqual(result_json["source_transport_bytes"], "UNKNOWN")
        self.assertGreater(result_json["source_bytes_read_locally"], 100000)
        self.assertEqual(len(result_json["selected"]), 1)
        self.assertNotIn("not-selected", result.stdout)
        self.assertNotIn("local-shell", result.stdout)

    def test_output_budget_fails_closed(self):
        result = self.call("--max-output-bytes", "15")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("EVIDENCE_INCOMPLETE", result.stderr)

    def test_no_unknown_connector_is_invented(self):
        result = self.call("--id", "missing")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["missing_ids"], ["missing"])


if __name__ == "__main__":
    unittest.main()
