from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from rescue_swarm.contracts import CodexProposal, WorldStateSnapshot

ALLOWED_PROPOSAL_TYPES = frozenset(
    {"mission_option", "scenario_test", "config_patch", "reward_patch"}
)
FORBIDDEN_CHANGE_KEYS = frozenset(
    {"execute_action", "actuator_command", "deploy_model", "update_weights", "bypass_safety"}
)


class ProposalValidationError(ValueError):
    """Raised when advisory output attempts to cross an authority boundary."""


@dataclass(frozen=True, slots=True)
class MissionCopilot:
    """Offline deterministic Mission Copilot fallback."""

    operator_id: str = "mission-copilot-offline"

    def propose(self, snapshot: WorldStateSnapshot) -> CodexProposal:
        stale_sources = [
            source for source, age in snapshot.data_freshness.items() if age > 30
        ]
        summary = "Hold risky actions and prioritize verification."
        change = {
            "operator_option": "review_assignments",
            "stale_sources": stale_sources,
            "requires_safety_shield": True,
        }
        if snapshot.victim_hypotheses:
            summary = "Prioritize confirming victim hypotheses before aid drops."
            change["operator_option"] = "confirm_victims_before_drop"
        return validate_proposal(
            CodexProposal(
                mission_id=snapshot.mission_id,
                proposal_type="mission_option",
                summary=summary,
                rationale="Generated from structured world state; no actuator access.",
                proposed_change=change,
                evidence_refs=(f"world-sequence:{snapshot.sequence}",),
            )
        )


@dataclass(frozen=True, slots=True)
class EvalEngineer:
    """Turns evaluation gaps into regression-test proposals."""

    def propose_regression(
        self,
        *,
        mission_id: UUID,
        evaluation_summary: dict[str, Any],
    ) -> CodexProposal:
        weak_metric = evaluation_summary.get("weakest_metric", "communication_continuity")
        return validate_proposal(
            CodexProposal(
                mission_id=mission_id,
                proposal_type="scenario_test",
                summary=f"Add regression coverage for {weak_metric}.",
                rationale="Evidence proposal only; implementation requires human approval.",
                proposed_change={
                    "scenario_family": f"stress_{weak_metric}",
                    "locked_seed": int(evaluation_summary.get("suggested_seed", 2026)),
                    "requires_safety_shield": True,
                },
                evidence_refs=tuple(evaluation_summary.get("evidence_refs", ())),
            )
        )


def validate_proposal(proposal: CodexProposal) -> CodexProposal:
    if proposal.proposal_type not in ALLOWED_PROPOSAL_TYPES:
        raise ProposalValidationError(f"proposal_type {proposal.proposal_type!r} is not allowed")
    if not proposal.requires_human_approval:
        raise ProposalValidationError("Codex proposals must require human approval")
    forbidden = FORBIDDEN_CHANGE_KEYS.intersection(proposal.proposed_change)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise ProposalValidationError(f"proposal attempts forbidden authority: {joined}")
    return proposal

