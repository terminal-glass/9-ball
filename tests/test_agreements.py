"""Edges for the five negotiated agreements."""

import tempfile
import unittest
from pathlib import Path

from osamp.agreements import AgreementBook
from osamp.conformance import _accept, _boot, _offer, _role_accept_fields
from osamp.errors import OsampError


class AgreementTests(unittest.TestCase):
    def test_revoked_peer_and_narrow_message_type_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            node, keys = _boot(Path(directory))
            book = AgreementBook(node)
            peer = book.propose_peer("owner-b", "worker-b", ["PEER_INVITE"], ["public-example"])
            book.accept_peer(peer, "human-example", keys["human"])
            _offer(node, "wrong-type")
            with self.assertRaises(OsampError) as caught:
                _accept(node, "wrong-type")
            self.assertEqual(caught.exception.code, "outside_peer")
            book.revoke_peer(peer, "human-example", keys["human"])
            with self.assertRaises(OsampError) as caught:
                _offer(node, "after-revoke")
            self.assertEqual(caught.exception.code, "peer_revoked")
            self.assertEqual(node.model_calls(), 0)
            self.assertIsNone(node.postbox.obligation_by_event("wrong-type"))

    def test_project_completion_needs_every_check(self):
        with tempfile.TemporaryDirectory() as directory:
            node, keys = _boot(Path(directory))
            book = AgreementBook(node)
            project = book.propose_project("Tighten one sentence", ["one sentence"], ["spell", "source"], 4)
            book.accept_work(project, "human-example", keys["human"])
            book.record_project_check(project, "spell", True)
            with self.assertRaises(OsampError):
                book.complete_project(project)
            book.record_project_check(project, "source", False)
            with self.assertRaises(OsampError):
                book.complete_project(project)
            book.record_project_check(project, "source", True)
            book.complete_project(project)
            self.assertEqual(book._get(project)["body"]["outcome"], "completed")
            self.assertEqual(book._get(project)["body"]["spent"], 0)

    def test_table_acceptance_does_not_create_a_second_table_role(self):
        with tempfile.TemporaryDirectory() as directory:
            node, keys = _boot(Path(directory))
            book = AgreementBook(node)
            book.accept_peer(
                book.propose_peer("owner-b", "worker-b", ["WORK_OFFER"], ["public-example"]),
                "human-example",
                keys["human"],
            )
            _offer(node, "only")
            table = book.propose_table("project-one", "editor", "worker-b")
            book.accept_table_role(
                table,
                "editor",
                "human-example",
                keys["human"],
                **_role_accept_fields("only", "one-work"),
            )
            self.assertEqual(len(node.postbox.list_obligations()), 1)

    def test_revoked_peer_cannot_be_accepted_again(self):
        with tempfile.TemporaryDirectory() as directory:
            node, keys = _boot(Path(directory))
            book = AgreementBook(node)
            peer = book.propose_peer("owner-b", "worker-b", ["WORK_OFFER"], ["public-example"])
            book.accept_peer(peer, "human-example", keys["human"])
            book.revoke_peer(peer, "human-example", keys["human"])
            with self.assertRaises(OsampError) as caught:
                book.accept_peer(peer, "human-example", keys["human"])
            self.assertEqual(caught.exception.code, "agreement_not_offered")
            self.assertEqual(book._get(peer)["status"], "revoked")

    def test_empty_peer_lists_allow_nothing_including_medical_mail(self):
        from osamp.canonical import digest

        with tempfile.TemporaryDirectory() as directory:
            node, keys = _boot(Path(directory))
            book = AgreementBook(node)
            peer = book.propose_peer("owner-b", "worker-b", [], [])
            book.accept_peer(peer, "human-example", keys["human"])
            payload = {"text": "non-sensitive placeholder"}
            node.receive(
                {
                    "event_id": "medical-offer",
                    "event_type": "WORK_OFFER",
                    "sender_key_id": "worker-b",
                    "recipient_key_id": "worker-a",
                    "sent_at": node.clock.now(),
                    "expires_at": "2026-11-25T00:00:00+00:00",
                    "payload": payload,
                    "payload_digest": digest(payload),
                    "data_class": "private-medical",
                }
            )
            with self.assertRaises(OsampError) as caught:
                _accept(node, "medical-offer", work_id="should-not-accept")
            self.assertEqual(caught.exception.code, "outside_peer")
            self.assertIsNone(node.postbox.obligation_by_event("medical-offer"))

    def test_a_completed_project_stays_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            node, keys = _boot(Path(directory))
            book = AgreementBook(node)
            project = book.propose_project("Tighten one sentence", ["one sentence"], ["spell"], 4)
            book.accept_work(project, "human-example", keys["human"])
            book.record_project_check(project, "spell", True)
            book.complete_project(project)
            with self.assertRaises(OsampError) as caught:
                book.record_project_check(project, "spell", True)
            self.assertEqual(caught.exception.code, "complete_refused")
            self.assertEqual(book._get(project)["status"], "closed")
            self.assertEqual(book._get(project)["body"]["outcome"], "completed")

    def test_agreement_acceptance_requires_contract_zero_acknowledgment(self):
        from osamp.clock import Clock
        from osamp.node import Node

        with tempfile.TemporaryDirectory() as directory:
            node = Node.open(str(Path(directory) / "postbox.sqlite"), clock=Clock())
            node.register_person("human-example", b"human-key-example")
            book = AgreementBook(node)
            peer = book.propose_peer("owner-b", "worker-b", ["WORK_OFFER"], ["public-example"])
            with self.assertRaises(OsampError) as caught:
                book.accept_peer(peer, "human-example", b"human-key-example")
            self.assertEqual(caught.exception.code, "ack_required")
            self.assertEqual(book._get(peer)["status"], "offered")


if __name__ == "__main__":
    unittest.main()
