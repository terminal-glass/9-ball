"""Extra local checks that sit beside the numbered conformance report."""

import tempfile
import threading
import unittest
from pathlib import Path

from osamp.conformance import _accept, _boot, _offer
from osamp.errors import OsampError
from osamp.node import Node


class FoundationTests(unittest.TestCase):
    def test_delivery_authority_and_execution_stay_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            node, _keys = _boot(Path(directory))
            _offer(node)
            self.assertEqual(node.postbox.get_envelope("offer-1")["delivery_state"], "delivered")
            self.assertEqual(node.postbox.get_envelope("offer-1")["role_state"], "offered")
            self.assertIsNone(node.postbox.obligation_by_event("offer-1"))
            obligation_id = _accept(node)
            node.play(obligation_id)
            obligation = node.postbox.get_obligation(obligation_id)
            envelope = node.postbox.get_envelope("offer-1")
            self.assertEqual(envelope["delivery_state"], "delivered")
            self.assertEqual(obligation["authority_state"], "accepted")
            self.assertEqual(obligation["execution_state"], "working")

    def test_unknown_event_and_unadopted_signature_do_not_wake_work(self):
        with tempfile.TemporaryDirectory() as directory:
            node, _keys = _boot(Path(directory))
            unknown = node.receive(
                {
                    "event_id": "weird-1",
                    "event_type": "MAKE_IT_SO",
                    "sender_key_id": "worker-b",
                    "recipient_key_id": "worker-a",
                    "sent_at": node.clock.now(),
                    "payload": {"text": "go"},
                    "payload_digest": "sha256:irrelevant",
                }
            )
            signed = node.receive(
                {
                    "event_id": "signed-1",
                    "event_type": "WORK_OFFER",
                    "sender_key_id": "worker-b",
                    "recipient_key_id": "worker-a",
                    "sent_at": node.clock.now(),
                    "payload": {"text": "go"},
                    "payload_digest": "sha256:irrelevant",
                    "signature": "not-a-real-suite",
                }
            )
            self.assertEqual(unknown["code"], "unknown_event")
            self.assertEqual(signed["code"], "signature_not_adopted")
            self.assertEqual(node.model_calls(), 0)
            self.assertEqual(node.postbox.list_obligations(), [])

    def test_hold_on_one_task_does_not_stop_another(self):
        with tempfile.TemporaryDirectory() as directory:
            node, _keys = _boot(Path(directory))
            _offer(node, "one")
            _offer(node, "two")
            first = _accept(node, "one", work_id="one")
            second = _accept(node, "two", work_id="two")
            node.request_hold(first, "conflicting_evidence", "Which source?")
            node.play(second)
            self.assertEqual(node.postbox.get_obligation(second)["execution_state"], "working")
            with self.assertRaises(OsampError):
                node.play(first)

    def test_freeze_is_not_cleared_by_a_human_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            node, keys = _boot(Path(directory))
            _offer(node)
            obligation_id = _accept(node)
            node.freeze_authority("task", obligation_id, "suspicious key use")
            obligation = node.postbox.get_obligation(obligation_id)
            from osamp.auth import mac
            from osamp.conformance import _decision

            decision = _decision(obligation, "approve_same_step", "human-example", step_id="approve_same_step")
            result = node.resolve_human(decision, keys["human"], mac(keys["human"], decision))
            self.assertFalse(result["resumed"])
            self.assertNotEqual(node.postbox.get_obligation(obligation_id)["execution_state"], "working")
            with self.assertRaises(OsampError):
                node.play(obligation_id)

    def test_operator_pause_can_resume_and_lease_does_not_renew_itself(self):
        with tempfile.TemporaryDirectory() as directory:
            node, _keys = _boot(Path(directory))
            _offer(node)
            obligation_id = _accept(node)
            node.play(obligation_id)
            node.pause(obligation_id)
            node.play(obligation_id)
            self.assertEqual(node.dispatch_tool(obligation_id, "format-check"), "tool-ok")
            self.assertEqual(node.model_calls(), 0)
            self.assertEqual(node.tool_calls(), 1)
            node.clock.advance(node.profile.limits["lease_seconds"] + 1)
            with self.assertRaises(OsampError) as caught:
                node.dispatch_tool(obligation_id, "format-check")
            self.assertEqual(caught.exception.code, "lease_expired")
            self.assertEqual(node.postbox.get_obligation(obligation_id)["execution_state"], "held")
            self.assertEqual(node.tool_calls(), 1)

    def test_two_accepts_of_one_offer_create_one_obligation(self):
        with tempfile.TemporaryDirectory() as directory:
            node, _keys = _boot(Path(directory))
            _offer(node)
            path = node.postbox.path
            clock = node.clock
            errors = []
            ids = []

            def worker():
                other = Node.open(path, clock=clock)
                try:
                    ids.append(_accept(other))
                except Exception as exc:
                    errors.append(exc)
                finally:
                    other.close()

            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(set(ids)), 1)
            self.assertEqual(len(node.postbox.list_obligations()), 1)
            remaining = node.postbox.conn.execute(
                "SELECT remaining_accepts FROM delegations"
            ).fetchone()["remaining_accepts"]
            self.assertEqual(remaining, 9)


if __name__ == "__main__":
    unittest.main()
