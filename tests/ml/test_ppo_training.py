from __future__ import annotations

from pathlib import Path

from rescue_swarm.ml.ppo import (
    STAGE_CONFIG,
    load_policy_checkpoint,
    propose_action_from_policy,
    train_swarm_policy,
)


def test_swarm_policy_training_runs_optimizer_steps_and_logs_release_metrics(
    tmp_path: Path,
) -> None:
    result = train_swarm_policy(stage="smoke", artifact_root=tmp_path, git_sha="abc123")

    assert result["proof_type"] == "rl_training"
    assert result["trained_result"] is True
    payload = result["payload"]
    assert payload["algorithm"] == "shared-linear-masked-ppo"
    assert payload["optimizer_steps"] > 0
    assert payload["ppo_constraints"]["clip_param"] == 0.2
    assert payload["ppo_constraints"]["normalize_advantages"] is True
    assert payload["ppo_constraints"]["entropy_bonus"] == 0.01
    assert payload["ppo_constraints"]["grad_clip"] == 0.5
    assert payload["candidate"]["episodes"] == 4
    assert payload["baseline"]["episodes"] == 4
    assert payload["release_gate"]["safety_failures"] == 0
    assert Path(payload["checkpoint_path"]).exists()


def test_policy_checkpoint_proposes_masked_action(tmp_path: Path) -> None:
    result = train_swarm_policy(stage="smoke", artifact_root=tmp_path, git_sha="abc123")
    policy = load_policy_checkpoint(Path(result["payload"]["checkpoint_path"]))
    proposal = propose_action_from_policy(
        policy,
        {
            "position": (0, 0, 1),
            "battery": 95,
            "known_victims": 1,
            "flood_cells": 4,
            "rescued_victims": 0,
            "link_quality": 0.9,
            "action_mask": [1, 1, 0, 1, 1, 1],
        },
    )

    assert proposal["action"] != "aid_drop"
    assert 0 <= proposal["confidence"] <= 1
    assert len(proposal["coordination_message"]) == 3


def test_smoke_stage_keeps_deadline_mvp_training_small() -> None:
    assert STAGE_CONFIG["smoke"].episodes <= 48
    assert STAGE_CONFIG["smoke"].num_drones == 4
