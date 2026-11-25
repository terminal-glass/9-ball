"""Stage 49-4: data, retention, and security schedules."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from osamp.conformance import _accept, _boot, _offer
from osamp.errors import OsampError
from osamp.schedules import DATA_CLASSES, RETENTION, SECURITY, screen_notice, trace_rows

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("bash 9.sh", "./9.sh", "source 9.sh", "sh 9.sh", ".\\9.sh")


class ScheduleTests(unittest.TestCase):
    def test_schedule_text_names_the_local_rules(self):
        self.assertIn("private-medical", DATA_CLASSES)
        self.assertIn("offsite_backups", RETENTION)
        self.assertEqual(RETENTION["offsite_backups"], "None are declared. This copy cannot delete a copy it does not have.")
        self.assertIn("notices", SECURITY)
        rows = {item[0] for item in trace_rows()}
        self.assertTrue({"B-DATA01", "B-QUEUE04", "B-SEC01", "P-Z09"}.issubset(rows))

    def test_a_notice_cannot_carry_a_secret_field(self):
        with self.assertRaises(OsampError) as caught:
            screen_notice({"question": "Review this.", "password": "not-a-real-secret"})
        self.assertEqual(caught.exception.code, "notice_refused")

    def test_invitation_text_leaves_the_backup_and_the_objective_stays(self):
        with tempfile.TemporaryDirectory() as directory:
            node, _keys = _boot(Path(directory))
            phrase = "backup-invitation-phrase"
            _offer(node, payload={"text": phrase})
            _offer(node, "kept", payload={"text": "other"})
            _accept(node, "kept", objective="backup-objective-stays")
            self.assertIn(b"backup-invitation-phrase", Path(node.postbox.backup_path).read_bytes())
            node.clock.advance(3 * 24 * 3600)
            node.expire_invitations()
            backup = Path(node.postbox.backup_path).read_bytes()
            self.assertNotIn(b"backup-invitation-phrase", backup)
            self.assertIn(b"backup-objective-stays", backup)
            self.assertEqual(node.postbox.backup_policy()["offsite_backups"], "none")

    def test_stage_entry_is_offline(self):
        for name in ("49-4.sh", "49-4-mac.sh", "49-4-windows.ps1"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for pattern in FORBIDDEN:
                self.assertNotIn(pattern, text, name)
        before = set(os.listdir(ROOT))
        result = subprocess.run(
            ["bash", str(ROOT / "49-4.sh"), "--dry-run"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("network=none", result.stdout)
        self.assertIn("Data schedule", result.stdout)
        self.assertEqual(set(os.listdir(ROOT)), before)


if __name__ == "__main__":
    unittest.main()
