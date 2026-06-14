from datetime import UTC, datetime
from uuid import UUID

import pytest

from rescue_swarm.advisors import EvalEngineer, MissionCopilot, ProposalValidationError
from rescue_swarm.advisors.services import validate_proposal
from rescue_swarm.contracts import CodexProposal, WorldStateSnapshot

MISSION_ID = UUID("32fd0264-68b2-43c6-813a-c1a6f2109878")


def snapshot() -> WorldStateSnapshot:
    return WorldStateSnapshot(
        mission_id=MISSION_ID,
        sequence=3,
        generated_at=datetime.now(UTC),
        victim_hypotheses=({"id": "v1", "confidence": 0.62},),
        data_freshness={"telemetry": 1.0, "sentinel": 7200.0},
        confidence=0.74,
    )


def test_mission_copilot_is_advisory_and_requires_human_approval() -> None:
    proposal = MissionCopilot().propose(snapshot())

    assert proposal.proposal_type == "mission_option"
    assert proposal.requires_human_approval is True
    assert proposal.model_generated is True
    assert "execute_action" not in proposal.proposed_change


def test_eval_engineer_proposes_regression_scenario_not_runtime_action() -> None:
    proposal = EvalEngineer().propose_regression(
        mission_id=MISSION_ID,
        evaluation_summary={"weakest_metric": "link_loss", "suggested_seed": 99},
    )

    assert proposal.proposal_type == "scenario_test"
    assert proposal.proposed_change["locked_seed"] == 99
    assert proposal.requires_human_approval is True


def test_malformed_or_actuating_proposals_are_rejected() -> None:
    with pytest.raises(ProposalValidationError, match="forbidden authority"):
        validate_proposal(
            CodexProposal(
                mission_id=MISSION_ID,
                proposal_type="mission_option",
                summary="bad",
                rationale="bad",
                proposed_change={"execute_action": "aid_drop"},
            )
        )

    with pytest.raises(ProposalValidationError, match="human approval"):
        validate_proposal(
            CodexProposal(
                mission_id=MISSION_ID,
                proposal_type="scenario_test",
                summary="bad",
                rationale="bad",
                proposed_change={"scenario": "x"},
                requires_human_approval=False,
            )
        )

