"""Deterministic gate. It runs before any model or tool call.

A signature field is refused. This slice has no adopted signature suite, so a
signature cannot be treated as proof.
"""

from __future__ import annotations

from dataclasses import dataclass

from osamp.canonical import digest
from osamp.clock import parse_time
from osamp.records import KNOWN_EVENT_TYPES, OFFER_EVENTS


@dataclass(frozen=True)
class GateDecision:
    code: str
    plain: str
    store_body: bool
    delivery_state: str
    role_state: str
    quarantine_reason: str | None = None
    duplicate: bool = False


def payload_digest_ok(payload: dict, claimed: str) -> bool:
    return digest(payload) == claimed


def screen(
    envelope: dict,
    *,
    known_sender: bool,
    now: str,
    existing: dict | None,
    payload_too_big: bool,
) -> GateDecision:
    if "signature" in envelope:
        return GateDecision(
            code="signature_not_adopted",
            plain=(
                "A signature field is not proof. This copy has no adopted "
                "signature suite, so the message was quarantined."
            ),
            store_body=False,
            delivery_state="failed",
            role_state="proposed",
            quarantine_reason="signature_not_adopted",
        )
    if payload_too_big:
        return GateDecision(
            code="payload_too_big",
            plain="The message is larger than this node's limit and was not stored.",
            store_body=False,
            delivery_state="failed",
            role_state="proposed",
            quarantine_reason="payload_too_big",
        )
    if envelope.get("event_type") not in KNOWN_EVENT_TYPES:
        return GateDecision(
            code="unknown_event",
            plain="The message type is not recognized, so it was not acted on.",
            store_body=False,
            delivery_state="failed",
            role_state="proposed",
            quarantine_reason="unknown_event",
        )
    if not known_sender:
        return GateDecision(
            code="unknown_sender",
            plain="The sender is not on this node's permitted list, so nothing was forwarded.",
            store_body=False,
            delivery_state="failed",
            role_state="proposed",
            quarantine_reason="unknown_sender",
        )
    payload = envelope.get("payload")
    if not isinstance(payload, dict) or not payload_digest_ok(payload, envelope.get("payload_digest", "")):
        return GateDecision(
            code="digest_mismatch",
            plain="The message body does not match its checksum.",
            store_body=False,
            delivery_state="failed",
            role_state="proposed",
            quarantine_reason="digest_mismatch",
        )
    if existing is not None:
        if existing["payload_digest"] != envelope["payload_digest"]:
            return GateDecision(
                code="integrity_failure",
                plain="The same message id arrived again with different contents. The original was kept.",
                store_body=False,
                delivery_state=existing["delivery_state"],
                role_state=existing["role_state"],
                quarantine_reason="reused_id",
                duplicate=True,
            )
        return GateDecision(
            code="duplicate",
            plain="This message was already recorded. It was not accepted twice.",
            store_body=False,
            delivery_state=existing["delivery_state"],
            role_state=existing["role_state"],
            duplicate=True,
        )
    expires_at = envelope.get("expires_at")
    if expires_at and parse_time(expires_at) <= parse_time(now):
        return GateDecision(
            code="expired",
            plain="The invitation had already expired, so its body was not kept.",
            store_body=False,
            delivery_state="expired",
            role_state="expired",
            quarantine_reason="expired",
        )
    role_state = "offered" if envelope["event_type"] in OFFER_EVENTS else "proposed"
    return GateDecision(
        code="admitted",
        plain="The message is in the local postbox. Delivery is not acceptance.",
        store_body=True,
        delivery_state="delivered",
        role_state=role_state,
    )
