"""Local supervisor. It ties the gate, the covenant, Contract Zero, and the Postbox.

This process can hold and recover accepted work with the language model off.
It does not send network mail and it does not talk to another country.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from osamp.auth import mac_ok
from osamp.canonical import canonical_bytes, digest, key_hash
from osamp.clock import Clock, parse_time
from osamp.contract_zero import (
    assess_task,
    build_capsule,
    check_decision_shape,
    copied_source,
    independent_opinion,
    minimal_closure_capsule,
    note_attempt,
    note_delegation,
)
from osamp.covenant import play_blockers, require_fast_forward, rewind_updates
from osamp.errors import OsampError
from osamp.gate import screen
from osamp.plain import OPERATOR_PROMISE, PERMITTED_HUMAN_STEPS, hold_sentence
from osamp.postbox import Postbox
from osamp.profile import Profile, default_profile
from osamp.records import HUMAN_HOLD_REASONS

ACK_SCOPE = "osamp-work"


class Node:
    def __init__(self, box: Postbox, profile: Profile, clock: Clock):
        self.postbox = box
        self.profile = profile
        self.clock = clock
        self.hook = None

    @classmethod
    def open(cls, path: str, profile: Profile | None = None, clock: Clock | None = None) -> "Node":
        box = Postbox(path)
        box.create()
        clock = clock or Clock()
        if profile is None:
            raw = box.get_meta("profile_json")
            profile = _profile_from_json(raw) if raw else default_profile()
        box.set_meta("profile_json", json.dumps(profile.material(), sort_keys=True))
        return cls(box, profile, clock)

    def close(self) -> None:
        self.postbox.close()

    def reopen(self) -> "Node":
        path = self.postbox.path
        clock = self.clock
        self.close()
        return Node.open(path, clock=clock)

    def _tx(self, fn):
        with self.postbox.transaction():
            return fn()

    def _now(self) -> str:
        return self.clock.now()

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def _hook(self, name: str, **kwargs) -> None:
        if self.hook is None:
            return
        fn = getattr(self.hook, name, None)
        if fn is not None:
            fn(self, **kwargs)

    def covenant_enabled(self) -> bool:
        return self.postbox.get_meta("covenant_enabled") == "1"

    def conformance_allowed(self) -> bool:
        return self.covenant_enabled()

    def disable_covenant(self) -> None:
        def run():
            self.postbox.set_meta("covenant_enabled", "0")
            self.postbox.audit(
                "covenant_disabled",
                None,
                {"conformance": False},
                self._now(),
            )

        self._tx(run)

    def model_calls(self) -> int:
        return int(self.postbox.get_meta("model_calls") or "0")

    def tool_calls(self) -> int:
        return int(self.postbox.get_meta("tool_calls") or "0")

    def relay_count(self) -> int:
        return int(self.postbox.get_meta("relay_count") or "0")

    def _bump(self, key: str) -> None:
        self.postbox.set_meta(key, str(int(self.postbox.get_meta(key) or "0") + 1))

    def register_person(self, person_id: str, key: bytes) -> None:
        def run():
            self.postbox.insert_person(person_id, key_hash(key), self._now())
            self.postbox.audit("person_registered", person_id, {"person_id": person_id}, self._now())

        self._tx(run)

    def _require_person_key(self, person_id: str, key: bytes) -> None:
        stored = self.postbox.person_hash(person_id)
        if stored is None or stored != key_hash(key):
            raise OsampError(
                "unauthenticated",
                "That approval does not match a registered person.",
            )

    def acknowledgment_text(self) -> str:
        return OPERATOR_PROMISE

    def record_acknowledgment(self, operator_id: str, key: bytes) -> str:
        payload = {
            "approved_at": self._now(),
            "digest": self.profile.governance_digest,
            "operator_id": operator_id,
            "scope": ACK_SCOPE,
            "version": self.profile.governance_version,
        }

        def run():
            self._require_person_key(operator_id, key)
            tag = _presented_mac(key, payload)
            self.postbox.supersede_acks(ACK_SCOPE)
            ack_id = self._new_id("ack")
            self.postbox.insert_ack(
                {
                    "ack_id": ack_id,
                    "operator_id": operator_id,
                    "scope": ACK_SCOPE,
                    "version": payload["version"],
                    "digest": payload["digest"],
                    "approved_at": payload["approved_at"],
                    "evidence": tag,
                }
            )
            self.postbox.audit(
                "acknowledgment",
                ack_id,
                {"operator_id": operator_id, "digest": payload["digest"]},
                self._now(),
            )
            return ack_id

        return self._tx(run)

    def current_acknowledgment(self) -> dict | None:
        return self.postbox.current_ack(ACK_SCOPE, self.profile.governance_digest)

    def grant_delegation(
        self,
        person_id: str,
        key: bytes,
        task_class: str,
        max_budget: int,
        remaining_accepts: int,
        agreed_closure: str = "hold",
    ) -> str:
        if agreed_closure not in {"hold", "close_when_due"}:
            raise OsampError("delegation_refused", "The closure rule must be hold or close_when_due.")
        payload = {
            "agreed_closure": agreed_closure,
            "governance_digest": self.profile.governance_digest,
            "max_budget": max_budget,
            "person_id": person_id,
            "remaining_accepts": remaining_accepts,
            "task_class": task_class,
        }

        def run():
            self._require_person_key(person_id, key)
            if not mac_ok(key, payload, _presented_mac(key, payload)):
                raise OsampError("unauthenticated", "The delegation tag does not match.")
            delegation_id = self._new_id("del")
            self.postbox.insert_delegation(
                {
                    "delegation_id": delegation_id,
                    "person_id": person_id,
                    "task_class": task_class,
                    "max_budget": max_budget,
                    "remaining_accepts": remaining_accepts,
                    "governance_digest": self.profile.governance_digest,
                    "agreed_closure": agreed_closure,
                    "mac": _presented_mac(key, payload),
                    "created_at": self._now(),
                }
            )
            self.postbox.audit(
                "delegation",
                delegation_id,
                {"task_class": task_class, "remaining_accepts": remaining_accepts},
                self._now(),
            )
            return delegation_id

        return self._tx(run)

    def permit_sender(self, sender_key_id: str) -> None:
        """Operator allowlist only. This is not a Peer Contract and not a signature."""

        def run():
            self.postbox.permit_sender(sender_key_id, self._now())
            self.postbox.audit("sender_permitted", sender_key_id, {"sender_key_id": sender_key_id}, self._now())

        self._tx(run)

    def set_profile(self, profile: Profile) -> None:
        def run():
            self.profile = profile
            self.postbox.set_meta("profile_json", json.dumps(profile.material(), sort_keys=True))
            self.postbox.audit(
                "profile_changed",
                None,
                {"digest": profile.governance_digest},
                self._now(),
            )

        self._tx(run)

    def receive(self, envelope: dict) -> dict:
        def run():
            self._hook("before_receive", envelope=envelope)
            existing = self.postbox.get_envelope(envelope["event_id"]) if envelope.get("event_id") else None
            payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
            too_big = len(canonical_bytes(payload)) > self.profile.limits["max_payload_bytes"]
            decision = screen(
                envelope,
                known_sender=self.postbox.sender_known(envelope.get("sender_key_id", "")),
                now=self._now(),
                existing=existing,
                payload_too_big=too_big,
            )
            if decision.duplicate and decision.code == "duplicate":
                return {"code": decision.code, "plain": decision.plain, "event_id": envelope["event_id"]}
            if decision.code == "integrity_failure":
                self.postbox.audit(
                    "integrity_failure",
                    envelope["event_id"],
                    {"event_id": envelope["event_id"]},
                    self._now(),
                )
                return {"code": decision.code, "plain": decision.plain, "event_id": envelope["event_id"]}
            if existing is None:
                self.postbox.insert_envelope(
                    {
                        "event_id": envelope["event_id"],
                        "event_type": envelope.get("event_type", ""),
                        "sender_key_id": envelope.get("sender_key_id", ""),
                        "recipient_key_id": envelope.get("recipient_key_id", ""),
                        "sent_at": envelope.get("sent_at", self._now()),
                        "expires_at": envelope.get("expires_at"),
                        "payload_digest": envelope.get("payload_digest", ""),
                        "body": payload if decision.store_body else None,
                        "delivery_state": decision.delivery_state,
                        "role_state": decision.role_state,
                        "quarantine_reason": decision.quarantine_reason,
                        "data_class": envelope.get("data_class", "public-example"),
                        "created_at": self._now(),
                        "updated_at": self._now(),
                    }
                )
                if decision.quarantine_reason:
                    self._trim_quarantine()
            self.postbox.audit(
                "receive",
                envelope.get("event_id"),
                {"code": decision.code, "event_id": envelope.get("event_id")},
                self._now(),
            )
            if (
                decision.code == "admitted"
                and envelope.get("event_type") == "WORK_STOP"
                and payload.get("obligation_id")
            ):
                self._enter_stop_pending(payload["obligation_id"], "inbound")
            return {"code": decision.code, "plain": decision.plain, "event_id": envelope["event_id"]}

        return self._tx(run)

    def _trim_quarantine(self) -> None:
        keep = self.profile.limits["max_quarantine"]
        if self.postbox.quarantine_count() > keep:
            self.postbox.trim_quarantine(keep)

    def relay(self, event_id: str, next_hop: str) -> None:
        """Foundation slice does not forward. Unknown senders cannot create a route."""

        def run():
            envelope = self.postbox.get_envelope(event_id)
            if envelope is None or not self.postbox.sender_known(envelope["sender_key_id"]):
                raise OsampError("no_relay", "Unknown or missing mail is not forwarded.")
            self._hook("before_relay", envelope=envelope, next_hop=next_hop)
            raise OsampError(
                "no_relay",
                "This copy keeps mail locally. It does not forward to another computer.",
            )

        self._tx(run)

    def accept(
        self,
        event_id: str,
        *,
        work_id: str,
        objective: str,
        task_class: str,
        scope: str,
        subtask_id: str | None,
        budget_ceiling: int,
        human_id: str,
        contract_version: str,
        contract_digest: str,
        deadline: str,
        retention_deadline: str,
        deputy_id: str | None = None,
        table_id: str | None = None,
        role_id: str | None = None,
        tool_allowlist: list[str] | None = None,
        contact_reachable: bool = True,
    ) -> str:
        def run():
            self._require_work_enabled()
            existing = self.postbox.obligation_by_event(event_id)
            if existing is not None:
                return existing["obligation_id"]
            envelope = self.postbox.get_envelope(event_id)
            if envelope is None or envelope["role_state"] != "offered" or envelope["body"] is None:
                raise OsampError("not_offered", "There is no open offer to accept.")
            if not self.postbox.sender_known(envelope["sender_key_id"]):
                raise OsampError("unknown_sender", "The sender is not permitted.")
            fit = assess_task(self.profile, task_class, scope, subtask_id)
            if fit["fit"] != "bounded_subtask":
                raise OsampError("task_unfit", fit["plain"])
            if self.postbox.get_meta("storage_pressure") == "1":
                raise OsampError(
                    "capacity_pressure",
                    "New work is refused because saved space is reserved for commitments already accepted.",
                )
            if self.postbox.count_open_obligations() >= self.profile.limits["max_open_obligations"]:
                raise OsampError(
                    "capacity_pressure",
                    "This small node cannot accept another commitment until one is finished or closed.",
                )
            delegation = self.postbox.find_delegation(task_class, self.profile.governance_digest)
            if delegation is None:
                raise OsampError(
                    "delegation_required",
                    "A registered person has not permitted acceptance of this kind of work.",
                )
            if budget_ceiling > delegation["max_budget"]:
                raise OsampError("budget_refused", "The budget is above the human delegation.")
            self._hook(
                "before_accept",
                envelope=envelope,
                task_class=task_class,
                table_id=table_id,
                role_id=role_id,
            )
            obligation_id = self._new_id("obl")
            limits = {
                "tool_allowlist": tool_allowlist or [],
                "agreed_closure": delegation["agreed_closure"],
                "subtask_id": subtask_id,
                "scope": scope,
            }
            capsule = build_capsule(
                {
                    "work_id": work_id,
                    "table_id": table_id,
                    "role_id": role_id,
                    "event_id": event_id,
                    "contract_version": contract_version,
                    "contract_digest": contract_digest,
                    "objective": objective,
                    "limits": limits,
                    "deadline": deadline,
                    "human_id": human_id,
                    "deputy_id": deputy_id,
                    "completed_actions": [],
                    "evidence_digests": [envelope["payload_digest"]],
                    "external_effects": [],
                    "blocker": None,
                    "uncertainty": None,
                    "checkpoint_id": None,
                    "budget_ceiling": budget_ceiling,
                    "budget_spent": 0,
                    "budget_reserved": 0,
                    "lease_expires_at": None,
                    "stop_state": None,
                    "pending_deliveries": [],
                    "human_decision_requested": None,
                    "permitted_next_steps": list(PERMITTED_HUMAN_STEPS),
                    "retention_deadline": retention_deadline,
                    "archive_rule": delegation["agreed_closure"],
                    "access": "designated-human",
                }
            )
            nbytes = len(canonical_bytes(capsule))
            if self.postbox.storage_used() + nbytes > self.profile.limits["storage_budget_bytes"]:
                raise OsampError(
                    "capacity_pressure",
                    "There is not enough reserved space for the recovery record, so the work was not accepted.",
                )
            now = self._now()
            try:
                self._insert_accepted(
                    obligation_id=obligation_id,
                    event_id=event_id,
                    work_id=work_id,
                    table_id=table_id,
                    role_id=role_id,
                    contract_version=contract_version,
                    contract_digest=contract_digest,
                    task_class=task_class,
                    objective=objective,
                    limits=limits,
                    deadline=deadline,
                    retention_deadline=retention_deadline,
                    human_id=human_id,
                    deputy_id=deputy_id,
                    budget_ceiling=budget_ceiling,
                    capsule=capsule,
                    contact_reachable=contact_reachable,
                    now=now,
                )
            except sqlite3.IntegrityError:
                found = self.postbox.obligation_by_event(event_id)
                if found is None:
                    raise
                return found["obligation_id"]
            self.postbox.decrement_delegation(delegation["delegation_id"])
            self.postbox.add_storage(nbytes)
            self.postbox.insert_receipt(
                {
                    "receipt_id": self._new_id("rcpt"),
                    "kind": "acceptance",
                    "event_id": event_id,
                    "obligation_id": obligation_id,
                    "body": {"obligation_id": obligation_id, "event_id": event_id},
                    "created_at": now,
                }
            )
            self.postbox.audit(
                "accepted",
                obligation_id,
                {"obligation_id": obligation_id, "event_id": event_id, "digest": contract_digest},
                now,
            )
            return obligation_id

        return self._tx(run)

    def _insert_accepted(self, **row) -> None:
        now = row["now"]
        self.postbox.insert_obligation(
            {
                "obligation_id": row["obligation_id"],
                "event_id": row["event_id"],
                "work_id": row["work_id"],
                "table_id": row["table_id"],
                "role_id": row["role_id"],
                "contract_version": row["contract_version"],
                "contract_digest": row["contract_digest"],
                "task_class": row["task_class"],
                "objective": row["objective"],
                "limits": row["limits"],
                "deadline": row["deadline"],
                "retention_deadline": row["retention_deadline"],
                "human_id": row["human_id"],
                "deputy_id": row["deputy_id"],
                "authority_state": "accepted",
                "execution_state": "ready",
                "budget_ceiling": row["budget_ceiling"],
                "budget_spent": 0,
                "budget_reserved": 0,
                "attempt_count": 0,
                "same_progress_count": 0,
                "delegation": [],
                "opinions": [],
                "capsule": row["capsule"],
                "hold_history": [],
                "uncertain_effects": [],
                "queue_cursor": 0,
                "history": [{"kind": "accepted", "at": now}],
                "contact_reachable": row["contact_reachable"],
                "created_at": now,
                "updated_at": now,
            }
        )

    def decline(self, event_id: str) -> None:
        def run():
            envelope = self.postbox.get_envelope(event_id)
            if envelope is None:
                raise OsampError("not_offered", "There is no offer to decline.")
            if self.postbox.obligation_by_event(event_id) is not None:
                raise OsampError("already_accepted", "Accepted work cannot be declined into nothing.")
            self.postbox.update_envelope(
                event_id,
                role_state="expired",
                delivery_state=envelope["delivery_state"],
                body=None,
                updated_at=self._now(),
            )

        self._tx(run)

    def _require_work_enabled(self) -> None:
        if not self.covenant_enabled():
            raise OsampError(
                "covenant_off",
                "Mandatory controls are off. This copy cannot start OSAMP work or claim conformance.",
            )
        if self.current_acknowledgment() is None:
            raise OsampError(
                "ack_required",
                "OSAMP work stays blocked until the operator acknowledges the current safeguards.",
            )

    def _load(self, obligation_id: str) -> dict:
        obligation = self.postbox.get_obligation(obligation_id)
        if obligation is None:
            raise OsampError("missing", "That commitment is not in the postbox.")
        return obligation

    def _context(self, obligation: dict) -> dict:
        obligation = dict(obligation)
        obligation["checkpoint_required"] = bool(obligation["limits"].get("checkpoint_required"))
        return {
            "covenant_enabled": self.covenant_enabled(),
            "ack": self.current_acknowledgment(),
            "now": self._now(),
            "blocks": self.postbox.active_blocks(),
            "storage_pressure": self.postbox.get_meta("storage_pressure") == "1",
        }

    def play(self, obligation_id: str) -> None:
        def run():
            self._require_work_enabled()
            obligation = self._load(obligation_id)
            if obligation["execution_state"] == "working":
                raise OsampError("already_working", "Work is already running. The lease was not renewed.")
            if obligation["execution_state"] == "paused":
                reason = (obligation.get("hold") or {}).get("reason")
                if reason not in {None, "operator_pause"}:
                    raise OsampError("held", "A pause that is a safety hold cannot resume this way.")
            blockers = play_blockers(obligation, self._context(obligation))
            if blockers:
                raise OsampError("play_refused", blockers[0])
            self._hook("before_play", obligation=obligation)
            lease = _plus(self._now(), self.profile.limits["lease_seconds"])
            history = list(obligation["history"])
            history.append({"kind": "play", "at": self._now(), "budget_spent": obligation["budget_spent"]})
            cleared_hold = obligation.get("hold")
            keep_hold = None if (cleared_hold or {}).get("reason") == "operator_pause" else cleared_hold
            self.postbox.update_obligation(
                obligation_id,
                execution_state="working",
                lease_expires_at=lease,
                history=history,
                hold=keep_hold,
                updated_at=self._now(),
            )
            self._refresh_capsule(obligation_id)

        self._tx(run)

    def dispatch_tool(self, obligation_id: str, tool_name: str) -> str:
        lease_hit = False

        def run():
            nonlocal lease_hit
            obligation = self._load(obligation_id)
            if obligation["execution_state"] != "working":
                raise OsampError("tool_refused", "Tools run only while this work is in a checked running state.")
            if obligation.get("lease_expires_at") and parse_time(self._now()) > parse_time(
                obligation["lease_expires_at"]
            ):
                self._enter_hold(obligation, "lease_expired", "The work permit timed out.")
                lease_hit = True
                return "held"
            blockers = play_blockers(obligation, self._context(obligation))
            if blockers:
                raise OsampError("tool_refused", blockers[0])
            allow = set(obligation["limits"].get("tool_allowlist") or [])
            if tool_name not in allow:
                raise OsampError("tool_refused", "That tool is not on the accepted list.")
            self._bump("tool_calls")
            self.postbox.audit("tool_call", obligation_id, {"tool": tool_name}, self._now())
            return "tool-ok"

        result = self._tx(run)
        if lease_hit:
            raise OsampError("lease_expired", "The work permit timed out. It was not renewed.")
        return result

    def note_progress(self, obligation_id: str, progress_digest: str | None, cost: int = 1) -> dict:
        def run():
            obligation = self._load(obligation_id)
            if obligation["execution_state"] != "working":
                raise OsampError("not_running", "Attempts are recorded only while this work is running.")
            if obligation["budget_spent"] + cost > obligation["budget_ceiling"]:
                self._enter_hold(obligation, "no_progress", "The budget is spent.")
                return {"held": True, "reason": "no_progress"}
            updates = note_attempt(obligation, progress_digest, self.profile.limits)
            self.postbox.update_obligation(
                obligation_id,
                attempt_count=updates["attempt_count"],
                same_progress_count=updates["same_progress_count"],
                last_progress_digest=updates["last_progress_digest"],
                budget_spent=obligation["budget_spent"] + cost,
                updated_at=self._now(),
            )
            if updates.get("hold_reason"):
                fresh = self._load(obligation_id)
                self._enter_hold(fresh, updates["hold_reason"], hold_sentence(updates["hold_reason"]))
                return {"held": True, "reason": updates["hold_reason"]}
            self._refresh_capsule(obligation_id)
            return {"held": False, "attempt_count": updates["attempt_count"]}

        return self._tx(run)

    def delegate(self, obligation_id: str, to_peer: str, stage_id: str, stage_index: int, child_budget: int) -> dict:
        def run():
            obligation = self._load(obligation_id)
            if obligation["execution_state"] in {"held", "review", "stopped", "stop_pending", "closed"}:
                raise OsampError("held", "Held work cannot be passed onward.")
            decision = note_delegation(
                obligation, to_peer, stage_id, stage_index, child_budget, self.profile.limits
            )
            if decision.get("hold_reason"):
                self._enter_hold(obligation, decision["hold_reason"], hold_sentence(decision["hold_reason"]))
                return {"held": True, "reason": decision["hold_reason"]}
            self.postbox.update_obligation(
                obligation_id,
                delegation=decision["delegation"],
                budget_reserved=decision["budget_reserved"],
                updated_at=self._now(),
            )
            self.postbox.insert_outbound(
                {
                    "outbound_id": self._new_id("out"),
                    "event_id": obligation["event_id"],
                    "next_hop": to_peer,
                    "state": "queued",
                    "body": {"stage_id": stage_id, "child_budget": child_budget},
                    "created_at": self._now(),
                }
            )
            self._refresh_capsule(obligation_id)
            return {"held": False}

        return self._tx(run)

    def record_opinion(
        self,
        obligation_id: str,
        reviewer_id: str,
        claim_id: str,
        lineage_id: str,
        agrees: bool,
        independent: bool = False,
    ) -> dict:
        def run():
            obligation = self._load(obligation_id)
            opinions = list(obligation["opinions"])
            opinions.append(
                {
                    "reviewer_id": reviewer_id,
                    "claim_id": claim_id,
                    "lineage_id": lineage_id,
                    "agrees": agrees,
                    "independent": independent and agrees,
                }
            )
            self.postbox.update_obligation(obligation_id, opinions=opinions, updated_at=self._now())
            fresh = self._load(obligation_id)
            if copied_source(fresh["opinions"]):
                self._enter_hold(fresh, "copied_source", hold_sentence("copied_source"), execution="review")
                return {"held": True, "reason": "copied_source"}
            return {"held": False, "independent": independent_opinion(fresh["opinions"])}

        return self._tx(run)

    def record_conflict(self, obligation_id: str, references: list[str], question: str) -> None:
        def run():
            obligation = self._load(obligation_id)
            self._enter_hold(
                obligation,
                "conflicting_evidence",
                question,
                extra={"references": references},
            )

        self._tx(run)

    def request_hold(self, obligation_id: str, reason: str, question: str) -> None:
        if reason not in HUMAN_HOLD_REASONS:
            raise OsampError("hold_refused", "The hold reason must be one of the named Contract Zero reasons.")

        def run():
            obligation = self._load(obligation_id)
            self._enter_hold(obligation, reason, question)

        self._tx(run)

    def widen_hold(self, obligation_id: str, scope: str, scope_ref: str, operator_id: str, key: bytes) -> None:
        payload = {
            "obligation_id": obligation_id,
            "operator_id": operator_id,
            "scope": scope,
            "scope_ref": scope_ref,
        }

        def run():
            self._require_person_key(operator_id, key)
            if not mac_ok(key, payload, _presented_mac(key, payload)):
                raise OsampError("unauthenticated", "Widening a hold needs the operator's approval tag.")
            self.postbox.insert_block(
                {
                    "block_id": self._new_id("block"),
                    "scope": scope,
                    "scope_ref": scope_ref,
                    "reason": "widened hold",
                    "at": self._now(),
                }
            )
            self.postbox.audit("hold_widened", obligation_id, payload, self._now())

        self._tx(run)

    def freeze_authority(self, scope: str, scope_ref: str, reason: str) -> None:
        def run():
            self.postbox.insert_block(
                {
                    "block_id": self._new_id("block"),
                    "scope": scope,
                    "scope_ref": scope_ref,
                    "reason": reason,
                    "at": self._now(),
                }
            )
            if scope == "task":
                obligation = self._load(scope_ref)
                self._enter_hold(obligation, "compromised_authority", hold_sentence("compromised_authority"))

        self._tx(run)

    def pause(self, obligation_id: str) -> None:
        def run():
            obligation = self._load(obligation_id)
            if obligation["execution_state"] not in {"ready", "working"}:
                raise OsampError("pause_refused", "Only running or ready work can be paused this way.")
            checkpoint = {
                "checkpoint_id": self._new_id("ckpt"),
                "queue_cursor": obligation["queue_cursor"],
                "attempt_count": obligation["attempt_count"],
                "broken": False,
            }
            history = list(obligation["history"])
            history.append({"kind": "pause", "at": self._now(), "checkpoint_id": checkpoint["checkpoint_id"]})
            self.postbox.update_obligation(
                obligation_id,
                execution_state="paused",
                checkpoint=checkpoint,
                history=history,
                hold={
                    "hold_id": self._new_id("hold"),
                    "reason": "operator_pause",
                    "resolved": False,
                    "question": "A person paused this work.",
                    "permitted_steps": ["leave_held", "approve_same_step"],
                    "scope": "task",
                },
                updated_at=self._now(),
            )

        self._tx(run)

    def stop_local(self, obligation_id: str) -> None:
        def run():
            obligation = self._load(obligation_id)
            history = list(obligation["history"])
            history.append(
                {
                    "kind": "stop_local",
                    "at": self._now(),
                    "external_effects_unchanged": obligation["uncertain_effects"],
                }
            )
            self.postbox.update_obligation(
                obligation_id,
                execution_state="stopped",
                history=history,
                updated_at=self._now(),
            )
            self._refresh_capsule(obligation_id)

        self._tx(run)

    def request_remote_stop(self, obligation_id: str, peer_id: str) -> None:
        def run():
            obligation = self._load(obligation_id)
            self.postbox.update_obligation(
                obligation_id,
                execution_state="stop_pending",
                hold={
                    "hold_id": self._new_id("hold"),
                    "reason": "remote_stop",
                    "resolved": False,
                    "question": "Wait until the other computer confirms it stopped.",
                    "permitted_steps": list(PERMITTED_HUMAN_STEPS),
                    "scope": "task",
                    "remote_peer": peer_id,
                },
                updated_at=self._now(),
            )
            self.postbox.audit(
                "stop_pending",
                obligation_id,
                {"peer_id": peer_id, "status": "STOP_PENDING"},
                self._now(),
            )
            self._refresh_capsule(obligation_id)
            return obligation

        self._tx(run)

    def acknowledge_remote_stop(self, obligation_id: str, peer_id: str) -> None:
        def run():
            obligation = self._load(obligation_id)
            hold = obligation.get("hold") or {}
            if obligation["execution_state"] != "stop_pending" or hold.get("remote_peer") != peer_id:
                raise OsampError(
                    "stop_unconfirmed",
                    "The stop stays STOP_PENDING until the named computer confirms it.",
                )
            history = list(obligation["history"])
            history.append({"kind": "remote_stop_acked", "at": self._now(), "peer_id": peer_id})
            self.postbox.update_obligation(
                obligation_id,
                execution_state="stopped",
                history=history,
                updated_at=self._now(),
            )

        self._tx(run)

    def confirm_local_stop(self, obligation_id: str) -> None:
        """The local supervisor confirms an inbound stop. Silence does not do this."""

        def run():
            obligation = self._load(obligation_id)
            if obligation["execution_state"] != "stop_pending":
                raise OsampError("stop_unconfirmed", "There is no pending stop to confirm.")
            self.postbox.update_obligation(
                obligation_id,
                execution_state="stopped",
                updated_at=self._now(),
            )

        self._tx(run)

    def _enter_stop_pending(self, obligation_id: str, source: str) -> None:
        obligation = self.postbox.get_obligation(obligation_id)
        if obligation is None:
            return
        if obligation["execution_state"] in {"stopped", "closed", "completed"}:
            return
        self.postbox.update_obligation(
            obligation_id,
            execution_state="stop_pending",
            hold={
                "hold_id": self._new_id("hold"),
                "reason": "remote_stop",
                "resolved": False,
                "question": "A stop arrived. The local supervisor has not confirmed it yet.",
                "permitted_steps": list(PERMITTED_HUMAN_STEPS),
                "scope": "task",
                "source": source,
            },
            updated_at=self._now(),
        )
        self.postbox.audit("stop_pending", obligation_id, {"source": source, "status": "STOP_PENDING"}, self._now())

    def rewind(self, obligation_id: str, checkpoint_id: str, compensation: str) -> None:
        def run():
            obligation = self._load(obligation_id)
            updates = rewind_updates(obligation, checkpoint_id, compensation)
            self.postbox.update_obligation(obligation_id, updated_at=self._now(), **updates)
            self.postbox.audit(
                "rewind",
                obligation_id,
                {"checkpoint_id": checkpoint_id, "compensation": compensation},
                self._now(),
            )

        self._tx(run)

    def fast_forward(self, obligation_id: str, to_cursor: int) -> None:
        def run():
            obligation = self._load(obligation_id)
            require_fast_forward(obligation, to_cursor)
            self.postbox.update_obligation(
                obligation_id,
                queue_cursor=to_cursor,
                updated_at=self._now(),
            )

        self._tx(run)

    def timeout(self, obligation_id: str) -> None:
        def run():
            obligation = self._load(obligation_id)
            self._enter_hold(obligation, "timeout", hold_sentence("timeout"))

        self._tx(run)

    def note_uncertain_effect(self, obligation_id: str, effect_id: str) -> None:
        def run():
            obligation = self._load(obligation_id)
            effects = list(obligation["uncertain_effects"])
            effects.append({"effect_id": effect_id, "state": "uncertain"})
            history = list(obligation["history"])
            history.append({"kind": "uncertain_effect", "effect_id": effect_id, "at": self._now()})
            self.postbox.update_obligation(
                obligation_id,
                uncertain_effects=effects,
                execution_state="uncertain",
                history=history,
                updated_at=self._now(),
            )
            self._refresh_capsule(obligation_id)

        self._tx(run)

    def replay_effect(self, obligation_id: str, effect_id: str) -> None:
        obligation = self._load(obligation_id)
        known = {item["effect_id"] for item in obligation["uncertain_effects"]}
        if effect_id in known or obligation["execution_state"] == "uncertain":
            raise OsampError(
                "replay_refused",
                "An external effect that may already have happened is not repeated.",
            )
        raise OsampError("replay_refused", "This slice does not repeat external effects.")

    def submit_result(self, obligation_id: str, result_digest: str, checks_passed: bool) -> None:
        def run():
            obligation = self._load(obligation_id)
            if obligation["execution_state"] in {"held", "review", "stop_pending", "uncertain", "stopped", "closed"}:
                raise OsampError("result_refused", "A result cannot clear a hold or a review.")
            if not checks_passed:
                self._enter_hold(
                    obligation,
                    "conflicting_evidence",
                    "The required checks did not pass. A plausible answer is not completion.",
                )
                return
            if copied_source(obligation["opinions"]) and not independent_opinion(obligation["opinions"]):
                self._enter_hold(obligation, "copied_source", hold_sentence("copied_source"), execution="review")
                return
            self.postbox.update_obligation(
                obligation_id,
                execution_state="result_submitted",
                result_digest=result_digest,
                checks_passed=True,
                updated_at=self._now(),
            )

        self._tx(run)

    def complete(self, obligation_id: str) -> None:
        def run():
            obligation = self._load(obligation_id)
            if obligation["execution_state"] != "result_submitted" or not obligation["checks_passed"]:
                raise OsampError(
                    "complete_refused",
                    "Completion needs a submitted result that passed its checks. History is kept.",
                )
            if obligation.get("hold") and not obligation["hold"].get("resolved"):
                raise OsampError("complete_refused", "An open hold cannot be rewritten as success.")
            history = list(obligation["history"])
            history.append({"kind": "completed", "at": self._now()})
            self.postbox.update_obligation(
                obligation_id,
                execution_state="completed",
                authority_state="closed",
                history=history,
                updated_at=self._now(),
            )
            self.postbox.insert_receipt(
                {
                    "receipt_id": self._new_id("rcpt"),
                    "kind": "completion",
                    "event_id": obligation["event_id"],
                    "obligation_id": obligation_id,
                    "body": {"result_digest": obligation["result_digest"]},
                    "created_at": self._now(),
                }
            )

        self._tx(run)

    def request_help(self, obligation_id: str) -> str:
        def run():
            obligation = self._load(obligation_id)
            hold = obligation.get("hold") or {}
            state = "queued"
            body = {
                "what_stopped": hold.get("reason"),
                "question": hold.get("question") or "Please review this held work.",
                "effects": [item["effect_id"] for item in obligation["uncertain_effects"]],
                "decisions": list(PERMITTED_HUMAN_STEPS),
                "reachable": obligation["contact_reachable"],
            }
            if not obligation["contact_reachable"]:
                body["note"] = "No contact is reachable. The work stays waiting."
            notification_id = self._new_id("note")
            self.postbox.insert_notification(
                {
                    "notification_id": notification_id,
                    "obligation_id": obligation_id,
                    "state": state,
                    "reminder_count": 0,
                    "body": body,
                    "created_at": self._now(),
                    "updated_at": self._now(),
                }
            )
            return notification_id

        return self._tx(run)

    def mark_notification(self, notification_id: str, state: str) -> None:
        if state not in {"queued", "sent", "delivered", "acknowledged"}:
            raise OsampError("notice_refused", "Unknown notification state.")

        def run():
            self.postbox.update_notification(notification_id, state=state, updated_at=self._now())

        self._tx(run)

    def remind(self, obligation_id: str) -> dict:
        def run():
            notes = self.postbox.notifications_for(obligation_id)
            if not notes:
                raise OsampError("notice_missing", "There is no help notice to remind.")
            note = notes[-1]
            gap = self.profile.limits["reminder_gap_seconds"]
            if note["reminder_count"] >= self.profile.limits["max_reminders"]:
                return {"sent": False, "reason": "limit"}
            if parse_time(self._now()) < _plus_time(note["updated_at"], gap):
                return {"sent": False, "reason": "too_soon"}
            self.postbox.update_notification(
                note["notification_id"],
                reminder_count=note["reminder_count"] + 1,
                updated_at=self._now(),
            )
            return {"sent": True, "reminder_count": note["reminder_count"] + 1}

        return self._tx(run)

    def natural_language_instruction(self, obligation_id: str, text: str) -> None:
        self._load(obligation_id)
        if text:
            raise OsampError(
                "not_authority",
                "A sentence is not a decision. This work was not changed.",
            )
        raise OsampError(
            "not_authority",
            "A sentence is not a decision. This work was not changed.",
        )

    def revoke_work(self, obligation_id: str) -> None:
        """Local revocation record. This does not reach another computer."""

        def run():
            obligation = self._load(obligation_id)
            history = list(obligation["history"])
            history.append({"kind": "revoked", "at": self._now()})
            self.postbox.update_obligation(
                obligation_id,
                authority_state="revoked",
                execution_state="held",
                history=history,
                updated_at=self._now(),
            )
            self.postbox.audit("revoked", obligation_id, {"obligation_id": obligation_id}, self._now())

        self._tx(run)

    def invoke_model(self, prompt: str) -> str:
        """Present so tests can prove the supervisor does not call it."""
        raise OsampError("model_off", "No language model is running.")

    def resolve_human(self, decision: dict, key: bytes, tag: str) -> dict:
        def run():
            obligation = self._load(decision.get("obligation_id", ""))
            if "mac" in decision:
                raise OsampError("not_authority", "Put the approval tag beside the decision, not inside the sentence.")
            if not mac_ok(key, decision, tag):
                raise OsampError("unauthenticated", "The approval tag does not match. The work stays held.")
            self._require_person_key(decision.get("operator_id", ""), key)
            check_decision_shape(decision, obligation)
            kind = decision["kind"]
            if kind == "leave_held":
                self.postbox.audit("human_decision", obligation["obligation_id"], {"kind": kind}, self._now())
                return {"resumed": False, "plain": "The work stays held, as requested."}
            if kind == "amend_budget":
                ceiling = int(decision.get("budget_ceiling", obligation["budget_ceiling"]))
                if ceiling < obligation["budget_spent"]:
                    raise OsampError("budget_refused", "The new ceiling is below what is already spent.")
                self.postbox.update_obligation(
                    obligation["obligation_id"],
                    budget_ceiling=ceiling,
                    updated_at=self._now(),
                )
                self.postbox.audit(
                    "human_decision",
                    obligation["obligation_id"],
                    {"kind": kind, "budget_ceiling": ceiling, "budget_spent": obligation["budget_spent"]},
                    self._now(),
                )
                return {
                    "resumed": False,
                    "plain": "The ceiling changed. Spent budget was not reset and the work was not resumed.",
                }
            if kind == "accept_handoff":
                self.postbox.audit("human_decision", obligation["obligation_id"], {"kind": kind}, self._now())
                return {
                    "resumed": False,
                    "plain": "A handoff was noted. The original commitment is not finished.",
                }
            if kind == "terminate":
                self._close_obligation(obligation, "terminated")
                return {"resumed": False, "plain": "The work is closed. It is not marked successful."}
            # clarify or approve_same_step: recheck gates, do not execute here.
            if obligation["budget_spent"] >= obligation["budget_ceiling"]:
                self.postbox.audit(
                    "human_decision_blocked",
                    obligation["obligation_id"],
                    {"kind": kind, "reason": "budget"},
                    self._now(),
                )
                return {
                    "resumed": False,
                    "plain": "The person approved a step, but the budget is spent, so the work stays held.",
                }
            if not self.covenant_enabled() or self.current_acknowledgment() is None:
                return {
                    "resumed": False,
                    "plain": "The decision is recorded as refused because safeguards or acknowledgment are not current.",
                }
            covered = play_blockers(obligation, self._context(obligation))
            # The hold itself is one blocker; a valid decision for this hold may clear it
            # only after the other blockers are absent.
            other = [item for item in covered if "human decision" not in item and "Execution is" not in item]
            if other:
                self.postbox.audit(
                    "human_decision_blocked",
                    obligation["obligation_id"],
                    {"kind": kind, "reasons": other},
                    self._now(),
                )
                return {"resumed": False, "plain": other[0]}
            history = list(obligation["hold_history"])
            prior = dict(obligation["hold"] or {})
            prior["resolved"] = True
            prior["decision_id"] = decision["decision_id"]
            history.append(prior)
            work_history = list(obligation["history"])
            work_history.append({"kind": "human_resolution", "decision_id": decision["decision_id"], "at": self._now()})
            self.postbox.update_obligation(
                obligation["obligation_id"],
                execution_state="ready",
                hold=None,
                hold_history=history,
                history=work_history,
                updated_at=self._now(),
            )
            self.postbox.audit(
                "human_decision",
                obligation["obligation_id"],
                {"kind": kind, "decision_id": decision["decision_id"], "attempts_kept": obligation["attempt_count"]},
                self._now(),
            )
            self._refresh_capsule(obligation["obligation_id"])
            return {
                "resumed": False,
                "ready": True,
                "plain": "The decision cleared the hold only. Tools have not run. Counters were not reset.",
            }

        return self._tx(run)

    def report_storage_pressure(self) -> None:
        def run():
            self.postbox.set_meta("storage_pressure", "1")
            for obligation in self.postbox.list_obligations():
                if obligation["execution_state"] in {"ready", "working", "paused"}:
                    self._enter_hold(obligation, "capacity_pressure", hold_sentence("capacity_pressure"))

        self._tx(run)

    def expire_invitations(self) -> int:
        def run():
            removed = 0
            for envelope in self.postbox.envelopes_due(self._now()):
                if self.postbox.obligation_by_event(envelope["event_id"]) is not None:
                    continue
                self.postbox.update_envelope(
                    envelope["event_id"],
                    delivery_state="expired",
                    role_state="expired",
                    body=None,
                    updated_at=self._now(),
                )
                self.postbox.audit(
                    "invitation_expired",
                    envelope["event_id"],
                    {"event_id": envelope["event_id"]},
                    self._now(),
                )
                removed += 1
            return removed

        removed = self._tx(run)
        self.compact()
        return removed

    def review_retention(self) -> list[str]:
        def run():
            notices = []
            warning = self.profile.limits["retention_warning_seconds"]
            now = parse_time(self._now())
            for obligation in self.postbox.list_obligations():
                if not obligation.get("retention_deadline") or obligation["execution_state"] == "closed":
                    continue
                due = parse_time(obligation["retention_deadline"])
                if now < _minus(due, warning):
                    continue
                notes = self.postbox.notifications_for(obligation["obligation_id"])
                if not any(item["body"].get("kind") == "retention" for item in notes):
                    self.postbox.insert_notification(
                        {
                            "notification_id": self._new_id("note"),
                            "obligation_id": obligation["obligation_id"],
                            "state": "queued",
                            "reminder_count": 0,
                            "body": {
                                "kind": "retention",
                                "question": "The retention deadline is near. Choose export, hold, or closure.",
                                "decisions": ["leave_held", "terminate"],
                            },
                            "created_at": self._now(),
                            "updated_at": self._now(),
                        }
                    )
                    notices.append(obligation["obligation_id"])
                if (
                    now >= due
                    and obligation["limits"].get("agreed_closure") == "close_when_due"
                    and obligation["execution_state"] not in {"closed", "completed"}
                ):
                    self._close_obligation(self._load(obligation["obligation_id"]), "retention_closure")
            return notices

        notices = self._tx(run)
        self.compact()
        return notices

    def compact(self) -> None:
        """Rewrite the local file so removed text is not left in free space."""
        if self.postbox._in_tx:
            raise OsampError("transaction", "Cannot compact while a save is in progress.")
        self.postbox.conn.execute("VACUUM")

    def export_minimal(self, obligation_id: str) -> dict:
        obligation = self._load(obligation_id)
        capsule = obligation["capsule"]
        return {
            "obligation_id": obligation_id,
            "work_id": obligation["work_id"],
            "disposition": (obligation.get("closure") or {}).get("disposition"),
            "execution_state": obligation["execution_state"],
            "authority_state": obligation["authority_state"],
            "contract_digest": obligation["contract_digest"],
            "human_id": obligation["human_id"],
            "objective_present": bool(capsule.get("objective")),
        }

    def plain_status(self, obligation_id: str) -> str:
        obligation = self._load(obligation_id)
        envelope = self.postbox.get_envelope(obligation["event_id"])
        delivery = envelope["delivery_state"] if envelope else "unknown"
        hold = obligation.get("hold")
        lines = [
            f"Work: {obligation['work_id']}",
            f"Delivery: {delivery}. Delivery only means the message is in this postbox.",
            f"Authority: {obligation['authority_state']}",
            f"Execution: {obligation['execution_state']}",
        ]
        if obligation["execution_state"] == "stop_pending":
            lines.append("Remote stop: STOP_PENDING")
            lines.append("The other computer has not confirmed that it stopped. Silence is not a stop.")
        if hold:
            lines.append("Needs human help: yes")
            lines.append("Why: " + hold_sentence(hold.get("reason", "")))
            lines.append("Question: " + str(hold.get("question")))
        else:
            lines.append("Needs human help: no")
        lines.append("A language model is not required to keep this record.")
        lines.append(
            f"Budget spent {obligation['budget_spent']} of {obligation['budget_ceiling']}. "
            f"Attempts {obligation['attempt_count']}."
        )
        return "\n".join(lines)

    def capsule(self, obligation_id: str) -> dict:
        return self._load(obligation_id)["capsule"]

    def _enter_hold(self, obligation: dict, reason: str, question: str, execution: str = "held", extra: dict | None = None) -> None:
        history = list(obligation["history"])
        history.append({"kind": "hold", "reason": reason, "at": self._now()})
        hold = {
            "hold_id": self._new_id("hold"),
            "reason": reason,
            "resolved": False,
            "question": question,
            "permitted_steps": list(PERMITTED_HUMAN_STEPS),
            "scope": "task",
        }
        if extra:
            hold.update(extra)
        self.postbox.update_obligation(
            obligation["obligation_id"],
            execution_state="review" if execution == "review" else "held",
            hold=hold,
            history=history,
            updated_at=self._now(),
        )
        self._refresh_capsule(obligation["obligation_id"])

    def _close_obligation(self, obligation: dict, disposition: str) -> None:
        capsule = minimal_closure_capsule(obligation["capsule"], disposition)
        history = list(obligation["history"])
        history.append({"kind": "closed", "disposition": disposition, "at": self._now()})
        self.postbox.update_obligation(
            obligation["obligation_id"],
            objective=None,
            objective_deleted=True,
            execution_state="closed",
            authority_state="closed",
            capsule=capsule,
            closure={"disposition": disposition, "at": self._now()},
            hold=None,
            history=history,
            updated_at=self._now(),
        )
        for note in self.postbox.notifications_for(obligation["obligation_id"]):
            self.postbox.update_notification(
                note["notification_id"],
                body={"kind": "closed", "obligation_id": obligation["obligation_id"], "disposition": disposition},
                updated_at=self._now(),
            )
        self.postbox.audit(
            "closed",
            obligation["obligation_id"],
            {"disposition": disposition, "obligation_id": obligation["obligation_id"]},
            self._now(),
        )

    def _refresh_capsule(self, obligation_id: str) -> None:
        obligation = self._load(obligation_id)
        if obligation["objective_deleted"]:
            return
        previous = obligation["capsule"]
        capsule = dict(previous)
        capsule["budget_ceiling"] = obligation["budget_ceiling"]
        capsule["budget_spent"] = obligation["budget_spent"]
        capsule["budget_reserved"] = obligation["budget_reserved"]
        capsule["lease_expires_at"] = obligation.get("lease_expires_at")
        capsule["stop_state"] = obligation["execution_state"]
        capsule["external_effects"] = obligation["uncertain_effects"]
        capsule["checkpoint_id"] = (obligation.get("checkpoint") or {}).get("checkpoint_id")
        hold = obligation.get("hold")
        capsule["blocker"] = None if hold is None else hold.get("reason")
        capsule["uncertainty"] = None if hold is None else hold.get("question")
        capsule["human_decision_requested"] = None if hold is None else hold.get("question")
        if obligation["objective_deleted"]:
            capsule["objective"] = None
        self.postbox.update_obligation(obligation_id, capsule=capsule, updated_at=self._now())


def _presented_mac(key: bytes, payload: dict) -> str:
    from osamp.auth import mac

    return mac(key, payload)


def _plus(now: str, seconds: int) -> str:
    from datetime import timedelta

    from osamp.clock import format_time

    return format_time(parse_time(now) + timedelta(seconds=seconds))


def _plus_time(now: str, seconds: int):
    from datetime import timedelta

    return parse_time(now) + timedelta(seconds=seconds)


def _minus(moment, seconds: int):
    from datetime import timedelta

    return moment - timedelta(seconds=seconds)


def _profile_from_json(raw: str) -> Profile:
    data = json.loads(raw)
    return Profile(
        limits=data["limits"],
        allowed_task_classes=tuple(data["allowed_task_classes"]),
        size=data["size"],
        promise_text=data["promise_text"],
        governance_version=data["governance_version"],
        profile_id=data["profile_id"],
    )
