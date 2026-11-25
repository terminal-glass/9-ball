"""Stage 49-6: shared vectors, adapter B, and the requirement trace."""

import os
import subprocess
import unittest
from pathlib import Path

from osamp.conformance import CHECKS, REQUIREMENTS
from osamp.trace import lines

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("bash 9.sh", "./9.sh", "source 9.sh", "sh 9.sh", ".\\9.sh")


class Stage496Tests(unittest.TestCase):
    def test_every_check_has_a_requirement_label(self):
        ids = [item[0] for item in CHECKS]
        self.assertEqual(len(ids), 29)
        self.assertEqual(set(ids), set(REQUIREMENTS))
        traced = lines()
        self.assertEqual(len(traced), 29)
        self.assertTrue(all(row.split()[1] for row in traced))

    def test_adapter_b_does_not_import_the_reference(self):
        text = (ROOT / "adapter-b.py").read_text(encoding="utf-8")
        self.assertNotIn("import osamp", text)
        self.assertNotIn("from osamp", text)

    def test_stage_entry_is_offline(self):
        for name in ("49-6.sh", "49-6-mac.sh", "49-6-windows.ps1"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for pattern in FORBIDDEN:
                self.assertNotIn(pattern, text, name)
        before = set(os.listdir(ROOT))
        result = subprocess.run(
            ["bash", str(ROOT / "49-6.sh"), "--dry-run"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("network=none", result.stdout)
        self.assertIn("Shared envelope vectors", result.stdout)
        self.assertEqual(set(os.listdir(ROOT)), before)


if __name__ == "__main__":
    unittest.main()
