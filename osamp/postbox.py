"""Durable local Postbox.

One SQLite file holds mail, accepted obligations, receipts, holds, and the
audit trail. Invitation cleanup can drop an unaccepted body. It cannot drop
an accepted obligation. The notification rows are not the authority record.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from osamp.errors import OsampError

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS people (
    person_id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acknowledgments (
    ack_id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    version TEXT NOT NULL,
    digest TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    evidence TEXT NOT NULL,
    superseded INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS delegations (
    delegation_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    task_class TEXT NOT NULL,
    max_budget INTEGER NOT NULL,
    remaining_accepts INTEGER NOT NULL,
    governance_digest TEXT NOT NULL,
    agreed_closure TEXT NOT NULL,
    mac TEXT NOT NULL,
    created_at TEXT NOT NULL,
    active INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS senders (
    sender_key_id TEXT PRIMARY KEY,
    permitted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS envelopes (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    sender_key_id TEXT NOT NULL,
    recipient_key_id TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    expires_at TEXT,
    payload_digest TEXT NOT NULL,
    body_json TEXT,
    delivery_state TEXT NOT NULL,
    role_state TEXT NOT NULL,
    quarantine_reason TEXT,
    data_class TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS obligations (
    obligation_id TEXT PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    work_id TEXT NOT NULL,
    table_id TEXT,
    role_id TEXT,
    contract_version TEXT NOT NULL,
    contract_digest TEXT NOT NULL,
    task_class TEXT NOT NULL,
    objective TEXT,
    objective_deleted INTEGER NOT NULL,
    limits_json TEXT NOT NULL,
    deadline TEXT,
    retention_deadline TEXT,
    human_id TEXT NOT NULL,
    deputy_id TEXT,
    authority_state TEXT NOT NULL,
    execution_state TEXT NOT NULL,
    budget_ceiling INTEGER NOT NULL,
    budget_spent INTEGER NOT NULL,
    budget_reserved INTEGER NOT NULL,
    attempt_count INTEGER NOT NULL,
    same_progress_count INTEGER NOT NULL,
    last_progress_digest TEXT,
    delegation_json TEXT NOT NULL,
    opinions_json TEXT NOT NULL,
    capsule_json TEXT NOT NULL,
    hold_json TEXT,
    hold_history_json TEXT NOT NULL,
    uncertain_effects_json TEXT NOT NULL,
    lease_expires_at TEXT,
    checkpoint_json TEXT,
    queue_cursor INTEGER NOT NULL,
    history_json TEXT NOT NULL,
    closure_json TEXT,
    checks_passed INTEGER NOT NULL,
    result_digest TEXT,
    contact_reachable INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    event_id TEXT,
    obligation_id TEXT,
    body_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    obligation_id TEXT NOT NULL,
    state TEXT NOT NULL,
    reminder_count INTEGER NOT NULL,
    body_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbound (
    outbound_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    next_hop TEXT NOT NULL,
    state TEXT NOT NULL,
    body_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
    block_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    reason TEXT NOT NULL,
    at TEXT NOT NULL,
    active INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref_id TEXT,
    body_json TEXT NOT NULL
);
"""


