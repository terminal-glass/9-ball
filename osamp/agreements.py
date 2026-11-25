"""Peer, Tribe, Clan, Table, and Work.

These are the five negotiated categories. Contract Zero is not one of them.
Nothing in this module sends network mail. An approved bridge queues a local
note only.
"""

from __future__ import annotations

import json
from typing import Any

from osamp.auth import mac
from osamp.canonical import digest, key_hash
from osamp.errors import OsampError

SCHEMA = """
CREATE TABLE IF NOT EXISTS agreements (
    agreement_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    digest TEXT NOT NULL,
    body_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bridges (
    bridge_id TEXT PRIMARY KEY,
    clan_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    peers_json TEXT NOT NULL,
    data_class TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL,
    approver TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS endorsements (
    endorsement_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    statement TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS obligation_links (
    obligation_id TEXT PRIMARY KEY,
    peer_agreement_id TEXT,
    table_agreement_id TEXT,
    work_agreement_id TEXT
);
"""


def _dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AgreementBook:
    def __init__(self, node):
        self.node = node
        self._pending_role = None
        node.postbox.conn.executescript(SCHEMA)
        node.hook = self

    def _now(self) -> str:
        return self.node.clock.now()

    def _tx(self, fn):
        return self.node._tx(fn)

    def _require_key(self, person_id: str, key: bytes) -> None:
        stored = self.node.postbox.person_hash(person_id)
        if stored is None or stored != key_hash(key):
            raise OsampError("unauthenticated", "That approval does not match a registered person.")

    def _insert(self, category: str, body: dict, status: str = "offered") -> str:
        agreement_id = self.node._new_id(category)
        now = self._now()
        self.node.postbox.conn.execute(
            """INSERT INTO agreements(agreement_id, category, status, digest, body_json, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)""",
            (agreement_id, category, status, digest(body), _dumps(body), now, now),
        )
        self.node.postbox.audit(
            "agreement_offered",
            agreement_id,
            {"category": category, "agreement_id": agreement_id, "status": status},
            now,
        )
        return agreement_id

    def _get(self, agreement_id: str) -> dict:
        row = self.node.postbox.conn.execute(
            "SELECT * FROM agreements WHERE agreement_id=?", (agreement_id,)
        ).fetchone()
        if row is None:
            raise OsampError("missing_agreement", "That agreement is not on this computer.")
        item = dict(row)
        item["body"] = json.loads(item.pop("body_json"))
        return item

    def _save(self, agreement_id: str, status: str, body: dict) -> None:
        self.node.postbox.conn.execute(
            "UPDATE agreements SET status=?, digest=?, body_json=?, updated_at=? WHERE agreement_id=?",
            (status, digest(body), _dumps(body), self._now(), agreement_id),
        )

    def _accept(self, agreement_id: str, person_id: str, key: bytes, action: str) -> dict:
        self._require_key(person_id, key)
        agreement = self._get(agreement_id)
        payload = {"action": action, "agreement_id": agreement_id, "person_id": person_id}
        tag = mac(key, payload)
        body = dict(agreement["body"])
        body["accepted_by"] = person_id
        body["acceptance_mac"] = tag
        self._save(agreement_id, "accepted", body)
        self.node.postbox.audit(
            "agreement_accepted",
            agreement_id,
            {"category": agreement["category"], "person_id": person_id},
            self._now(),
        )
        return self._get(agreement_id)

    def propose_peer(self, owner_id: str, key_id: str, message_types: list[str], data_classes: list[str]) -> str:
        def run():
            return self._insert(
                "peer",
                {
                    "owner_id": owner_id,
                    "key_id": key_id,
                    "message_types": message_types,
                    "data_classes": data_classes,
                },
            )

        return self._tx(run)

    def accept_peer(self, agreement_id: str, person_id: str, key: bytes) -> dict:
        return self._tx(lambda: self._accept(agreement_id, person_id, key, "accept_peer"))

    def revoke_peer(self, agreement_id: str, person_id: str, key: bytes) -> None:
        def run():
            self._require_key(person_id, key)
            agreement = self._get(agreement_id)
            if agreement["category"] != "peer":
                raise OsampError("peer_required", "Revocation of this kind needs a peer agreement.")
            body = dict(agreement["body"])
            body["revoked_by"] = person_id
            self._save(agreement_id, "revoked", body)
            self.node.postbox.audit("peer_revoked", agreement_id, {"person_id": person_id}, self._now())

        self._tx(run)

    def peer_for_sender(self, key_id: str) -> dict | None:
        rows = self.node.postbox.conn.execute(
            "SELECT * FROM agreements WHERE category='peer'"
        ).fetchall()
        for row in rows:
            body = json.loads(row["body_json"])
            if body.get("key_id") == key_id:
                item = dict(row)
                item["body"] = body
                return item
        return None

    def propose_tribe(self, name: str, members: list[str], offer_budget: int) -> str:
        def run():
            return self._insert(
                "tribe",
                {
                    "name": name,
                    "members": list(members),
                    "offer_budget": offer_budget,
                    "offers_used": 0,
                    "declined": [],
                },
            )

        return self._tx(run)

    def accept_tribe(self, agreement_id: str, person_id: str, key: bytes) -> dict:
        return self._tx(lambda: self._accept(agreement_id, person_id, key, "accept_tribe"))

    def offer_tribe_help(self, agreement_id: str, target: str, task: str) -> dict:
        def run():
            agreement = self._get(agreement_id)
            if agreement["status"] != "accepted" or agreement["category"] != "tribe":
                raise OsampError("tribe_required", "Help needs an accepted tribe.")
            body = dict(agreement["body"])
            if target not in body["members"]:
                raise OsampError("outside_tribe", "That helper is outside this tribe.")
            if target in body["declined"]:
                raise OsampError("already_declined", "A refusal is not a reason to ask again.")
            if body["offers_used"] >= body["offer_budget"]:
                raise OsampError("budget_spent", "The tribe help budget is spent. It was not renewed.")
            body["offers_used"] += 1
            self._save(agreement_id, "accepted", body)
            outbound_id = self.node._new_id("out")
            self.node.postbox.insert_outbound(
                {
                    "outbound_id": outbound_id,
                    "event_id": agreement_id,
                    "next_hop": target,
                    "state": "queued",
                    "body": {"task": task, "local_only": True},
                    "created_at": self._now(),
                }
            )
            return {"queued": True, "offers_used": body["offers_used"], "outbound_id": outbound_id}

        return self._tx(run)

    def decline_tribe_help(self, agreement_id: str, target: str) -> None:
        def run():
            agreement = self._get(agreement_id)
            body = dict(agreement["body"])
            if target not in body["declined"]:
                body["declined"].append(target)
            self._save(agreement_id, agreement["status"], body)

        self._tx(run)

    def propose_clan(self, name: str, destinations: list[str], max_hops: int) -> str:
        def run():
            return self._insert(
                "clan",
                {"name": name, "destinations": list(destinations), "max_hops": max_hops},
            )

        return self._tx(run)

    def accept_clan(self, agreement_id: str, person_id: str, key: bytes) -> dict:
        return self._tx(lambda: self._accept(agreement_id, person_id, key, "accept_clan"))

    def propose_bridge(self, clan_id: str, purpose: str, peers: list[str], data_class: str, expires_at: str) -> str:
        def run():
            clan = self._get(clan_id)
            if clan["category"] != "clan" or clan["status"] != "accepted":
                raise OsampError("clan_required", "A bridge needs an accepted clan.")
            bridge_id = self.node._new_id("bridge")
            self.node.postbox.conn.execute(
                """INSERT INTO bridges(bridge_id, clan_id, purpose, peers_json, data_class, expires_at, status, approver, created_at)
                VALUES(?, ?, ?, ?, ?, ?, 'offered', NULL, ?)""",
                (bridge_id, clan_id, purpose, _dumps(peers), data_class, expires_at, self._now()),
            )
            return bridge_id

        return self._tx(run)

    def approve_bridge(self, bridge_id: str, person_id: str, key: bytes) -> None:
        def run():
            self._require_key(person_id, key)
            row = self.node.postbox.conn.execute(
                "SELECT * FROM bridges WHERE bridge_id=?", (bridge_id,)
            ).fetchone()
            if row is None:
                raise OsampError("missing_agreement", "That bridge is not recorded.")
            payload = {"action": "approve_bridge", "bridge_id": bridge_id, "person_id": person_id}
            mac(key, payload)
            self.node.postbox.conn.execute(
                "UPDATE bridges SET status='accepted', approver=? WHERE bridge_id=?",
                (person_id, bridge_id),
            )
            self.node.postbox.audit("bridge_accepted", bridge_id, {"person_id": person_id}, self._now())

        self._tx(run)

    def record_endorsement(self, subject_id: str, statement: str) -> str:
        def run():
            endorsement_id = self.node._new_id("endorse")
            self.node.postbox.conn.execute(
                "INSERT INTO endorsements(endorsement_id, subject_id, statement, created_at) VALUES(?, ?, ?, ?)",
                (endorsement_id, subject_id, statement, self._now()),
            )
            return endorsement_id

        return self._tx(run)

    def escalate(self, clan_id: str, destination: str, hop_count: int) -> dict:
        def run():
            clan = self._get(clan_id)
            if clan["status"] != "accepted":
                raise OsampError("clan_required", "Escalation needs an accepted clan.")
            if hop_count > clan["body"]["max_hops"]:
                raise OsampError("boundary_refused", "That hop is beyond the clan limit.")
            allowed = destination in clan["body"]["destinations"] or self._bridge_allows(clan_id, destination)
            if not allowed:
                raise OsampError(
                    "boundary_refused",
                    "That destination is outside the clan and has no approved bridge.",
                )
            outbound_id = self.node._new_id("out")
            self.node.postbox.insert_outbound(
                {
                    "outbound_id": outbound_id,
                    "event_id": clan_id,
                    "next_hop": destination,
                    "state": "queued",
                    "body": {"local_only": True, "destination": destination},
                    "created_at": self._now(),
                }
            )
            return {"queued_locally": True, "transmitted": False, "relay_count": self.node.relay_count()}

        return self._tx(run)

    def _bridge_allows(self, clan_id: str, destination: str) -> bool:
        rows = self.node.postbox.conn.execute(
            "SELECT * FROM bridges WHERE clan_id=? AND status='accepted'", (clan_id,)
        ).fetchall()
        now = self._now()
        for row in rows:
            if row["expires_at"] <= now:
                continue
            peers = json.loads(row["peers_json"])
            if destination in peers:
                return True
        return False

    def propose_table(self, project_id: str, role_id: str, participant: str) -> str:
        def run():
            return self._insert(
                "table",
                {
                    "project_id": project_id,
                    "roles": [{"role_id": role_id, "participant": participant, "status": "offered"}],
                },
            )

        return self._tx(run)

    def accept_table_role(self, agreement_id: str, role_id: str, person_id: str, key: bytes, **accept_kwargs) -> str:
        self._require_key(person_id, key)
        accept_kwargs["table_id"] = agreement_id
        accept_kwargs["role_id"] = role_id
        self._pending_role = {
            "agreement_id": agreement_id,
            "role_id": role_id,
            "person_id": person_id,
        }
        try:
            return self.node.accept(**accept_kwargs)
        finally:
            self._pending_role = None

    def propose_handoff(self, agreement_id: str, from_role: str, to_participant: str) -> None:
        def run():
            agreement = self._get(agreement_id)
            body = dict(agreement["body"])
            body["proposed_handoff"] = {"from_role": from_role, "to_participant": to_participant}
            self._save(agreement_id, agreement["status"], body)

        self._tx(run)

    def role_status(self, agreement_id: str, role_id: str) -> str | None:
        agreement = self._get(agreement_id)
        for role in agreement["body"].get("roles", []):
            if role["role_id"] == role_id:
                return role["status"]
        return None

    def propose_project(self, objective: str, deliverables: list[str], required_checks: list[str], budget: int) -> str:
        def run():
            return self._insert(
                "work",
                {
                    "kind": "project",
                    "objective": objective,
                    "deliverables": deliverables,
                    "required_checks": required_checks,
                    "checks": {},
                    "budget": budget,
                    "spent": 0,
                    "outcome": "active",
                },
            )

        return self._tx(run)

    def accept_work(self, agreement_id: str, person_id: str, key: bytes) -> dict:
        return self._tx(lambda: self._accept(agreement_id, person_id, key, "accept_work"))

    def record_project_check(self, agreement_id: str, check_id: str, passed: bool) -> None:
        def run():
            agreement = self._require_project(agreement_id)
            body = dict(agreement["body"])
            body["checks"][check_id] = passed
            body["spent"] = body["spent"]  # a check does not refill the budget
            self._save(agreement_id, "accepted", body)

        self._tx(run)

    def complete_project(self, agreement_id: str) -> None:
        def run():
            agreement = self._require_project(agreement_id)
            body = dict(agreement["body"])
            missing = [
                check_id
                for check_id in body["required_checks"]
                if body["checks"].get(check_id) is not True
            ]
            if missing or body["outcome"] == "completed":
                raise OsampError(
                    "complete_refused",
                    "A project completes only when every required check passed. A plausible answer is not enough.",
                )
            body["outcome"] = "completed"
            self._save(agreement_id, "closed", body)
            self.node.postbox.audit("project_completed", agreement_id, {"outcome": "completed"}, self._now())

        self._tx(run)

    def _require_project(self, agreement_id: str) -> dict:
        agreement = self._get(agreement_id)
        if agreement["category"] != "work" or agreement["body"].get("kind") != "project":
            raise OsampError("work_required", "That record is not a project.")
        if agreement["status"] not in {"accepted", "closed"}:
            raise OsampError("work_required", "The project is not accepted.")
        return agreement

    def propose_corridor(self, stages: list[dict], budget: int) -> str:
        cleaned = []
        for index, stage in enumerate(stages):
            cleaned.append(
                {
                    "stage_id": stage["stage_id"],
                    "recipient": stage["recipient"],
                    "cost": stage["cost"],
                    "status": "pending",
                    "index": index,
                }
            )
        def run():
            return self._insert(
                "work",
                {
                    "kind": "corridor",
                    "stages": cleaned,
                    "index": 0,
                    "budget": budget,
                    "spent": 0,
                    "outcome": "active",
                },
            )

        return self._tx(run)

    def offer_corridor_stage(self, agreement_id: str) -> dict:
        def run():
            agreement = self._require_corridor(agreement_id)
            body = dict(agreement["body"])
            if body["outcome"] in {"solved", "human_satisfied", "held", "closed"}:
                return {"refused": "corridor_closed"}
            stage = body["stages"][body["index"]]
            if body["spent"] + stage["cost"] > body["budget"]:
                body["outcome"] = "held"
                self._save(agreement_id, "accepted", body)
                return {"refused": "budget_spent", "spent": body["spent"]}
            stage["status"] = "offered"
            self._save(agreement_id, "accepted", body)
            return {"stage_id": stage["stage_id"], "recipient": stage["recipient"], "spent": body["spent"]}

        result = self._tx(run)
        if result.get("refused") == "corridor_closed":
            raise OsampError("corridor_closed", "This corridor is not taking another stage.")
        if result.get("refused") == "budget_spent":
            raise OsampError("budget_spent", "The corridor budget is spent. It was not renewed.")
        return result

    def accept_corridor_stage(self, agreement_id: str, stage_id: str) -> dict:
        def run():
            agreement = self._require_corridor(agreement_id)
            body = dict(agreement["body"])
            stage = body["stages"][body["index"]]
            if stage["stage_id"] != stage_id:
                raise OsampError("corridor_refused", "Only the current stage can be accepted.")
            if stage["status"] == "accepted":
                return {"spent": body["spent"], "repeated": True}
            if body["spent"] + stage["cost"] > body["budget"]:
                raise OsampError("budget_spent", "The corridor budget is spent. It was not renewed.")
            body["spent"] += stage["cost"]
            stage["status"] = "accepted"
            self._save(agreement_id, "accepted", body)
            return {"spent": body["spent"], "repeated": False}

        return self._tx(run)

    def solve_corridor(self, agreement_id: str, evidence_digest: str) -> None:
        def run():
            agreement = self._require_corridor(agreement_id)
            body = dict(agreement["body"])
            body["outcome"] = "solved"
            body["evidence_digest"] = evidence_digest
            self._save(agreement_id, "closed", body)
            self.node.postbox.audit("corridor_solved", agreement_id, {"outcome": "solved"}, self._now())

        self._tx(run)

    def decline_corridor_stage(self, agreement_id: str, stage_id: str) -> dict:
        def run():
            agreement = self._require_corridor(agreement_id)
            body = dict(agreement["body"])
            recipients = [stage["recipient"] for stage in body["stages"]]
            stage = body["stages"][body["index"]]
            if stage["stage_id"] != stage_id:
                raise OsampError("corridor_refused", "A decline cannot choose a different stage.")
            stage["status"] = "declined"
            body["outcome"] = "held"
            self._save(agreement_id, "accepted", body)
            return {"recipients": recipients, "spent": body["spent"], "outcome": "held"}

        return self._tx(run)

    def advance_corridor(self, agreement_id: str) -> dict:
        def run():
            agreement = self._require_corridor(agreement_id)
            body = dict(agreement["body"])
            if body["outcome"] != "active":
                return {"refused": "corridor_closed", "spent": body["spent"]}
            current = body["stages"][body["index"]]
            if current["status"] != "accepted":
                return {"refused": "corridor_refused", "spent": body["spent"]}
            if body["index"] + 1 >= len(body["stages"]):
                body["outcome"] = "held"
                self._save(agreement_id, "accepted", body)
                return {"refused": "corridor_held", "spent": body["spent"]}
            body["index"] += 1
            self._save(agreement_id, "accepted", body)
            return {"index": body["index"], "spent": body["spent"]}

        result = self._tx(run)
        if result.get("refused") == "corridor_closed":
            raise OsampError("corridor_closed", "A solved, held, or satisfied corridor does not advance.")
        if result.get("refused") == "corridor_refused":
            raise OsampError("corridor_refused", "The current stage is not accepted.")
        if result.get("refused") == "corridor_held":
            raise OsampError("corridor_held", "There is no approved next stage. The corridor is held.")
        return result

    def attempt_earlier_stage(self, agreement_id: str, stage_index: int) -> None:
        def run():
            agreement = self._require_corridor(agreement_id)
            body = dict(agreement["body"])
            if stage_index < body["index"]:
                spent = body["spent"]
                body["outcome"] = "held"
                self._save(agreement_id, "accepted", body)
                self.node.postbox.audit(
                    "corridor_loop",
                    agreement_id,
                    {"stage_index": stage_index, "current": body["index"], "spent": spent},
                    self._now(),
                )
                return {"refused": "loop", "spent": spent}
            return {"refused": "not_earlier"}

        result = self._tx(run)
        if result["refused"] == "loop":
            raise OsampError("circular_delegation", "The corridor cannot return to an earlier stage.")
        raise OsampError("corridor_refused", "That stage is not an earlier stage.")

    def human_satisfied(self, agreement_id: str, person_id: str, key: bytes) -> str:
        def run():
            self._require_key(person_id, key)
            agreement = self._require_corridor(agreement_id)
            payload = {"action": "human_satisfied", "agreement_id": agreement_id, "person_id": person_id}
            tag = mac(key, payload)
            body = dict(agreement["body"])
            body["outcome"] = "human_satisfied"
            body["satisfied_by"] = person_id
            self._save(agreement_id, "closed", body)
            receipt_id = self.node._new_id("rcpt")
            self.node.postbox.insert_receipt(
                {
                    "receipt_id": receipt_id,
                    "kind": "human_satisfaction",
                    "event_id": agreement_id,
                    "obligation_id": None,
                    "body": {"agreement_id": agreement_id, "person_id": person_id, "tag": tag},
                    "created_at": self._now(),
                }
            )
            self.node.postbox.audit(
                "human_satisfied",
                agreement_id,
                {"person_id": person_id, "receipt_id": receipt_id},
                self._now(),
            )
            return receipt_id

        return self._tx(run)

    def _require_corridor(self, agreement_id: str) -> dict:
        agreement = self._get(agreement_id)
        if agreement["category"] != "work" or agreement["body"].get("kind") != "corridor":
            raise OsampError("work_required", "That record is not a corridor.")
        if agreement["status"] not in {"accepted", "closed"}:
            raise OsampError("work_required", "The corridor is not accepted.")
        return agreement

    def before_receive(self, node, envelope: dict) -> None:
        peer = self.peer_for_sender(envelope.get("sender_key_id", ""))
        if peer is not None and peer["status"] == "revoked":
            raise OsampError("peer_revoked", "A revoked peer cannot start mail handling or forwarding.")

    def before_relay(self, node, envelope: dict, next_hop: str) -> None:
        peer = self.peer_for_sender(envelope.get("sender_key_id", ""))
        if peer is None or peer["status"] != "accepted":
            raise OsampError("peer_required", "Forwarding needs an accepted peer. None was transmitted.")

    def before_accept(self, node, envelope: dict, task_class: str, table_id: str | None, role_id: str | None) -> None:
        peer = self.peer_for_sender(envelope.get("sender_key_id", ""))
        if peer is None or peer["status"] != "accepted":
            raise OsampError("peer_required", "Accepting work needs an accepted peer agreement.")
        allowed_types = set(peer["body"].get("message_types") or [])
        if allowed_types and envelope.get("event_type") not in allowed_types:
            raise OsampError("outside_peer", "That message type is outside the peer agreement.")
        if not table_id:
            return
        pending = self._pending_role
        if pending and pending["role_id"] == role_id and pending["agreement_id"] == table_id:
            self._mark_role(pending["agreement_id"], role_id, "accepted")
            return
        if not self._role_is_accepted(table_id, role_id):
            raise OsampError("table_required", "A table role is not accepted merely because an invitation arrived.")

    def before_play(self, node, obligation: dict) -> None:
        row = node.postbox.conn.execute(
            "SELECT * FROM obligation_links WHERE obligation_id=?",
            (obligation["obligation_id"],),
        ).fetchone()
        if row is None:
            return
        if row["work_agreement_id"]:
            work = self._get(row["work_agreement_id"])
            outcome = work["body"].get("outcome")
            if work["status"] == "revoked" or outcome in {"held", "solved", "human_satisfied"}:
                raise OsampError("play_refused", "The work agreement does not currently allow execution.")

    def link_obligation(self, obligation_id: str, peer_agreement_id: str | None, table_agreement_id: str | None, work_agreement_id: str | None) -> None:
        def run():
            self.node.postbox.conn.execute(
                """INSERT INTO obligation_links(obligation_id, peer_agreement_id, table_agreement_id, work_agreement_id)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(obligation_id) DO UPDATE SET
                peer_agreement_id=excluded.peer_agreement_id,
                table_agreement_id=excluded.table_agreement_id,
                work_agreement_id=excluded.work_agreement_id""",
                (obligation_id, peer_agreement_id, table_agreement_id, work_agreement_id),
            )

        self._tx(run)

    def _mark_role(self, agreement_id: str, role_id: str, status: str) -> None:
        agreement = self._get(agreement_id)
        body = dict(agreement["body"])
        found = False
        for role in body["roles"]:
            if role["role_id"] == role_id:
                role["status"] = status
                found = True
        if not found:
            raise OsampError("table_required", "That role is not on the table.")
        self._save(agreement_id, "accepted", body)

    def _role_is_accepted(self, table_id: str, role_id: str | None) -> bool:
        try:
            agreement = self._get(table_id)
        except OsampError:
            return False
        if agreement["category"] != "table":
            return False
        for role in agreement["body"].get("roles", []):
            if role["role_id"] == role_id and role["status"] == "accepted":
                return True
        return False
