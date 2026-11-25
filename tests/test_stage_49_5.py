"""Stage 49-5: acknowledgment text, work schedules, measurement, and a killed process."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from osamp.agreements import AgreementBook
from osamp.conformance import _boot
from osamp.errors import OsampError

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("bash 9.sh", "./9.sh", "source 9.sh", "sh 9.sh", ".\\9.sh")


class Stage495Tests(unittest.TestCase):
    def test_acknowledgment_text_is_what_gets_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            node, _keys = _boot(Path(directory))
            text = node.acknowledgment_text()
            self.assertIn("Stopping does not undo mail already sent", text)
            self.assertIn("explicit closure", text)
            self.assertIn("named deputy", text)
            self.assertIn("Installation, a license key, and opening a file are not this acknowledgment", text)
            ack = node.current_acknowledgment()
            self.assertEqual(ack["digest"], node.profile.governance_digest)
            self.assertIn(text, node.profile.material()["promise_text"])

    def test_project_and_corridor_schedules_are_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            node, keys = _boot(Path(directory))
            book = AgreementBook(node)
            with self.assertRaises(OsampError):
                book.propose_project("", ["one"], [], 1)
            project = book.propose_project(
                "Tighten one sentence",
                ["one sentence"],
                ["spell"],
                4,
                exclusions=["a second document"],
            )
            book.accept_work(project, "human-example", keys["human"])
            schedule = book.project_schedule(project)
            self.assertEqual(schedule["exclusions"], ["a second document"])
            self.assertEqual(schedule["required_checks"], ["spell"])
            self.assertIn("named human", schedule["completion_authority"])
            corridor = book.propose_corridor(
                [{"stage_id": "read", "recipient": "worker-b", "cost": 1}],
                3,
            )
            shown = book.corridor_schedule(corridor)
            self.assertEqual(shown["stop_rules"], ["solved", "human_satisfied", "held", "expired_or_closed"])
            self.assertEqual(shown["stages"][0]["recipient"], "worker-b")

    def test_stage_entry_is_offline(self):
        for name in ("49-5.sh", "49-5-mac.sh", "49-5-windows.ps1"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for pattern in FORBIDDEN:
                self.assertNotIn(pattern, text, name)
        before = set(os.listdir(ROOT))
        result = subprocess.run(
            ["bash", str(ROOT / "49-5.sh"), "--status"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("network=none", result.stdout)
        self.assertIn("Human acknowledgment", result.stdout)
        self.assertEqual(set(os.listdir(ROOT)), before)


if __name__ == "__main__":
    unittest.main()
