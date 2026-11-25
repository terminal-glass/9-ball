"""Names for the three kinds of state.

Delivery, authority, and execution are stored separately. One of them
changing must not be read as a change to the others.
"""

from __future__ import annotations

DELIVERY_STATES = (
    "draft",
    "queued",
    "sending",
    "delivered",
    "failed",
    "expired",
)

AUTHORITY_STATES = (
    "proposed",
    "offered",
    "accepted",
    "revoked",
    "expired",
    "closed",
)

EXECUTION_STATES = (
    "absent",
    "ready",
    "working",
    "paused",
    "held",
    "review",
    "stop_pending",
    "stopped",
    "result_submitted",
    "completed",
    "uncertain",
    "closed",
)

# Holds that must not resume on a timer or an unsigned reply.
HUMAN_HOLD_REASONS = frozenset(
    {
        "copied_source",
        "circular_delegation",
        "conflicting_evidence",
        "no_progress",
        "missing_checkpoint",
        "capacity_pressure",
        "timeout",
        "integrity_failure",
        "compromised_authority",
        "lease_expired",
        "retention",
        "remote_stop",
    }
)

OFFER_EVENTS = frozenset(
    {
        "WORK_OFFER",
        "TABLE_ROLE_OFFER",
        "CORRIDOR_STAGE_OFFER",
        "PEER_INVITE",
        "HELP_REQUEST",
    }
)

KNOWN_EVENT_TYPES = frozenset(
    {
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
)

CAPSULE_KEYS = (
    "work_id",
    "table_id",
    "role_id",
    "event_id",
    "contract_version",
    "contract_digest",
    "objective",
    "limits",
    "deadline",
    "human_id",
    "deputy_id",
    "completed_actions",
    "evidence_digests",
    "external_effects",
    "blocker",
    "uncertainty",
    "checkpoint_id",
    "budget_ceiling",
    "budget_spent",
    "budget_reserved",
    "lease_expires_at",
    "stop_state",
    "pending_deliveries",
    "human_decision_requested",
    "permitted_next_steps",
    "retention_deadline",
    "archive_rule",
    "access",
)
