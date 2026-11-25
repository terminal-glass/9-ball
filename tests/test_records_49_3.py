"""Stage 49-3 behavior: receipts, catch-up, restore, and the ledger."""

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from osamp.auth import mac
from osamp.conformance import _accept, _boot, _decision, _offer, run_all
from osamp.errors import OsampError
from osamp.node import Node


class RecordTests(unittest.TestCase):
    def test_delivery_receipt_does_not_accept_the_role(self):
        with tempfile.TemporaryDirectory() as directory:
            node, _keys = _boot(Path(directory))
            _offer(node)
            receipts = node.postbox.list_receipts()
            self.assertEqual([item["kind"] for item in receipts], ["delivery"])
            self.assertIsNone(receipts[0]["obligation_id"])
            self.assertIsNone(node.postbox.obligation_by_event("offer-1"))
            self.assertEqual(node.postbox.get_envelope("offer-1")["role_state"], "offered")

    def test_restore_keeps_revocation_and_spent_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node, _keys = _boot(root)
            _offer(node)
            obligation_id = _accept(node, budget_ceiling=5)
            node.play(obligation_id)
            node.snapshot(str(root / "before.sqlite"))
            node.note_progress(obligation_id, "step", cost=2)
            node.revoke_work(obligation_id)
            node = node.restore_from_snapshot(str(root / "before.sqlite"))
            restored = node.postbox.get_obligation(obligation_id)
            self.assertEqual(restored["authority_state"], "revoked")
            self.assertEqual(restored["budget_spent"], 2)
            with self.assertRaises(OsampError):
                node.play(obligation_id)
            with self.assertRaises(OsampError):
                node.submit_result(obligation_id, "sha256:late", True)

    def test_closed_tombstone_scrubs_the_capsule_after_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node, keys = _boot(root)
            phrase = "capsule-objective-must-vanish"
            _offer(node)
            obligation_id = _accept(node, objective=phrase)
            node.snapshot(str(root / "before-close.sqlite"))
            node.request_hold(obligation_id, "timeout", "Please close this.")
            obligation = node.postbox.get_obligation(obligation_id)
            decision = _decision(obligation, "terminate", "human-example")
            node.resolve_human(decision, keys["human"], mac(keys["human"], decision))
            node = node.restore_from_snapshot(str(root / "before-close.sqlite"))
            restored = node.postbox.get_obligation(obligation_id)
            self.assertIsNone(restored["objective"])
            self.assertIsNone(restored["capsule"].get("objective"))
            self.assertFalse(node.export_minimal(obligation_id)["objective_present"])
            self.assertNotIn(phrase.encode(), Path(node.postbox.path).read_bytes())

    def test_failed_commit_does_not_keep_a_tombstone_and_a_crash_does(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node, _keys = _boot(root)
            _offer(node)
            obligation_id = _accept(node)
            node.postbox.fail_next_commit()
            with self.assertRaises(OsampError) as caught:
                node.revoke_work(obligation_id)
            self.assertEqual(caught.exception.code, "commit_failed")
            node = node.reopen()
            self.assertEqual(node.postbox.get_obligation(obligation_id)["authority_state"], "accepted")

            database = node.postbox.path
            node.close()
            script = textwrap.dedent(
                f"""
                from osamp.node import Node
                node = Node.open({database!r})
                node.postbox.crash_before_sql_commit = True
                node.revoke_work({obligation_id!r})
                """
            )
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(Path(__file__).resolve().parents[1]),
                check=False,
            )
            self.assertEqual(completed.returncode, 99)
            reopened = Node.open(database)
            self.assertEqual(reopened.postbox.get_obligation(obligation_id)["authority_state"], "revoked")
            reopened.close()

    def test_ledger_has_no_failures(self):
        results = run_all()
        failed = [item.check_id for item in results if item.status == "fail"]
        self.assertEqual(failed, [])
        self.assertEqual(len(results), 29)


if __name__ == "__main__":
    unittest.main()
