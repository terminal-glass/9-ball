"""Self-Governance Covenant: which moves are allowed.

These checks are ordinary code. They do not ask a language model whether
work should stop.
"""

from __future__ import annotations

from osamp.clock import parse_time
from osamp.errors import OsampError
from osamp.records import HUMAN_HOLD_REASONS


def _covered(obligation: dict, blocks: list[dict]) -> str | None:
    refs = {
        "task": obligation["obligation_id"],
        "work": obligation["work_id"],
        "table": obligation.get("table_id") or "",
        "node": "node",
    }
    for block in blocks:
        if not block["active"]:
            continue
        if block["scope"] == "node" and block["scope_ref"] == "node":
            return block["reason"]
        if refs.get(block["scope"]) and refs[block["scope"]] == block["scope_ref"]:
            return block["reason"]
    return None


def play_blockers(obligation: dict, ctx: dict) -> list[str]:
    """Reasons PLAY must refuse. Empty means the gates currently allow a start."""
    reasons: list[str] = []
    if not ctx["covenant_enabled"]:
        reasons.append("Mandatory controls are off, so this copy cannot claim conformance or start work.")
    if ctx["ack"] is None:
        reasons.append("The operator has not acknowledged the current safeguards.")
    if obligation["authority_state"] != "accepted":
        reasons.append("This role is not accepted.")
    execution = obligation["execution_state"]
    if execution in {
        "held",
        "review",
        "stop_pending",
        "stopped",
        "uncertain",
        "closed",
        "completed",
        "absent",
        "result_submitted",
    }:
        reasons.append(f"Execution is {execution} and cannot start.")
    hold = obligation.get("hold")
    if hold and hold.get("reason") in HUMAN_HOLD_REASONS and not hold.get("resolved"):
        reasons.append("A human decision is still required before this hold can clear.")
    if obligation["budget_spent"] >= obligation["budget_ceiling"]:
        reasons.append("The budget is spent. A reply does not renew it.")
    if obligation.get("lease_expires_at") and execution == "working":
        if parse_time(ctx["now"]) > parse_time(obligation["lease_expires_at"]):
            reasons.append("The execution lease has expired.")
    covered = _covered(obligation, ctx["blocks"])
    if covered:
        reasons.append(f"Authority is blocked: {covered}")
    if obligation.get("checkpoint_required") and not obligation.get("checkpoint"):
        reasons.append("A checkpoint is required and missing.")
    if obligation.get("checkpoint") and obligation["checkpoint"].get("broken"):
        reasons.append("The checkpoint does not match its check value.")
    if ctx.get("storage_pressure") and execution != "working":
        reasons.append("Storage pressure blocks starting more work.")
    return reasons


def require_fast_forward(obligation: dict, to_cursor: int) -> None:
    if obligation["authority_state"] != "accepted":
        raise OsampError(
            "fast_forward_refused",
            "Fast-forward cannot accept work or skip consent.",
        )
    if obligation.get("hold") and not obligation["hold"].get("resolved"):
        raise OsampError(
            "fast_forward_refused",
            "Fast-forward cannot skip a hold.",
        )
    if obligation["execution_state"] in {
        "held",
        "review",
        "stop_pending",
        "stopped",
        "uncertain",
        "closed",
    }:
        raise OsampError(
            "fast_forward_refused",
            "Fast-forward cannot skip a hold, a review, or a stop.",
        )
    if to_cursor != obligation["queue_cursor"] + 1:
        raise OsampError(
            "fast_forward_refused",
            "Fast-forward can only move the waiting cursor by one already-permitted step.",
        )


def rewind_updates(obligation: dict, checkpoint_id: str, compensation: str) -> dict:
    checkpoint = obligation.get("checkpoint")
    if not checkpoint or checkpoint.get("checkpoint_id") != checkpoint_id:
        raise OsampError(
            "rewind_refused",
            "Rewind needs a checkpoint this node already verified.",
        )
    if obligation.get("hold") and not obligation["hold"].get("resolved"):
        raise OsampError(
            "rewind_refused",
            "Rewind cannot clear a hold or erase the record of it.",
        )
    history = list(obligation["history"])
    history.append(
        {
            "kind": "rewind",
            "checkpoint_id": checkpoint_id,
            "compensation": compensation,
            "attempt_count_kept": obligation["attempt_count"],
            "budget_spent_kept": obligation["budget_spent"],
            "prior_execution": obligation["execution_state"],
        }
    )
    # Counters never move backwards. External effects stay recorded.
    return {
        "history": history,
        "execution_state": "ready" if obligation["execution_state"] == "working" else obligation["execution_state"],
        "queue_cursor": checkpoint.get("queue_cursor", obligation["queue_cursor"]),
    }
