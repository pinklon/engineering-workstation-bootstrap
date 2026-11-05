import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "workstation-capability"


class FastInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.home = root / "home"
        release = self.home / ".local/share/engineering-workstation-bootstrap/current/runtime"
        (release / "lib").mkdir(parents=True)
        (release / "manifests").mkdir()
        (release / "manifests/connector-capabilities.json").write_text(json.dumps({
            "connectors": [{"id": "cloudflare-api", "tier": "REQUIRED", "surfaces": {
                "codex-cli": {"support": "UNQUALIFIED", "health": "UNAVAILABLE"}}}]
        }))
        # Simulates only the pinned projection contract, not a second catalog.
        (release / "lib/connector-evidence-slice.py").write_text(
            "import argparse,json,sys\n"
            "p=argparse.ArgumentParser();p.add_argument('--manifest');p.add_argument('--id');"
            "p.add_argument('--surface');p.add_argument('--max-output-bytes',type=int);a=p.parse_args();"
            "out=json.dumps({'id':a.id,'surface':a.surface,'status':'UNQUALIFIED'})+'\\n';"
            "sys.exit(2) if len(out.encode())>a.max_output_bytes else sys.stdout.write(out)\n"
        )

    def call(self, *args):
        return subprocess.run(["bash", str(SCRIPT), "--id", "cloudflare-api", "--surface",
                               "codex-cli", *args], env={**os.environ, "HOME": str(self.home)},
                              capture_output=True, text=True)

    def test_success_is_small_and_read_only(self):
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "UNQUALIFIED")
        self.assertLess(len(result.stdout), 2048)

    def test_missing_release_fails_closed(self):
        helper = self.home / ".local/share/engineering-workstation-bootstrap/current/runtime/lib/connector-evidence-slice.py"
        helper.unlink()
        result = self.call()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("EVIDENCE_INCOMPLETE", result.stderr)

    def test_tight_limit_fails_closed(self):
        result = self.call("--max-output-bytes", "4")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
