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


if __name__ == "__main__":
    unittest.main()
