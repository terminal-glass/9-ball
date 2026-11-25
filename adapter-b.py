#!/usr/bin/env python3
"""A second, small gate. It does not import the reference program.

It answers the shared envelope vectors and keeps a tiny hold record.
It is not a full second product and it does not talk to another computer.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime


KNOWN_EVENTS = {
    "WORK_PAUSE",
    "WORK_STOP",
    "WORK_REVIEW",
    "REWIND_REQUEST",
    "REWIND_APPROVAL",
    "RESUME_APPROVAL",
    "PEER_INVITE",
    "PEER_ACCEPT",
    "WORK_OFFER",
    "WORK_ACCEPT",
    "TABLE_ROLE_OFFER",
    "TABLE_ROLE_ACCEPT",
    "TABLE_ROLE_HOLD",
    "TABLE_ROLE_HANDOFF",
    "TABLE_ROLE_COMPLETE",
    "CORRIDOR_STAGE_OFFER",
    "CORRIDOR_STAGE_ACCEPT",
    "CORRIDOR_STAGE_COMPLETE",
    "CORRIDOR_STAGE_HOLD",
    "HELP_REQUEST",
    "HUMAN_REVIEW_REQUEST",
    "HUMAN_SATISFIED_ACK",
    "HOLD_NOTICE",
    "HOLD_ACK",
    "RESUME_REQUEST",
    "RESULT",
    "COMPLETE_ACK",
    "REVOKE",
    "CATCH_UP",
}

OFFER_EVENTS = {
    "WORK_OFFER",
    "TABLE_ROLE_OFFER",
    "CORRIDOR_STAGE_OFFER",
    "PEER_INVITE",
    "HELP_REQUEST",
}


def digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _expired(expires_at: str | None, now: str) -> bool:
    if not expires_at:
        return False
    left = datetime.fromisoformat(expires_at)
    right = datetime.fromisoformat(now)
    return left <= right


def decide(envelope: dict, known_sender: bool, now: str, existing: dict | None, payload_too_big: bool) -> str:
    if "signature" in envelope:
        return "signature_not_adopted"
    if payload_too_big:
        return "payload_too_big"
    if envelope.get("event_type") not in KNOWN_EVENTS:
        return "unknown_event"
    if not known_sender:
        return "unknown_sender"
    payload = envelope.get("payload")
    if not isinstance(payload, dict) or digest(payload) != envelope.get("payload_digest", ""):
        return "digest_mismatch"
    if existing is not None:
        if existing.get("payload_digest") != envelope.get("payload_digest"):
            return "integrity_failure"
        return "duplicate"
    if _expired(envelope.get("expires_at"), now):
        return "expired"
    return "admitted"


class TinyLedger:
    """A separate hold record for the shared state vectors."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def accept(self, event_id: str) -> None:
        self.rows[event_id] = {"authority": "accepted", "execution": "ready"}

    def request_stop(self, event_id: str, peer: str) -> str:
        self.rows[event_id]["execution"] = "stop_pending"
        self.rows[event_id]["peer"] = peer
        return "stop_pending"

    def acknowledge_stop(self, event_id: str, peer: str) -> str:
        if self.rows[event_id].get("peer") != peer:
            return "stop_pending"
        self.rows[event_id]["execution"] = "stopped"
        return "stopped"

    def dump(self) -> str:
        return json.dumps(self.rows, sort_keys=True)

    @classmethod
    def load(cls, text: str) -> "TinyLedger":
        item = cls()
        item.rows = json.loads(text)
        return item
