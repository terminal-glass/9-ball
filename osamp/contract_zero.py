"""Contract Zero rules: detect trouble, keep a recovery capsule, and wait.

Nothing in this module calls a language model.
"""

from __future__ import annotations

from typing import Any

from osamp.errors import OsampError
from osamp.plain import PERMITTED_HUMAN_STEPS
from osamp.records import CAPSULE_KEYS


def build_capsule(data: dict[str, Any]) -> dict[str, Any]:
    if "transcript" in data or "chain_of_thought" in data:
        raise OsampError(
            "capsule_refused",
            "The recovery record cannot keep a transcript or private reasoning.",
        )
    missing = [key for key in CAPSULE_KEYS if key not in data]
    if missing:
        raise OsampError(
            "capsule_incomplete",
            "The recovery record is missing: " + ", ".join(missing),
        )
    return {key: data[key] for key in CAPSULE_KEYS}


def minimal_closure_capsule(capsule: dict[str, Any], disposition: str) -> dict[str, Any]:
    kept = {
        "work_id": capsule.get("work_id"),
        "table_id": capsule.get("table_id"),
        "role_id": capsule.get("role_id"),
        "event_id": capsule.get("event_id"),
        "contract_version": capsule.get("contract_version"),
        "contract_digest": capsule.get("contract_digest"),
        "human_id": capsule.get("human_id"),
        "disposition": disposition,
        "objective": None,
    }
    return kept


def assess_task(profile, task_class: str, scope: str, subtask_id: str | None, measurement: dict | None) -> dict:
    """Use the published local measurement. This is not a cross-vendor ranking."""
    if not measurement or "elapsed_ms" not in measurement or not measurement.get("measured_at"):
        return {
            "fit": "decline",
            "subtask_id": None,
            "plain": "No measured sample is published, so the fit is unknown.",
        }
    matches = (
        task_class == measurement.get("task_class")
        and scope == measurement.get("scope")
        and subtask_id
        and subtask_id == measurement.get("subtask_id")
        and task_class in profile.allowed_task_classes
    )
    if matches:
        return {
            "fit": "bounded_subtask",
            "subtask_id": subtask_id,
            "plain": (
                f"The measured sample covers the bounded step {subtask_id}. "
                f"It took {measurement['elapsed_ms']} ms on {measurement['measured_at']}."
            ),
        }
    return {
        "fit": "decline",
        "subtask_id": None,
        "plain": "The offer is outside the measured sample, or it is not that bounded step.",
    }


def note_attempt(obligation: dict, progress_digest: str | None, limits: dict) -> dict:
    attempt_count = obligation["attempt_count"] + 1
    last = obligation.get("last_progress_digest")
    if progress_digest and progress_digest != last:
        same = 0
        last = progress_digest
        progressed = True
    else:
        same = obligation["same_progress_count"] + 1
        progressed = False
    updates = {
        "attempt_count": attempt_count,
        "same_progress_count": same,
        "last_progress_digest": last,
        "progressed": progressed,
    }
    if attempt_count >= limits["max_attempts"] or same >= limits["max_same_progress"]:
        updates["hold_reason"] = "no_progress"
    return updates


def note_delegation(
    obligation: dict,
    to_peer: str,
    stage_id: str,
    stage_index: int,
    child_budget: int,
    limits: dict,
) -> dict:
    path = list(obligation["delegation"])
    pair = {"to_peer": to_peer, "stage_id": stage_id, "stage_index": stage_index}
    seen = {(item["to_peer"], item["stage_id"]) for item in path}
    indexes = [item.get("stage_index", 0) for item in path]
    if (to_peer, stage_id) in seen or (indexes and stage_index < max(indexes)):
        return {"hold_reason": "circular_delegation", "delegation": path}
    if len(path) + 1 > limits["max_delegation_depth"]:
        return {"hold_reason": "circular_delegation", "delegation": path}
    remaining = (
        obligation["budget_ceiling"]
        - obligation["budget_spent"]
        - obligation["budget_reserved"]
    )
    if child_budget > remaining or child_budget > limits["max_delegation_budget"]:
        return {"hold_reason": "no_progress", "delegation": path, "budget_refused": True}
    path.append(pair)
    return {
        "delegation": path,
        "budget_reserved": obligation["budget_reserved"] + child_budget,
    }


def copied_source(opinions: list[dict]) -> bool:
    agreeing = [item for item in opinions if item.get("agrees")]
    if len(agreeing) < 2:
        return False
    lineages = {item.get("lineage_id") for item in agreeing}
    return len(lineages) == 1


def independent_opinion(opinions: list[dict]) -> bool:
    """An independent check uses a different source lineage and says so."""
    lineages = [item.get("lineage_id") for item in opinions if item.get("agrees")]
    if len(set(lineages)) < 2:
        return False
    return any(item.get("independent") and item.get("agrees") for item in opinions)


def check_decision_shape(decision: dict, obligation: dict) -> None:
    required = ("decision_id", "obligation_id", "hold_id", "operator_id", "kind", "scope")
    missing = [key for key in required if not decision.get(key)]
    if missing:
        raise OsampError(
            "decision_incomplete",
            "The human decision is missing: " + ", ".join(missing),
        )
    if decision["obligation_id"] != obligation["obligation_id"]:
        raise OsampError("decision_mismatch", "That decision is for different work.")
    hold = obligation.get("hold") or {}
    if decision["hold_id"] != hold.get("hold_id"):
        raise OsampError(
            "stale_decision",
            "That decision does not match the current hold.",
        )
    if decision["operator_id"] not in {obligation["human_id"], obligation.get("deputy_id")}:
        raise OsampError(
            "not_designated_human",
            "Only the designated person or their named deputy can resolve this hold.",
        )
    if decision["kind"] not in {
        "leave_held",
        "terminate",
        "clarify",
        "approve_same_step",
        "amend_budget",
        "accept_handoff",
    }:
        raise OsampError("decision_unknown", "That decision is not one of the permitted choices.")
    if decision["kind"] in {"clarify", "approve_same_step"} and decision["kind"] not in PERMITTED_HUMAN_STEPS:
        raise OsampError("decision_refused", "That step is not permitted for this hold.")
    if decision["kind"] == "approve_same_step":
        allowed = set((obligation.get("hold") or {}).get("permitted_steps") or [])
        step_id = decision.get("step_id")
        if step_id != "approve_same_step" or step_id not in allowed:
            raise OsampError(
                "decision_scope",
                "The approval must name the same step already on this hold. It cannot widen the work.",
            )
    if "continue" in str(decision.get("statement", "")).lower() and decision["kind"] not in {
        "approve_same_step",
        "clarify",
        "terminate",
        "leave_held",
        "amend_budget",
        "accept_handoff",
    }:
        raise OsampError("not_authority", "A sentence is not a decision.")
