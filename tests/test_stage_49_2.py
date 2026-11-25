"""Stage 49-2 is present for every platform and does not call stage 9."""

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("bash 9.sh", "./9.sh", "source 9.sh", "sh 9.sh", ".\\9.sh")


def _run(script: str, verb: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(ROOT / script), verb],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class Stage492Tests(unittest.TestCase):
    def test_scripts_do_not_invoke_stage_9(self):
        for name in ("49-2.sh", "49-2-mac.sh", "49-2-windows.ps1"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for pattern in FORBIDDEN:
                self.assertNotIn(pattern, text, name)

    def test_controller_runs_both_groups(self):
        before = set(os.listdir(ROOT))
        result = _run("49.sh", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("49-1 piece 1: Contract Zero", result.stdout)
        self.assertIn("49-2 piece 1: Peer contract", result.stdout)
        self.assertIn("network=none", result.stdout)
        mac = _run("49-mac.sh", "--status")
        self.assertEqual(mac.returncode, 0, mac.stderr)
        self.assertIn("platform=macos", mac.stdout)
        self.assertIn("Peer contract", mac.stdout)
        self.assertEqual(set(os.listdir(ROOT)), before)

    def test_verify_runs_the_agreement_checks(self):
        result = _run("49-2.sh", "--verify")
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("OK", combined)


if __name__ == "__main__":
    unittest.main()
