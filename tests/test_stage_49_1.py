"""Stage 49-1 and the controller stay offline and do not call stage 9."""

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


class Stage49FoundationTests(unittest.TestCase):
    def test_scripts_do_not_invoke_stage_9(self):
        names = [
            "49.sh",
            "49-1.sh",
            "49-mac.sh",
            "49-1-mac.sh",
            "49-windows.ps1",
            "49-1-windows.ps1",
            "OpenClaw-Installer-Linux",
            "OpenClaw-Installer-Mac",
            "OpenClaw-Installer-Windows",
            "OSAMP-Linux",
            "OSAMP-Mac",
            "OSAMP-Windows",
        ]
        for name in names:
            text = (ROOT / name).read_text(encoding="utf-8")
            for pattern in FORBIDDEN:
                self.assertNotIn(pattern, text, name)

    def test_controller_and_substage_flags(self):
        before = set(os.listdir(ROOT))
        for script in ("49.sh", "49-1.sh", "49-mac.sh", "49-1-mac.sh", "OpenClaw-Installer-Linux", "OSAMP-Linux"):
            helped = _run(script, "--help")
            self.assertEqual(helped.returncode, 0, helped.stderr)
            self.assertIn("Stage 9 is not called", helped.stdout)
            for verb in ("--dry-run", "--status"):
                result = _run(script, verb)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("network=none", result.stdout)
                self.assertIn("jet_stage_9=untouched", result.stdout)
        self.assertIn("Contract Zero", _run("49-1.sh", "--dry-run").stdout)
        self.assertEqual(set(os.listdir(ROOT)), before)
        unknown = _run("49.sh", "--nope")
        self.assertEqual(unknown.returncode, 2)

    def test_verify_runs_the_foundation_checks(self):
        result = _run("49-1.sh", "--verify")
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("OK", combined)


if __name__ == "__main__":
    unittest.main()
