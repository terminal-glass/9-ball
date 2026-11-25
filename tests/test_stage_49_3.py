"""Stage 49-3 entry points stay offline and do not call stage 9."""

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


class Stage493Tests(unittest.TestCase):
    def test_scripts_and_controller(self):
        for name in ("49-3.sh", "49-3-mac.sh", "49-3-windows.ps1"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for pattern in FORBIDDEN:
                self.assertNotIn(pattern, text, name)
        before = set(os.listdir(ROOT))
        dry = _run("49.sh", "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn("49-3 piece 1:", dry.stdout)
        self.assertIn("network=none", dry.stdout)
        self.assertEqual(set(os.listdir(ROOT)), before)

    def test_verify_runs_the_record_checks(self):
        result = _run("49-3.sh", "--verify")
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("OK", combined)


if __name__ == "__main__":
    unittest.main()
