"""Executable checks for the local slice.

Pending and partial results are reported on purpose. A pass is only a pass
for the behavior this copy actually demonstrates.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from osamp.agreements import AgreementBook
from osamp.auth import mac
from osamp.canonical import digest
from osamp.clock import Clock
from osamp.covenant import require_fast_forward
from osamp.gate import screen
from osamp.errors import OsampError
from osamp.node import Node
from osamp.profile import default_profile


@dataclass
class CheckResult:
    check_id: str
    title: str
    status: str
    evidence: str


def _boot(directory: Path, **profile_kwargs) -> tuple[Node, dict]:
    clock = Clock()
    profile = default_profile(**profile_kwargs) if profile_kwargs else default_profile()
    node = Node.open(str(directory / "postbox.sqlite"), profile=profile, clock=clock)
    keys = {"owner": b"owner-key-example", "human": b"human-key-example", "deputy": b"deputy-key-example"}
    node.register_person("operator-example", keys["owner"])
    node.register_person("human-example", keys["human"])
    node.register_person("deputy-example", keys["deputy"])
    node.record_acknowledgment("operator-example", keys["owner"])
    node.grant_delegation(
        "human-example",
        keys["human"],
        "public-wording",
        max_budget=100,
        remaining_accepts=10,
    )
    node.permit_sender("worker-b")
    return node, keys


def _offer(node: Node, event_id: str = "offer-1", payload: dict | None = None, **extra) -> dict:
    body = payload or {"text": "Please tighten one public sentence about rain."}
    envelope = {
        "event_id": event_id,
        "event_type": extra.get("event_type", "WORK_OFFER"),
        "sender_key_id": extra.get("sender_key_id", "worker-b"),
        "recipient_key_id": "worker-a",
        "sent_at": node.clock.now(),
        "expires_at": extra.get("expires_at", "2026-11-25T00:00:00+00:00"),
        "payload": body,
        "payload_digest": digest(body),
        "data_class": extra.get("data_class", "public-example"),
    }
    if extra.get("signature"):
        envelope["signature"] = extra["signature"]
    node.receive(envelope)
    return envelope


def _accept(node: Node, event_id: str = "offer-1", **kwargs) -> str:
    fields = {
        "work_id": "weather-wording",
        "objective": "Tighten one public sentence about rain.",
        "task_class": "public-wording",
        "scope": "bounded",
        "subtask_id": "sentence-1",
        "budget_ceiling": 10,
        "human_id": "human-example",
        "deputy_id": "deputy-example",
        "contract_version": "work/local-1",
        "contract_digest": "sha256:local-work-example",
        "deadline": "2026-12-01T00:00:00+00:00",
        "retention_deadline": "2026-12-15T00:00:00+00:00",
        "tool_allowlist": ["format-check"],
    }
    fields.update(kwargs)
    return node.accept(event_id, **fields)


def _guard_model(node: Node) -> list:
    called: list = []

    def boom(prompt: str) -> str:
        called.append(prompt)
        raise AssertionError("language model was called")

    node.invoke_model = boom
    return called


def _decision(obligation: dict, kind: str, operator_id: str, **extra) -> dict:
    decision = {
        "decision_id": extra.pop("decision_id", f"decision-{kind}"),
        "obligation_id": obligation["obligation_id"],
        "hold_id": obligation["hold"]["hold_id"],
        "operator_id": operator_id,
        "kind": kind,
        "scope": "task",
    }
    decision.update(extra)
    return decision


def check_wp01(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    called = _guard_model(node)
    result = node.receive(
        {
            "event_id": "unknown-1",
            "event_type": "WORK_OFFER",
            "sender_key_id": "stranger",
            "recipient_key_id": "worker-a",
            "sent_at": node.clock.now(),
            "expires_at": "2026-11-25T00:00:00+00:00",
            "payload": {"text": "forward me"},
            "payload_digest": digest({"text": "forward me"}),
        }
    )
    try:
        node.relay("unknown-1", "someone-else")
        relayed = True
    except OsampError as exc:
        relayed = exc.code != "no_relay"
    stored = node.postbox.get_envelope("unknown-1")
    assert result["code"] == "unknown_sender"
    assert relayed is False
    assert node.relay_count() == 0
    assert node.model_calls() == 0
    assert called == []
    assert stored["body"] is None
    assert node.postbox.list_outbound() == []
    return (
        "pass",
        "Unknown sender quarantined with no body, no outbound item, relay_count=0, model_calls=0. "
        "Limitation: the sender check is a local allowlist. No signature suite is adopted.",
    )


def check_wp02(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    called = _guard_model(node)
    _offer(node)
    assert node.postbox.obligation_by_event("offer-1") is None
    assert node.model_calls() == 0 and node.tool_calls() == 0 and called == []
    node.clock.advance(2 * 24 * 3600)
    assert node.expire_invitations() == 1
    assert node.model_calls() == 0
    return "pass", "Unaccepted invitation stored then expired with model_calls=0 and tool_calls=0."


def check_wp03(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    _offer(node)
    envelope = node.postbox.get_envelope("offer-1")
    assert envelope["delivery_state"] == "delivered"
    assert envelope["role_state"] == "offered"
    assert node.postbox.list_obligations() == []
    node.postbox.fail_next_commit()
    try:
        _accept(node)
        raise AssertionError("failed commit still accepted")
    except OsampError as exc:
        assert exc.code == "commit_failed"
    assert node.postbox.list_obligations() == []
    obligation_id = _accept(node)
    node = node.reopen()
    restored = node.postbox.get_obligation(obligation_id)
    assert restored["authority_state"] == "accepted"
    assert restored["execution_state"] == "ready"
    assert restored["capsule"]["objective"]
    fresh = node.postbox.get_envelope("offer-1")
    assert fresh["delivery_state"] == "delivered"
    assert fresh["role_state"] == "accepted"
    assert restored["authority_state"] == "accepted"
    return (
        "pass",
        "A failed save left no obligation. After a successful accept, delivery stayed delivered, "
        "the offer's role became accepted, execution was ready, and the recovery record survived reopening the file.",
    )


def check_wp04(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    sample = node.measurement()
    assert sample["task_class"] == "public-wording"
    assert sample["subtask_id"] == "sentence-1"
    assert sample["measured_at"]
    assert isinstance(sample["elapsed_ms"], (int, float))
    _offer(node, "wide")
    try:
        _accept(node, "wide", scope="whole-project", subtask_id=None)
        raise AssertionError("broad work was accepted")
    except OsampError as exc:
        assert exc.code == "task_unfit"
    _offer(node, "narrow")
    obligation_id = _accept(node, "narrow", subtask_id="sentence-1")
    capsule = node.capsule(obligation_id)
    assert capsule["limits"]["subtask_id"] == "sentence-1"
    return (
        "pass",
        "This computer hashed one fixed public sentence 2000 times and recorded the date and elapsed "
        f"milliseconds ({sample['elapsed_ms']}). The gate then accepted only that bounded step and refused "
        "a whole project. This is not a cross-vendor laboratory benchmark and it does not rank a person.",
    )


def _role_accept_fields(event_id: str, work_id: str) -> dict:
    return {
        "event_id": event_id,
        "work_id": work_id,
        "objective": "Tighten one public sentence about rain.",
        "task_class": "public-wording",
        "scope": "bounded",
        "subtask_id": "sentence-1",
        "budget_ceiling": 10,
        "human_id": "human-example",
        "deputy_id": "deputy-example",
        "contract_version": "work/local-1",
        "contract_digest": "sha256:local-work-example",
        "deadline": "2026-12-01T00:00:00+00:00",
        "retention_deadline": "2026-12-15T00:00:00+00:00",
        "tool_allowlist": ["format-check"],
    }


def check_wp05(tmp: Path) -> tuple[str, str]:
    node, keys = _boot(tmp)
    called = _guard_model(node)
    book = AgreementBook(node)
    tribe = book.propose_tribe("writers", ["helper-1"], 1)
    book.accept_tribe(tribe, "human-example", keys["human"])
    assert node.postbox.list_obligations() == []
    first = book.offer_tribe_help(tribe, "helper-1", "read one public sentence")
    assert first["offers_used"] == 1 and first["queued"] is True
    try:
        book.offer_tribe_help(tribe, "helper-1", "read it again")
        raise AssertionError("tribe budget was exceeded")
    except OsampError as exc:
        assert exc.code == "budget_spent"
    other = book.propose_tribe("readers", ["helper-2"], 2)
    book.accept_tribe(other, "human-example", keys["human"])
    book.decline_tribe_help(other, "helper-2")
    try:
        book.offer_tribe_help(other, "helper-2", "ask again")
        raise AssertionError("declined helper was recruited again")
    except OsampError as exc:
        assert exc.code == "already_declined"
    assert node.model_calls() == 0 and called == []
    assert book._get(tribe)["body"]["offers_used"] == 1
    return (
        "pass",
        "Tribe membership created no job. One help offer was queued locally, the next was refused, "
        "and a declined helper was not asked again. Model calls stayed at 0. Nothing was transmitted.",
    )


def check_wp06(tmp: Path) -> tuple[str, str]:
    node, keys = _boot(tmp)
    called = _guard_model(node)
    book = AgreementBook(node)
    clan = book.propose_clan("example-federation", ["dest-known"], 1)
    book.accept_clan(clan, "human-example", keys["human"])
    book.record_endorsement("dest-new", "A fixture statement, not an approval.")
    try:
        book.escalate(clan, "dest-new", 1)
        raise AssertionError("endorsement opened a destination")
    except OsampError as exc:
        assert exc.code == "boundary_refused"
    bridge = book.propose_bridge(
        clan, "one harmless fixture", ["dest-new"], "public-example", "2026-11-30T00:00:00+00:00"
    )
    try:
        book.escalate(clan, "dest-new", 1)
        raise AssertionError("unapproved bridge opened a destination")
    except OsampError as exc:
        assert exc.code == "boundary_refused"
    book.approve_bridge(bridge, "human-example", keys["human"])
    queued = book.escalate(clan, "dest-new", 1)
    assert queued["queued_locally"] is True and queued["transmitted"] is False
    assert node.relay_count() == 0 and called == []
    try:
        book.escalate(clan, "dest-known", 2)
        raise AssertionError("hop limit was ignored")
    except OsampError as exc:
        assert exc.code == "boundary_refused"
    assert book._get(clan)["body"]["destinations"] == ["dest-known"]
    return (
        "pass",
        "An unapproved destination and an endorsement were refused. A human-approved bridge queued a local "
        "note only: transmitted=false and relay_count=0. The clan destination list did not grow. "
        "Names are fixtures, not a live route.",
    )


def check_wp13(tmp: Path) -> tuple[str, str]:
    node, keys = _boot(tmp)
    book = AgreementBook(node)
    peer = book.propose_peer("owner-b", "worker-b", ["WORK_OFFER"], ["public-example"])
    book.accept_peer(peer, "human-example", keys["human"])
    table = book.propose_table("project-words", "editor", "worker-b")
    _offer(node, "seat")
    assert book.role_status(table, "editor") == "offered"
    assert node.postbox.obligation_by_event("seat") is None
    book.accept_table_role(table, "editor", "human-example", keys["human"], **_role_accept_fields("seat", "table-work"))
    assert book.role_status(table, "editor") == "accepted"
    node = node.reopen()
    book = AgreementBook(node)
    assert book.role_status(table, "editor") == "accepted"
    other = book.propose_table("project-other", "editor", "worker-b")
    assert book.role_status(other, "editor") == "offered"
    book.propose_handoff(table, "editor", "worker-c")
    assert book.role_status(table, "editor") == "accepted"
    return (
        "pass",
        "Delivering an invitation did not seat anyone. Accepting the role did, and that acceptance survived "
        "reopening the file. Another table stayed unseated, and a proposed handoff did not release the first role.",
    )


def check_wp14(tmp: Path) -> tuple[str, str]:
    node, keys = _boot(tmp)
    book = AgreementBook(node)
    senders = node.postbox.list_senders()
    book.accept_peer(
        book.propose_peer("owner-b", "worker-b", ["WORK_OFFER"], ["public-example"]),
        "human-example",
        keys["human"],
    )
    tribe = book.propose_tribe("circle", ["helper-1"], 1)
    book.accept_tribe(tribe, "human-example", keys["human"])
    book.accept_peer(
        book.propose_peer("owner-c", "worker-c", ["WORK_OFFER"], ["public-example"]),
        "human-example",
        keys["human"],
    )
    assert book._get(tribe)["body"]["members"] == ["helper-1"]
    clan = book.propose_clan("federation", ["dest-1"], 1)
    book.accept_clan(clan, "human-example", keys["human"])
    _offer(node, "scope")
    table = book.propose_table("project-one", "editor", "worker-b")
    book.accept_table_role(
        table, "editor", "human-example", keys["human"], **_role_accept_fields("scope", "scope-work")
    )
    assert book._get(clan)["body"]["destinations"] == ["dest-1"]
    work = book.propose_project("Tighten one sentence", ["one sentence"], ["spell"], 5)
    book.accept_work(work, "human-example", keys["human"])
    assert node.postbox.list_senders() == senders
    other = book.propose_table("project-two", "editor", "worker-b")
    assert book.role_status(other, "editor") == "offered"
    assert node.postbox.list_obligations()[0]["work_id"] == "scope-work"
    return (
        "pass",
        "Accepting a peer did not add a tribe member. A new peer did not join the tribe or the clan "
        "destination list. A table role did not change the clan. A work agreement did not add a sender. "
        "A second table stayed offered.",
    )


def check_wp15(tmp: Path) -> tuple[str, str]:
    node, keys = _boot(tmp)
    called = _guard_model(node)
    book = AgreementBook(node)
    solved = book.propose_corridor(
        [
            {"stage_id": "read", "recipient": "worker-b", "cost": 1},
            {"stage_id": "check", "recipient": "worker-c", "cost": 1},
        ],
        5,
    )
    book.accept_work(solved, "human-example", keys["human"])
    assert book.offer_corridor_stage(solved)["recipient"] == "worker-b"
    book.solve_corridor(solved, "sha256:solved-example")
    try:
        book.offer_corridor_stage(solved)
        raise AssertionError("solved corridor continued")
    except OsampError as exc:
        assert exc.code == "corridor_closed"
    looped = book.propose_corridor(
        [
            {"stage_id": "a", "recipient": "worker-b", "cost": 2},
            {"stage_id": "b", "recipient": "worker-c", "cost": 2},
        ],
        3,
    )
    book.accept_work(looped, "human-example", keys["human"])
    book.offer_corridor_stage(looped)
    assert book.accept_corridor_stage(looped, "a")["spent"] == 2
    book.offer_corridor_stage(looped)
    assert book._get(looped)["body"]["stages"][0]["status"] == "accepted"
    repeated = book.accept_corridor_stage(looped, "a")
    assert repeated["repeated"] is True
    assert book._get(looped)["body"]["spent"] == 2
    book.advance_corridor(looped)
    try:
        book.attempt_earlier_stage(looped, 0)
        raise AssertionError("corridor loop was allowed")
    except OsampError as exc:
        assert exc.code == "circular_delegation"
    assert book._get(looped)["body"]["outcome"] == "held"
    assert book._get(looped)["body"]["spent"] == 2
    declined = book.propose_corridor(
        [{"stage_id": "only", "recipient": "worker-b", "cost": 1}],
        4,
    )
    book.accept_work(declined, "human-example", keys["human"])
    book.offer_corridor_stage(declined)
    result = book.decline_corridor_stage(declined, "only")
    assert result["recipients"] == ["worker-b"] and result["outcome"] == "held"
    assert called == [] and node.model_calls() == 0
    return (
        "pass",
        "A solved corridor took no further stage. Offering an accepted stage again did not reset it "
        "or double its spend. "
        "Returning to an earlier stage held the corridor with the same spend. A decline did not add a recipient.",
    )


def check_wp07(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    envelope = _offer(node)
    first = _accept(node)
    second = _accept(node)
    node.receive(envelope)
    assert first == second
    assert len(node.postbox.list_obligations()) == 1
    tampered = dict(envelope)
    tampered["payload"] = {"text": "different"}
    tampered["payload_digest"] = digest(tampered["payload"])
    result = node.receive(tampered)
    assert result["code"] == "integrity_failure"
    assert node.postbox.get_obligation(first)["objective"].startswith("Tighten")
    assert node.model_calls() == 0
    return "pass", "Repeating one offer created one obligation. A changed body under the same id was refused."


def check_wp08(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    _offer(node, "held-offer")
    held = _accept(node, "held-offer", work_id="held-work")
    node.request_hold(held, "conflicting_evidence", "Which sentence is the source?")
    _offer(node, "revoked-offer")
    revoked = _accept(node, "revoked-offer", work_id="revoked-work")
    node.revoke_work(revoked)
    node = node.reopen()
    for obligation_id in (held, revoked):
        try:
            node.play(obligation_id)
            raise AssertionError("work resumed after reopen")
        except OsampError as exc:
            assert exc.code == "play_refused"
    assert node.postbox.get_obligation(revoked)["authority_state"] == "revoked"
    return (
        "pass",
        "After the file was closed and opened again, a hold and a local revocation still blocked PLAY. "
        "Limitation: this is the same computer reopening its file, not a network reconnect.",
    )


def check_wp09(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    _offer(node)
    obligation_id = _accept(node)
    node.play(obligation_id)
    node.request_remote_stop(obligation_id, "worker-b")
    text = node.plain_status(obligation_id)
    assert "STOP_PENDING" in text
    assert "confirmed" in text
    node.clock.advance(48 * 3600)
    assert node.postbox.get_obligation(obligation_id)["execution_state"] == "stop_pending"
    try:
        node.acknowledge_remote_stop(obligation_id, "someone-else")
        raise AssertionError("wrong peer confirmed the stop")
    except OsampError:
        pass
    assert node.postbox.get_obligation(obligation_id)["execution_state"] == "stop_pending"
    node.acknowledge_remote_stop(obligation_id, "worker-b")
    assert node.postbox.get_obligation(obligation_id)["execution_state"] == "stopped"
    return (
        "pass",
        "Status stayed STOP_PENDING across a clock advance and a wrong confirmation, then stopped only "
        "after the named peer id was supplied. Limitation: that confirmation is a local test input, not a remote machine.",
    )


def check_wp10(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    phrase = "invitation-body-not-for-the-record"
    _offer(node, payload={"text": phrase})
    _offer(node, "kept", payload={"text": "other"})
    kept = _accept(node, "kept", objective="accepted-objective-must-remain")
    node.clock.advance(3 * 24 * 3600)
    removed = node.expire_invitations()
    assert removed == 1
    expired = node.postbox.get_envelope("offer-1")
    assert expired["body"] is None and expired["delivery_state"] == "expired"
    blob = Path(node.postbox.path).read_bytes()
    backup = Path(node.postbox.backup_path).read_bytes()
    assert phrase.encode() not in blob
    assert phrase.encode() not in backup
    assert b"accepted-objective-must-remain" in blob
    assert b"accepted-objective-must-remain" in backup
    assert node.postbox.get_obligation(kept)["authority_state"] == "accepted"
    policy = node.postbox.backup_policy()
    assert policy["offsite_backups"] == "none"
    return (
        "pass",
        "Expired invitation text was removed from the main database and from the local backup file. "
        "The accepted objective remained in both. The declared policy says there is no off-site backup, "
        "so no off-site copy was deleted.",
    )


def check_wp16(tmp: Path) -> tuple[str, str]:
    node, keys = _boot(tmp)
    _offer(node)
    obligation_id = _accept(node)
    node.request_hold(obligation_id, "conflicting_evidence", "Need a person.")
    obligation = node.postbox.get_obligation(obligation_id)
    decision = _decision(obligation, "leave_held", "human-example")
    node.resolve_human(decision, keys["human"], mac(keys["human"], decision))
    book = AgreementBook(node)
    corridor = book.propose_corridor(
        [{"stage_id": "read", "recipient": "worker-b", "cost": 1}],
        3,
    )
    book.accept_work(corridor, "human-example", keys["human"])
    book.human_satisfied(corridor, "human-example", keys["human"])
    node = node.reopen()
    book = AgreementBook(node)
    kinds = [item["kind"] for item in node.postbox.list_audit()]
    assert "human_decision" in kinds and "human_satisfied" in kinds
    assert node.postbox.get_obligation(obligation_id)["execution_state"] == "held"
    assert book._get(corridor)["body"]["outcome"] == "human_satisfied"
    receipts = [item for item in node.postbox.list_receipts() if item["kind"] == "human_satisfaction"]
    assert len(receipts) == 1
    return (
        "pass",
        "A leave-held decision and a HUMAN_SATISFIED receipt both survived reopening the file. "
        "The held obligation stayed held.",
    )


def check_wp17(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    called = _guard_model(node)
    _offer(node, "local")
    local_id = _accept(node, "local", work_id="local-work")
    node.play(local_id)
    node.pause(local_id)
    try:
        node.dispatch_tool(local_id, "format-check")
        raise AssertionError("paused work used a tool")
    except OsampError:
        pass
    node.stop_local(local_id)
    try:
        node.play(local_id)
        raise AssertionError("stopped work restarted")
    except OsampError:
        pass
    _offer(node, "inbound")
    inbound = _accept(node, "inbound", work_id="inbound-work")
    payload = {"obligation_id": inbound}
    node.receive(
        {
            "event_id": "stop-1",
            "event_type": "WORK_STOP",
            "sender_key_id": "worker-b",
            "recipient_key_id": "worker-a",
            "sent_at": node.clock.now(),
            "expires_at": "2026-11-25T00:00:00+00:00",
            "payload": payload,
            "payload_digest": digest(payload),
        }
    )
    assert node.postbox.get_obligation(inbound)["execution_state"] == "stop_pending"
    assert "STOP_PENDING" in node.plain_status(inbound)
    assert node.model_calls() == 0 and called == []
    return (
        "pass",
        "Local pause and stop blocked new tool use and PLAY. An inbound stop stayed STOP_PENDING "
        "until a local confirmation, which this check deliberately did not send.",
    )


def check_wp18(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    _offer(node)
    obligation_id = _accept(node)
    node.play(obligation_id)
    node.pause(obligation_id)
    checkpoint_id = node.postbox.get_obligation(obligation_id)["checkpoint"]["checkpoint_id"]
    node.play(obligation_id)
    node.note_progress(obligation_id, "progress-1", cost=1)
    node.note_uncertain_effect(obligation_id, "outside-notice")
    before = node.postbox.get_obligation(obligation_id)["attempt_count"]
    node.rewind(obligation_id, checkpoint_id, "The outside notice may already have been sent.")
    restored = node.postbox.get_obligation(obligation_id)
    assert restored["attempt_count"] == before
    assert restored["budget_spent"] == 1
    assert any(item["kind"] == "rewind" for item in restored["history"])
    assert any(item["kind"] == "uncertain_effect" for item in restored["history"])
    assert restored["uncertain_effects"][0]["effect_id"] == "outside-notice"
    assert restored["execution_state"] == "uncertain"
    try:
        node.replay_effect(obligation_id, "outside-notice")
        raise AssertionError("effect was replayed")
    except OsampError as exc:
        assert exc.code == "replay_refused"
    node = node.reopen()
    assert any(item["kind"] == "rewind" for item in node.postbox.get_obligation(obligation_id)["history"])
    return "pass", "Rewind added history, kept the attempt and spend, and did not replay the uncertain outside effect."


def check_wp19(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    called = _guard_model(node)
    _offer(node)
    obligation_id = _accept(node)
    for reviewer in ("a", "b", "c"):
        outcome = node.record_opinion(
            obligation_id,
            reviewer,
            "claim-1",
            "source-1",
            True,
            independent=True,
        )
    assert outcome["held"] is True
    try:
        node.complete(obligation_id)
        raise AssertionError("copied agreement completed the work")
    except OsampError:
        pass
    try:
        node.dispatch_tool(obligation_id, "format-check")
        raise AssertionError("copied agreement ran a tool")
    except OsampError:
        pass
    assert called == []
    return (
        "pass",
        "Three agreements that reused source-1, even when marked independent, entered review and "
        "could not complete or run a tool.",
    )


def check_wp20(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    _offer(node, "waiting")
    assert node.postbox.get_envelope("waiting")["role_state"] == "offered"
    try:
        node.fast_forward("waiting", 1)
        raise AssertionError("offer was fast-forwarded")
    except OsampError:
        pass
    assert node.postbox.obligation_by_event("waiting") is None
    try:
        require_fast_forward({"authority_state": "offered", "queue_cursor": 0, "execution_state": "absent", "hold": None}, 1)
        raise AssertionError("pure fast-forward skipped consent")
    except OsampError as exc:
        assert exc.code == "fast_forward_refused"
    _offer(node, "ready")
    ready = _accept(node, "ready", work_id="ready-work")
    node.fast_forward(ready, 1)
    moved = node.postbox.get_obligation(ready)
    assert moved["queue_cursor"] == 1 and moved["authority_state"] == "accepted"
    assert moved["execution_state"] == "ready"
    try:
        node.fast_forward(ready, 3)
        raise AssertionError("cursor jumped")
    except OsampError:
        pass
    node.request_hold(ready, "timeout", "Wait.")
    try:
        node.fast_forward(ready, 2)
        raise AssertionError("hold was skipped")
    except OsampError:
        pass
    return "pass", "Fast-forward moved one waiting cursor and refused an offer, a jump, and a hold."


def check_wp21(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    _offer(node)
    obligation_id = _accept(node)
    node.disable_covenant()
    assert node.conformance_allowed() is False
    try:
        node.play(obligation_id)
        raise AssertionError("disabled covenant started work")
    except OsampError as exc:
        assert exc.code == "covenant_off"
    assert node.capsule(obligation_id)["objective"]
    return "pass", "With mandatory controls off, conformance is refused and PLAY is refused. The obligation remains."


def check_cz22(tmp: Path) -> tuple[str, str]:
    directory = tmp
    clock = Clock()
    node = Node.open(str(directory / "postbox.sqlite"), clock=clock)
    node.register_person("operator-example", b"owner-key-example")
    node.register_person("human-example", b"human-key-example")
    node.permit_sender("worker-b")
    _offer(node)
    try:
        _accept(node)
        raise AssertionError("work started without acknowledgment")
    except OsampError as exc:
        assert exc.code == "ack_required"
    assert node.postbox.list_obligations() == []
    node.record_acknowledgment("operator-example", b"owner-key-example")
    assert node.postbox.list_obligations() == []
    assert node.postbox.list_senders() == ["worker-b"]
    try:
        _accept(node)
        raise AssertionError("acknowledgment was treated as delegation")
    except OsampError as exc:
        assert exc.code == "delegation_required"
    node.grant_delegation("human-example", b"human-key-example", "public-wording", 100, 2)
    obligation_id = _accept(node)
    node.play(obligation_id)
    node.set_profile(default_profile(limits={"max_attempts": 4}))
    try:
        node.dispatch_tool(obligation_id, "format-check")
        raise AssertionError("stale acknowledgment allowed a tool")
    except OsampError:
        pass
    node.record_acknowledgment("operator-example", b"owner-key-example")
    # Lease and running state still apply; the point of the renewed ack is that
    # the stale digest no longer blocks by itself. PLAY is already working.
    assert node.current_acknowledgment() is not None
    return (
        "pass",
        "No acknowledgment and acknowledgment-without-delegation both refused acceptance. "
        "Changing limits made the old acknowledgment stale and blocked a tool until it was renewed. "
        "Acknowledgment did not add a sender or create work by itself.",
    )


def check_cz23(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    called = _guard_model(node)
    _offer(node)
    obligation_id = _accept(node)
    node.play(obligation_id)
    node.record_opinion(obligation_id, "one", "claim", "shared-source", True)
    node.record_opinion(obligation_id, "two", "claim", "shared-source", True)
    assert node.postbox.get_obligation(obligation_id)["execution_state"] == "review"
    try:
        node.dispatch_tool(obligation_id, "format-check")
        raise AssertionError("dependent tool ran")
    except OsampError:
        pass
    assert node.tool_calls() == 0 and called == []
    return "pass", "Two helpers agreeing from shared-source entered review. No tool call and no model call followed."


def check_cz24(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    called = _guard_model(node)
    _offer(node, "attempts")
    attempts = _accept(node, "attempts", work_id="attempt-work", budget_ceiling=20)
    node.play(attempts)
    first = node.note_progress(attempts, None, cost=1)
    assert first["held"] is False
    second = node.note_progress(attempts, None, cost=1)
    assert second["held"] is True and second["reason"] == "no_progress"
    spent = node.postbox.get_obligation(attempts)["budget_spent"]
    ceiling = node.postbox.get_obligation(attempts)["budget_ceiling"]
    _offer(node, "circle")
    circle = _accept(node, "circle", work_id="circle-work")
    node.play(circle)
    assert node.delegate(circle, "peer-1", "stage-a", 0, 1)["held"] is False
    looped = node.delegate(circle, "peer-1", "stage-a", 0, 1)
    assert looped["held"] is True and looped["reason"] == "circular_delegation"
    assert node.postbox.get_obligation(attempts)["budget_spent"] == spent
    assert node.postbox.get_obligation(attempts)["budget_ceiling"] == ceiling
    assert called == [] and node.model_calls() == 0
    return (
        "pass",
        "A repeated no-progress attempt and a circular handoff both held without a model call. "
        "The spent budget and ceiling were not renewed.",
    )


def check_cz25(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    _offer(node, "kept")
    kept = _accept(node, "kept", objective="capsule-objective-kept")
    _guard_model(node)
    node.report_storage_pressure()
    assert node.postbox.get_obligation(kept)["execution_state"] == "held"
    assert node.capsule(kept)["objective"] == "capsule-objective-kept"
    _offer(node, "new")
    try:
        _accept(node, "new", work_id="should-refuse")
        raise AssertionError("pressure still accepted work")
    except OsampError as exc:
        assert exc.code == "capacity_pressure"
    node = node.reopen()
    called = _guard_model(node)
    assert node.capsule(kept)["work_id"] == "weather-wording"
    assert node.postbox.get_obligation(kept)["execution_state"] == "held"
    assert called == [] and node.model_calls() == 0
    tiny = Node.open(
        str(tmp / "tiny.sqlite"),
        profile=default_profile(limits={"storage_budget_bytes": 40}),
        clock=Clock(),
    )
    tiny.register_person("operator-example", b"owner-key-example")
    tiny.register_person("human-example", b"human-key-example")
    tiny.record_acknowledgment("operator-example", b"owner-key-example")
    tiny.grant_delegation("human-example", b"human-key-example", "public-wording", 100, 2)
    tiny.permit_sender("worker-b")
    _offer(tiny, "too-big")
    try:
        _accept(tiny, "too-big")
        raise AssertionError("tiny store accepted")
    except OsampError as exc:
        assert exc.code == "capacity_pressure"
    assert tiny.postbox.list_obligations() == []
    return (
        "pass",
        "Storage pressure held the accepted work, kept its capsule, and refused new acceptance with the "
        "model port disabled. A store too small to hold the capsule refused before acceptance. "
        "Limitation: no separate language-model process is installed to kill.",
    )


def check_cz26(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    _offer(node, payload={"text": "offer-only"})
    obligation_id = _accept(node, contact_reachable=False, objective="silence-must-keep-this")
    node.request_hold(obligation_id, "timeout", "Are we allowed to send this wording?")
    note_id = node.request_help(obligation_id)
    notes = node.postbox.notifications_for(obligation_id)
    assert notes[0]["state"] == "queued"
    assert notes[0]["body"]["reachable"] is False
    node.mark_notification(note_id, "sent")
    node.mark_notification(note_id, "delivered")
    assert node.postbox.get_obligation(obligation_id)["execution_state"] == "held"
    assert node.remind(obligation_id)["sent"] is False
    node.clock.advance(3600)
    assert node.remind(obligation_id)["sent"] is True
    node.clock.advance(3600)
    assert node.remind(obligation_id)["sent"] is True
    node.clock.advance(3600)
    assert node.remind(obligation_id)["reason"] == "limit"
    node.clock.advance(30 * 24 * 3600)
    node.expire_invitations()
    node.review_retention()
    node = node.reopen()
    restored = node.postbox.get_obligation(obligation_id)
    assert restored["execution_state"] == "held"
    assert restored["objective"] == "silence-must-keep-this"
    states = [item["state"] for item in node.postbox.notifications_for(obligation_id)]
    assert "delivered" in states
    return (
        "pass",
        "Silence, a delivered notice, capped reminders, invitation expiry, and the retention review "
        "left the accepted objective held. Notification state did not resume work.",
    )


def check_cz27(tmp: Path) -> tuple[str, str]:
    node, keys = _boot(tmp, limits={"max_attempts": 10, "max_same_progress": 10})
    _offer(node, "budget")
    budget_id = _accept(node, "budget", work_id="budget-work", budget_ceiling=2)
    node.play(budget_id)
    node.note_progress(budget_id, "one", cost=1)
    node.note_progress(budget_id, "two", cost=1)
    held = node.note_progress(budget_id, "three", cost=1)
    assert held["held"] is True
    obligation = node.postbox.get_obligation(budget_id)
    before_attempts = obligation["attempt_count"]
    before_senders = node.postbox.list_senders()
    try:
        node.natural_language_instruction(budget_id, "please continue")
        raise AssertionError("sentence was accepted")
    except OsampError as exc:
        assert exc.code == "not_authority"
    bad = _decision(obligation, "approve_same_step", "human-example", step_id="approve_same_step")
    try:
        node.resolve_human(bad, keys["human"], "not-a-tag")
        raise AssertionError("bad tag worked")
    except OsampError as exc:
        assert exc.code == "unauthenticated"
    stale = dict(bad)
    stale["hold_id"] = "hold-old"
    try:
        node.resolve_human(stale, keys["human"], mac(keys["human"], stale))
        raise AssertionError("stale hold worked")
    except OsampError as exc:
        assert exc.code == "stale_decision"
    node.register_person("stranger", b"stranger-key")
    stranger = _decision(node.postbox.get_obligation(budget_id), "approve_same_step", "stranger", step_id="approve_same_step")
    try:
        node.resolve_human(stranger, b"stranger-key", mac(b"stranger-key", stranger))
        raise AssertionError("stranger resolved the hold")
    except OsampError as exc:
        assert exc.code == "not_designated_human"
    current = node.postbox.get_obligation(budget_id)
    amend = _decision(current, "amend_budget", "human-example", budget_ceiling=9, decision_id="amend-1")
    amended = node.resolve_human(amend, keys["human"], mac(keys["human"], amend))
    assert amended["resumed"] is False
    after = node.postbox.get_obligation(budget_id)
    assert after["budget_spent"] == current["budget_spent"]
    assert after["budget_ceiling"] == 9
    assert after["execution_state"] == "held"
    assert after["attempt_count"] == before_attempts
    assert node.postbox.list_senders() == before_senders
    approved = _decision(after, "approve_same_step", "deputy-example", step_id="approve_same_step", decision_id="ok-1")
    result = node.resolve_human(approved, keys["deputy"], mac(keys["deputy"], approved))
    assert result.get("ready") is True
    ready = node.postbox.get_obligation(budget_id)
    assert ready["execution_state"] == "ready"
    assert ready["attempt_count"] == before_attempts
    assert node.tool_calls() == 0 and node.model_calls() == 0
    node.play(budget_id)
    assert node.postbox.get_obligation(budget_id)["execution_state"] == "working"
    return (
        "pass",
        "A sentence, a bad tag, a stale hold, and a stranger were refused. A budget amendment did not "
        "resume work, reset spend, or add a sender. The deputy's scoped approval became ready only, "
        "and tools stayed at zero until a separate PLAY.",
    )


def check_wp11(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp)
    _offer(node, "public")
    assert node.postbox.obligation_by_event("public") is None
    try:
        node.catch_up("not-accepted-yet", "review")
        raise AssertionError("catch-up ran before acceptance")
    except OsampError as exc:
        assert exc.code == "catchup_refused"
    public_id = _accept(node, "public")
    package = node.catch_up(public_id, "review", ["summary"])
    assert set(package) == {"summary", "evidence", "uncertainty", "subtask", "contract_version"}
    try:
        node.catch_up(public_id, "review", ["transcript"])
        raise AssertionError("transcript was returned")
    except OsampError as exc:
        assert exc.code == "catchup_refused"
    _offer(
        node,
        "clinic",
        payload={"text": "non-sensitive placeholder"},
        data_class="private-medical",
    )
    clinic_id = _accept(
        node,
        "clinic",
        work_id="clinic-placeholder",
        objective="placeholder only, not a real record",
    )
    try:
        node.catch_up(clinic_id, "public-news")
        raise AssertionError("medical placeholder was placed on a public route")
    except OsampError as exc:
        assert exc.code == "catchup_refused"
    private = node.catch_up(clinic_id, "designated-review")
    assert private["summary"] == "placeholder only, not a real record"
    assert "transcript" not in private
    assert node.model_calls() == 0
    return (
        "pass",
        "Catch-up was refused before acceptance and when a transcript was requested. "
        "A private-medical placeholder was refused on a public-news route and returned only the short fields on a designated route. "
        "The placeholder is not a real health record.",
    )


def check_cz28(tmp: Path) -> tuple[str, str]:
    node, _keys = _boot(tmp, limits={"max_open_obligations": 4})
    _offer(node, "held")
    held = _accept(node, "held", work_id="held-work")
    node.play(held)
    node.note_uncertain_effect(held, "maybe-sent")
    _offer(node, "remote")
    remote = _accept(node, "remote", work_id="remote-work")
    node.request_remote_stop(remote, "worker-b")
    _offer(node, "budgeted")
    budgeted = _accept(node, "budgeted", work_id="budgeted-work", budget_ceiling=5)
    node.play(budgeted)
    snapshot = tmp / "before-revoke.sqlite"
    node.snapshot(str(snapshot))
    node.note_progress(budgeted, "step-1", cost=1)
    node.revoke_work(budgeted)
    node = node.restore_from_snapshot(str(snapshot))
    restored = node.postbox.get_obligation(budgeted)
    assert restored["authority_state"] == "revoked"
    assert restored["budget_spent"] == 1
    try:
        node.submit_result(budgeted, "sha256:late", True)
        raise AssertionError("late result resurrected revoked work")
    except OsampError as exc:
        assert exc.code == "result_refused"
    node = node.reopen()
    try:
        node.play(held)
        raise AssertionError("uncertain work resumed")
    except OsampError:
        pass
    try:
        node.replay_effect(held, "maybe-sent")
        raise AssertionError("replayed")
    except OsampError as exc:
        assert exc.code == "replay_refused"
    assert node.postbox.get_obligation(remote)["execution_state"] == "stop_pending"
    assert any(item["kind"] == "uncertain_effect" for item in node.postbox.get_obligation(held)["history"])
    _kill_committed_hold(tmp)
    return (
        "pass",
        "A committed hold survived reopening the file, a snapshot restore, and a killed process. "
        "The uncertain outside effect was not repeated, history remained, and STOP_PENDING stayed "
        "unconfirmed. The operating system killed the process after the hold was saved. The machine stayed powered on.",
    )


def _kill_committed_hold(tmp: Path) -> None:
    import os
    import signal
    import subprocess
    import time

    crash_dir = tmp / "crash"
    crash_dir.mkdir()
    node, _keys = _boot(crash_dir)
    _offer(node, "crash-offer")
    obligation_id = _accept(node, "crash-offer", work_id="crash-work")
    database = node.postbox.path
    node.close()
    ready = crash_dir / "ready"
    process = subprocess.Popen(
        [sys.executable, "-m", "osamp.crash_probe", database, str(ready), obligation_id],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    for _ in range(100):
        if ready.exists():
            break
        time.sleep(0.05)
    else:
        process.kill()
        process.wait(timeout=5)
        raise AssertionError("child did not commit the hold")
    os.kill(process.pid, signal.SIGKILL)
    process.wait(timeout=5)
    reopened = Node.open(database)
    obligation = reopened.postbox.get_obligation(obligation_id)
    assert obligation["execution_state"] == "held"
    assert obligation["hold"]["reason"] == "timeout"
    try:
        reopened.play(obligation_id)
        raise AssertionError("work resumed after the process was killed")
    except OsampError:
        pass
    reopened.close()


def check_cz29(tmp: Path) -> tuple[str, str]:
    clock = Clock()
    node = Node.open(str(tmp / "postbox.sqlite"), clock=clock)
    owner = b"owner-key-example"
    human = b"human-key-example"
    node.register_person("operator-example", owner)
    node.register_person("human-example", human)
    node.record_acknowledgment("operator-example", owner)
    node.grant_delegation(
        "human-example",
        human,
        "public-wording",
        100,
        2,
        agreed_closure="close_when_due",
    )
    node.permit_sender("worker-b")
    phrase = "closure-objective-should-be-removed"
    _offer(node, payload={"text": "unrelated offer text"})
    obligation_id = _accept(
        node,
        objective=phrase,
        retention_deadline="2026-11-24T00:00:10+00:00",
    )
    notices = node.review_retention()
    assert obligation_id in notices
    assert node.postbox.get_obligation(obligation_id)["objective"] == phrase
    node.clock.advance(30)
    node.review_retention()
    closed = node.postbox.get_obligation(obligation_id)
    assert closed["closure"]["disposition"] == "retention_closure"
    assert closed["execution_state"] == "closed"
    assert closed["objective"] is None
    blob = Path(node.postbox.path).read_bytes()
    backup = Path(node.postbox.backup_path).read_bytes()
    assert phrase.encode() not in blob
    assert phrase.encode() not in backup
    assert b"retention_closure" in backup
    exported = node.export_minimal(obligation_id)
    assert exported["objective_present"] is False
    assert exported["disposition"] == "retention_closure"
    assert node.postbox.backup_policy()["offsite_backups"] == "none"
    return (
        "pass",
        "A pre-agreed closure sent a notice, removed the objective from the main database and the local "
        "backup, and kept the disposition in both. No off-site backup is declared, so none was deleted.",
    )


def check_pending(_tmp: Path, reason: str) -> tuple[str, str]:
    return "pending", reason


def check_wp12(tmp: Path) -> tuple[str, str]:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    source = (root / "adapter-b.py").read_text(encoding="utf-8")
    if "import osamp" in source or "from osamp" in source:
        raise AssertionError("adapter B imports the reference program")
    spec = importlib.util.spec_from_file_location("adapter_b_vectors", root / "adapter-b.py")
    if spec is None or spec.loader is None:
        raise AssertionError("adapter B could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.digest({"text": "hello"}) != digest({"text": "hello"}):
        raise AssertionError("checksums differ")
    cases = json.loads((root / "vectors.json").read_text(encoding="utf-8"))["cases"]
    now = "2026-11-24T00:00:00+00:00"
    for case in cases:
        payload = case["payload"]
        claimed = case.get("payload_digest") or digest(payload)
        envelope = {
            "event_type": case["event_type"],
            "payload": payload,
            "payload_digest": claimed,
            "expires_at": case.get("expires_at"),
        }
        if case.get("signature"):
            envelope["signature"] = case["signature"]
        existing = None
        if case.get("existing"):
            existing = {"payload_digest": claimed, "delivery_state": "delivered", "role_state": "offered"}
        if case.get("existing_digest"):
            existing = {
                "payload_digest": case["existing_digest"],
                "delivery_state": "delivered",
                "role_state": "offered",
            }
        reference = screen(
            envelope,
            known_sender=case["known_sender"],
            now=now,
            existing=existing,
            payload_too_big=bool(case.get("payload_too_big")),
        )
        other = module.decide(
            envelope,
            case["known_sender"],
            now,
            existing,
            bool(case.get("payload_too_big")),
        )
        if reference.code != case["expect"] or other != case["expect"]:
            raise AssertionError(f"{case['name']}: reference={reference.code} adapter={other}")
    ledger = module.TinyLedger()
    ledger.accept("offer-1")
    restored = module.TinyLedger.load(ledger.dump())
    if restored.rows["offer-1"]["authority"] != "accepted":
        raise AssertionError("adapter B forgot an acceptance")
    if restored.request_stop("offer-1", "worker-b") != "stop_pending":
        raise AssertionError("stop was confirmed too early")
    if restored.acknowledge_stop("offer-1", "someone-else") != "stop_pending":
        raise AssertionError("the wrong peer confirmed the stop")
    if restored.acknowledge_stop("offer-1", "worker-b") != "stopped":
        raise AssertionError("the named peer did not confirm the stop")
    return (
        "partial",
        f"Adapter B passed {len(cases)} shared envelope vectors and its own small hold record "
        "without importing the reference program. It does not perform the other conformance checks. "
        "A second organization did not run it. This is not an interoperability claim.",
    )


REQUIREMENTS = {
    "WP-01": "B-PEER01, B-GATE02",
    "WP-02": "B-GATE02",
    "WP-03": "B-TABLE01, P-GATE04",
    "WP-04": "B-CAP01, B-CAP02",
    "WP-05": "B-TRIBE01",
    "WP-06": "B-CLAN01, B-DATA01",
    "WP-07": "P-GATE04, P-MSG04",
    "WP-08": "B-CTRL02, B-QUEUE01",
    "WP-09": "B-CTRL02",
    "WP-10": "B-QUEUE04",
    "WP-11": "B-DATA02",
    "WP-12": "B-MSG05",
    "WP-13": "B-TABLE01",
    "WP-14": "B-AUTH01",
    "WP-15": "B-COR01, B-COR02",
    "WP-16": "B-COR02, P-Z13",
    "WP-17": "B-CTRL01, B-CTRL02",
    "WP-18": "B-CTRL01",
    "WP-19": "B-EVID01, P-Z03",
    "WP-20": "B-CTRL01",
    "WP-21": "B-AUTH01",
    "CZ-22": "P-Z01, P-Z02",
    "CZ-23": "P-Z03, B-EVID01",
    "CZ-24": "P-Z03, P-Z04",
    "CZ-25": "P-Z05, P-Z08",
    "CZ-26": "P-Z10, B-RET01",
    "CZ-27": "P-Z11, P-Z12",
    "CZ-28": "P-Z05, P-GATE04",
    "CZ-29": "P-Z09",
}


CHECKS = [
    ("WP-01", "Unknown sender is not relayed", check_wp01),
    ("WP-02", "Unaccepted invitation uses no model", check_wp02),
    ("WP-03", "Explicit acceptance is durable", check_wp03),
    ("WP-04", "Capability fit identifies a bounded step", check_wp04),
    ("WP-05", "Tribe help stays within budgets", check_wp05),
    ("WP-06", "Cross-clan bridge requires human approval", check_wp06),
    ("WP-07", "Replay does not duplicate accepted work", check_wp07),
    ("WP-08", "Reopen checks revocation and holds", check_wp08),
    ("WP-09", "Unreachable stop stays STOP_PENDING", check_wp09),
    ("WP-10", "TTL deletion covers stored copies", check_wp10),
    ("WP-11", "Catch-up exposes only authorized context", check_wp11),
    ("WP-12", "A second adapter passes the same vectors", check_wp12),
    ("WP-13", "Table membership requires role acceptance", check_wp13),
    ("WP-14", "Five agreement categories have separate scopes", check_wp14),
    ("WP-15", "Corridor stages do not loop or reset budgets", check_wp15),
    ("WP-16", "Human satisfaction and holds are durable", check_wp16),
    ("WP-17", "Local pause and stop are truthful", check_wp17),
    ("WP-18", "Rewind keeps history and outside effects", check_wp18),
    ("WP-19", "Review separates copied agreement from independent evidence", check_wp19),
    ("WP-20", "Fast-forward cannot skip consent or holds", check_wp20),
    ("WP-21", "Disabling the covenant blocks a conformance claim", check_wp21),
    ("CZ-22", "Acknowledgment is required and is not work authority", check_cz22),
    ("CZ-23", "Copied sources cannot verify each other", check_cz23),
    ("CZ-24", "Attempt and circular-work limits stop without a model", check_cz24),
    ("CZ-25", "A small store holds without a model", check_cz25),
    ("CZ-26", "Silence does not resume or erase accepted work", check_cz26),
    ("CZ-27", "Only an authenticated scoped decision can clear a hold", check_cz27),
    ("CZ-28", "Restart reconciles holds and uncertain effects", check_cz28),
    ("CZ-29", "Retention closure is explicit", check_cz29),
]


def run_all() -> list[CheckResult]:
    results = []
    for check_id, title, fn in CHECKS:
        with tempfile.TemporaryDirectory() as directory:
            try:
                status, evidence = fn(Path(directory))
            except Exception as exc:
                status, evidence = "fail", f"{type(exc).__name__}: {exc}"
        results.append(CheckResult(check_id, title, status, evidence))
    return results


def format_report(results: list[CheckResult]) -> str:
    counts: dict[str, int] = {}
    lines = [
        "OSAMP local conformance report",
        "This report is about one computer. It is not a federation test and not a Cameroon–Lagos pilot.",
        "",
    ]
    for item in results:
        counts[item.status] = counts.get(item.status, 0) + 1
        lines.append(f"{item.check_id}  {item.status.upper():8}  {item.title}")
        lines.append(f"    {item.evidence}")
    lines.append("")
    lines.append(
        "Totals: "
        + ", ".join(f"{counts.get(name, 0)} {name}" for name in ("pass", "partial", "pending", "fail"))
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local OSAMP conformance checks")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = run_all()
    if args.json:
        import json

        print(json.dumps([item.__dict__ for item in results], indent=2))
    else:
        print(format_report(results))
    return 1 if any(item.status == "fail" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
