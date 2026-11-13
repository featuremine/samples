"""Optional real local integration; set TITAN_TEST_FIXTURE to its executable."""

import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = os.environ.get("TITAN_TEST_FIXTURE")


@unittest.skipUnless(FIXTURE, "TITAN_TEST_FIXTURE is not set")
class TitanIntegrationTests(unittest.TestCase):
    def test_seeded_orders_over_both_transports(self):
        # All generated files remain under Samples, never in a saved user session.
        with tempfile.TemporaryDirectory(prefix="titan-test-", dir=ROOT) as directory:
            fixture_file = Path(directory) / "fixture.json"
            process = subprocess.Popen(
                [FIXTURE, "--directory", directory, "--output", str(fixture_file)],
                cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True)
            try:
                readable, _, _ = select.select([process.stdout], [], [], 15)
                self.assertTrue(readable, "Local fixture did not become ready")
                self.assertEqual(process.stdout.readline().strip(), "ready", "Local fixture startup failed")
                with fixture_file.open(encoding="utf-8") as source:
                    configuration = json.load(source)
                for transport in ("tcp", "websocket"):
                    with self.subTest(transport=transport):
                        result = subprocess.run(
                            [sys.executable, "-B", str(ROOT / "titan-test.py"),
                             "--fixture", str(fixture_file), "--transport", transport,
                             "--seed", "7", "--orders", "24", "--timeout", "20", "--verbose"],
                            cwd=ROOT, capture_output=True, text=True, timeout=25)
                        output = result.stdout + result.stderr
                        for key in ("host", "token"):
                            self.assertFalse(configuration[key] in output,
                                             "Sensitive fixture value appeared in tester output")
                        reason = "Local tester reported an integration failure"
                        if result.returncode and result.stderr:
                            try:
                                failure = json.loads(result.stderr.splitlines()[-1])
                                reason += ": " + failure.get("reason", "No structured reason")
                            except (ValueError, TypeError):
                                pass
                        self.assertEqual(result.returncode, 0, reason)
                        self.assertIn("Order 1: submit ", result.stdout)
                        self.assertIn("Order 24: submit ", result.stdout)
                        self.assertIn("submit buy ", result.stdout)
                        self.assertIn("submit sell ", result.stdout)
                        summary = json.loads(result.stdout.splitlines()[-1])
                        self.assertEqual(summary, {"status": "passed", "transport": transport,
                                                  "seed": 7, "submitted": 24, "completed": 24})
            finally:
                try:
                    process.communicate("\n", timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                self.assertEqual(process.returncode, 0, "Local fixture did not stop cleanly")


if __name__ == "__main__":
    unittest.main()