def _dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _loads(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


class Postbox:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path, timeout=5, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._fail_commits = 0
        self._in_tx = False

    def close(self) -> None:
        self.conn.close()

    def create(self) -> None:
        self.conn.executescript(SCHEMA)
        if self.get_meta("schema_version") is None:
            self.set_meta("schema_version", "1")
            self.set_meta("covenant_enabled", "1")
            self.set_meta("storage_used_bytes", "0")
            self.set_meta("storage_pressure", "0")
            self.set_meta("model_calls", "0")
            self.set_meta("tool_calls", "0")
            self.set_meta("relay_count", "0")

    def fail_next_commit(self) -> None:
        self._fail_commits += 1

    def begin(self) -> None:
        if self._in_tx:
            raise OsampError("transaction", "A save was already in progress.")
        self.conn.execute("BEGIN IMMEDIATE")
        self._in_tx = True

    def commit(self) -> None:
        if not self._in_tx:
            raise OsampError("transaction", "There is no save in progress.")
        if self._fail_commits:
            self._fail_commits -= 1
            raise OsampError(
                "commit_failed",
                "The record could not be saved, so nothing from this step was kept.",
            )
        self.conn.execute("COMMIT")
        self._in_tx = False

    def rollback(self) -> None:
        if self._in_tx:
            self.conn.execute("ROLLBACK")
            self._in_tx = False

    def transaction(self) -> "Tx":
        return Tx(self)

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return None if row is None else row["value"]

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def audit(self, kind: str, ref_id: str | None, body: dict, at: str) -> None:
        # Audit keeps identifiers and digests, not task prose.
        self.conn.execute(
            "INSERT INTO audit(at, kind, ref_id, body_json) VALUES(?, ?, ?, ?)",
            (at, kind, ref_id, _dumps(body)),
        )

    def list_audit(self, kind: str | None = None) -> list[dict]:
        if kind is None:
            rows = self.conn.execute("SELECT * FROM audit ORDER BY audit_id").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM audit WHERE kind=? ORDER BY audit_id", (kind,)
            ).fetchall()
        return [_audit_row(row) for row in rows]

    def insert_person(self, person_id: str, key_hash: str, at: str) -> None:
        existing = self.conn.execute(
            "SELECT key_hash FROM people WHERE person_id=?", (person_id,)
        ).fetchone()
        if existing is not None:
            raise OsampError(
                "person_exists",
                "That person is already registered. This draft does not rotate keys.",
            )
        self.conn.execute(
            "INSERT INTO people(person_id, key_hash, created_at) VALUES(?, ?, ?)",
            (person_id, key_hash, at),
        )

    def person_hash(self, person_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT key_hash FROM people WHERE person_id=?", (person_id,)
        ).fetchone()
        return None if row is None else row["key_hash"]

    def insert_ack(self, row: dict) -> None:
        self.conn.execute(
            """INSERT INTO acknowledgments
            (ack_id, operator_id, scope, version, digest, approved_at, evidence, superseded)
            VALUES(?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                row["ack_id"],
                row["operator_id"],
                row["scope"],
                row["version"],
                row["digest"],
                row["approved_at"],
                row["evidence"],
            ),
        )

    def supersede_acks(self, scope: str) -> None:
        self.conn.execute(
            "UPDATE acknowledgments SET superseded=1 WHERE scope=? AND superseded=0",
            (scope,),
        )

    def current_ack(self, scope: str, digest_value: str) -> dict | None:
        row = self.conn.execute(
            """SELECT * FROM acknowledgments
            WHERE scope=? AND digest=? AND superseded=0
            ORDER BY approved_at DESC LIMIT 1""",
            (scope, digest_value),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def insert_delegation(self, row: dict) -> None:
        self.conn.execute(
            """INSERT INTO delegations
            (delegation_id, person_id, task_class, max_budget, remaining_accepts,
             governance_digest, agreed_closure, mac, created_at, active)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                row["delegation_id"],
                row["person_id"],
                row["task_class"],
                row["max_budget"],
                row["remaining_accepts"],
                row["governance_digest"],
                row.get("agreed_closure", "hold"),
                row["mac"],
                row["created_at"],
            ),
        )

    def find_delegation(self, task_class: str, digest_value: str) -> dict | None:
        row = self.conn.execute(
            """SELECT * FROM delegations
            WHERE task_class=? AND governance_digest=? AND active=1 AND remaining_accepts>0
            ORDER BY created_at DESC LIMIT 1""",
            (task_class, digest_value),
        ).fetchone()
        return None if row is None else dict(row)

    def decrement_delegation(self, delegation_id: str) -> None:
        cur = self.conn.execute(
            """UPDATE delegations
            SET remaining_accepts=remaining_accepts-1
            WHERE delegation_id=? AND remaining_accepts>0""",
            (delegation_id,),
        )
        if cur.rowcount != 1:
            raise OsampError(
                "delegation_spent",
                "The human permission to accept this kind of work is used up.",
            )

    def permit_sender(self, sender_key_id: str, at: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO senders(sender_key_id, permitted_at) VALUES(?, ?)",
            (sender_key_id, at),
        )

    def sender_known(self, sender_key_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM senders WHERE sender_key_id=?", (sender_key_id,)
        ).fetchone()
        return row is not None

    def list_senders(self) -> list[str]:
        rows = self.conn.execute("SELECT sender_key_id FROM senders ORDER BY sender_key_id").fetchall()
        return [row["sender_key_id"] for row in rows]

    def get_envelope(self, event_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM envelopes WHERE event_id=?", (event_id,)).fetchone()
        return None if row is None else _envelope(row)

    def insert_envelope(self, row: dict) -> None:
        self.conn.execute(
            """INSERT INTO envelopes
            (event_id, event_type, sender_key_id, recipient_key_id, sent_at, expires_at,
             payload_digest, body_json, delivery_state, role_state, quarantine_reason,
             data_class, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["event_id"],
                row["event_type"],
                row["sender_key_id"],
                row["recipient_key_id"],
                row["sent_at"],
                row.get("expires_at"),
                row["payload_digest"],
                None if row.get("body") is None else _dumps(row["body"]),
                row["delivery_state"],
                row["role_state"],
                row.get("quarantine_reason"),
                row.get("data_class", "public-example"),
                row["created_at"],
                row["updated_at"],
            ),
        )

    def update_envelope(self, event_id: str, **fields: Any) -> None:
        mapping = {
            "delivery_state": "delivery_state",
            "role_state": "role_state",
            "quarantine_reason": "quarantine_reason",
            "updated_at": "updated_at",
            "expires_at": "expires_at",
        }
        sets = []
        values: list[Any] = []
        for key, column in mapping.items():
            if key in fields:
                sets.append(f"{column}=?")
                values.append(fields[key])
        if "body" in fields:
            sets.append("body_json=?")
            values.append(None if fields["body"] is None else _dumps(fields["body"]))
        if not sets:
            return
        values.append(event_id)
        self.conn.execute(f"UPDATE envelopes SET {', '.join(sets)} WHERE event_id=?", values)

    def insert_obligation(self, row: dict) -> None:
        self.conn.execute(
            """INSERT INTO obligations (
            obligation_id, event_id, work_id, table_id, role_id, contract_version,
            contract_digest, task_class, objective, objective_deleted, limits_json,
            deadline, retention_deadline, human_id, deputy_id, authority_state,
            execution_state, budget_ceiling, budget_spent, budget_reserved, attempt_count,
            same_progress_count, last_progress_digest, delegation_json, opinions_json,
            capsule_json, hold_json, hold_history_json, uncertain_effects_json,
            lease_expires_at, checkpoint_json, queue_cursor, history_json, closure_json,
            checks_passed, result_digest, contact_reachable, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["obligation_id"],
                row["event_id"],
                row["work_id"],
                row.get("table_id"),
                row.get("role_id"),
                row["contract_version"],
                row["contract_digest"],
                row["task_class"],
                row.get("objective"),
                1 if row.get("objective_deleted") else 0,
                _dumps(row.get("limits", {})),
                row.get("deadline"),
                row.get("retention_deadline"),
                row["human_id"],
                row.get("deputy_id"),
                row["authority_state"],
                row["execution_state"],
                row["budget_ceiling"],
                row["budget_spent"],
                row["budget_reserved"],
                row["attempt_count"],
                row["same_progress_count"],
                row.get("last_progress_digest"),
                _dumps(row.get("delegation", [])),
                _dumps(row.get("opinions", [])),
                _dumps(row["capsule"]),
                None if row.get("hold") is None else _dumps(row["hold"]),
                _dumps(row.get("hold_history", [])),
                _dumps(row.get("uncertain_effects", [])),
                row.get("lease_expires_at"),
                None if row.get("checkpoint") is None else _dumps(row["checkpoint"]),
                row.get("queue_cursor", 0),
                _dumps(row.get("history", [])),
                None if row.get("closure") is None else _dumps(row["closure"]),
                1 if row.get("checks_passed") else 0,
                row.get("result_digest"),
                1 if row.get("contact_reachable", True) else 0,
                row["created_at"],
                row["updated_at"],
            ),
        )

    def get_obligation(self, obligation_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM obligations WHERE obligation_id=?", (obligation_id,)
        ).fetchone()
        return None if row is None else _obligation(row)

    def obligation_by_event(self, event_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM obligations WHERE event_id=?", (event_id,)
        ).fetchone()
        return None if row is None else _obligation(row)

    def count_open_obligations(self) -> int:
        row = self.conn.execute(
            """SELECT COUNT(*) AS n FROM obligations
            WHERE authority_state='accepted'
            AND execution_state NOT IN ('completed', 'closed', 'stopped')"""
        ).fetchone()
        return int(row["n"])

    def update_obligation(self, obligation_id: str, **fields: Any) -> None:
        json_fields = {
            "limits": "limits_json",
            "delegation": "delegation_json",
            "opinions": "opinions_json",
            "capsule": "capsule_json",
            "hold": "hold_json",
            "hold_history": "hold_history_json",
            "uncertain_effects": "uncertain_effects_json",
            "checkpoint": "checkpoint_json",
            "history": "history_json",
            "closure": "closure_json",
        }
        plain = {
            "objective": "objective",
            "objective_deleted": "objective_deleted",
            "authority_state": "authority_state",
            "execution_state": "execution_state",
            "budget_ceiling": "budget_ceiling",
            "budget_spent": "budget_spent",
            "budget_reserved": "budget_reserved",
            "attempt_count": "attempt_count",
            "same_progress_count": "same_progress_count",
            "last_progress_digest": "last_progress_digest",
            "lease_expires_at": "lease_expires_at",
            "queue_cursor": "queue_cursor",
            "checks_passed": "checks_passed",
            "result_digest": "result_digest",
            "contact_reachable": "contact_reachable",
            "updated_at": "updated_at",
            "deadline": "deadline",
            "retention_deadline": "retention_deadline",
        }
        sets = []
        values: list[Any] = []
        for key, column in plain.items():
            if key in fields:
                value = fields[key]
                if key in {"objective_deleted", "checks_passed", "contact_reachable"}:
                    value = 1 if value else 0
                sets.append(f"{column}=?")
                values.append(value)
        for key, column in json_fields.items():
            if key in fields:
                value = fields[key]
                sets.append(f"{column}=?")
                values.append(None if value is None else _dumps(value))
        if not sets:
            return
        values.append(obligation_id)
        self.conn.execute(
            f"UPDATE obligations SET {', '.join(sets)} WHERE obligation_id=?", values
        )

    def list_obligations(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM obligations ORDER BY created_at").fetchall()
        return [_obligation(row) for row in rows]

    def envelopes_due(self, now: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM envelopes
            WHERE expires_at IS NOT NULL AND expires_at<=?
            AND delivery_state!='expired'""",
            (now,),
        ).fetchall()
        return [_envelope(row) for row in rows]

    def insert_receipt(self, row: dict) -> None:
        self.conn.execute(
            """INSERT INTO receipts(receipt_id, kind, event_id, obligation_id, body_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?)""",
            (
                row["receipt_id"],
                row["kind"],
                row.get("event_id"),
                row.get("obligation_id"),
                _dumps(row["body"]),
                row["created_at"],
            ),
        )

    def list_receipts(self, obligation_id: str | None = None) -> list[dict]:
        if obligation_id is None:
            rows = self.conn.execute("SELECT * FROM receipts ORDER BY created_at").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM receipts WHERE obligation_id=? ORDER BY created_at",
                (obligation_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["body"] = _loads(item.pop("body_json"))
            result.append(item)
        return result

    def insert_notification(self, row: dict) -> None:
        self.conn.execute(
            """INSERT INTO notifications
            (notification_id, obligation_id, state, reminder_count, body_json, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)""",
            (
                row["notification_id"],
                row["obligation_id"],
                row["state"],
                row["reminder_count"],
                _dumps(row["body"]),
                row["created_at"],
                row["updated_at"],
            ),
        )

    def update_notification(self, notification_id: str, **fields: Any) -> None:
        sets = []
        values: list[Any] = []
        if "state" in fields:
            sets.append("state=?")
            values.append(fields["state"])
        if "reminder_count" in fields:
            sets.append("reminder_count=?")
            values.append(fields["reminder_count"])
        if "body" in fields:
            sets.append("body_json=?")
            values.append(_dumps(fields["body"]))
        if "updated_at" in fields:
            sets.append("updated_at=?")
            values.append(fields["updated_at"])
        values.append(notification_id)
        self.conn.execute(
            f"UPDATE notifications SET {', '.join(sets)} WHERE notification_id=?", values
        )

    def notifications_for(self, obligation_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM notifications WHERE obligation_id=? ORDER BY created_at",
            (obligation_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["body"] = _loads(item.pop("body_json"))
            result.append(item)
        return result

    def insert_outbound(self, row: dict) -> None:
        self.conn.execute(
            """INSERT INTO outbound(outbound_id, event_id, next_hop, state, body_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?)""",
            (
                row["outbound_id"],
                row["event_id"],
                row["next_hop"],
                row["state"],
                _dumps(row["body"]),
                row["created_at"],
            ),
        )

    def list_outbound(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM outbound ORDER BY created_at").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["body"] = _loads(item.pop("body_json"))
            result.append(item)
        return result

    def insert_block(self, row: dict) -> None:
        self.conn.execute(
            """INSERT INTO blocks(block_id, scope, scope_ref, reason, at, active)
            VALUES(?, ?, ?, ?, ?, 1)""",
            (row["block_id"], row["scope"], row["scope_ref"], row["reason"], row["at"]),
        )

    def active_blocks(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM blocks WHERE active=1").fetchall()
        return [dict(row) for row in rows]

    def storage_used(self) -> int:
        return int(self.get_meta("storage_used_bytes") or "0")

    def add_storage(self, nbytes: int) -> None:
        used = self.storage_used() + nbytes
        if used < 0:
            used = 0
        self.set_meta("storage_used_bytes", str(used))

    def quarantine_count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM envelopes WHERE quarantine_reason IS NOT NULL"
        ).fetchone()
        return int(row["n"])

    def tombstone_path(self) -> str:
        return self.path + ".tombstones"

    def append_tombstone(self, record: dict) -> None:
        with open(self.tombstone_path(), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def reapply_tombstones(self) -> None:
        path = self.tombstone_path()
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
        for line in lines:
            if not line.strip():
                continue
            record = json.loads(line)
            obligation = self.get_obligation(record.get("obligation_id", ""))
            if obligation is None:
                continue
            if record["kind"] == "spent" and obligation["budget_spent"] < int(record["spent"]):
                self.update_obligation(
                    obligation["obligation_id"],
                    budget_spent=int(record["spent"]),
                    updated_at=obligation["updated_at"],
                )
            elif record["kind"] == "revoked" and obligation["authority_state"] != "revoked":
                execution = obligation["execution_state"]
                if execution not in {"closed", "completed"}:
                    execution = "held"
                self.update_obligation(
                    obligation["obligation_id"],
                    authority_state="revoked",
                    execution_state=execution,
                    updated_at=obligation["updated_at"],
                )
            elif record["kind"] == "closed" and obligation["execution_state"] != "closed":
                self.update_obligation(
                    obligation["obligation_id"],
                    authority_state="closed",
                    execution_state="closed",
                    objective=None,
                    objective_deleted=True,
                    updated_at=obligation["updated_at"],
                )

    def trim_quarantine(self, keep: int) -> None:
        rows = self.conn.execute(
            """SELECT event_id FROM envelopes
            WHERE quarantine_reason IS NOT NULL
            ORDER BY created_at DESC"""
        ).fetchall()
        for row in rows[keep:]:
            self.conn.execute("DELETE FROM envelopes WHERE event_id=?", (row["event_id"],))


def _envelope(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["body"] = _loads(item.pop("body_json"))
    return item


def _obligation(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["objective_deleted"] = bool(item["objective_deleted"])
    item["checks_passed"] = bool(item["checks_passed"])
    item["contact_reachable"] = bool(item["contact_reachable"])
    item["limits"] = _loads(item.pop("limits_json")) or {}
    item["delegation"] = _loads(item.pop("delegation_json")) or []
    item["opinions"] = _loads(item.pop("opinions_json")) or []
    item["capsule"] = _loads(item.pop("capsule_json")) or {}
    item["hold"] = _loads(item.pop("hold_json"))
    item["hold_history"] = _loads(item.pop("hold_history_json")) or []
    item["uncertain_effects"] = _loads(item.pop("uncertain_effects_json")) or []
    item["checkpoint"] = _loads(item.pop("checkpoint_json"))
    item["history"] = _loads(item.pop("history_json")) or []
    item["closure"] = _loads(item.pop("closure_json"))
    return item


def _audit_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["body"] = _loads(item.pop("body_json"))
    return item


class Tx:
    def __init__(self, box: Postbox):
        self.box = box

    def __enter__(self) -> Postbox:
        self.box.begin()
        return self.box

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            try:
                self.box.commit()
            except Exception:
                self.box.rollback()
                raise
        else:
            self.box.rollback()
        return False
