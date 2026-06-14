from __future__ import annotations

import json

from rescue_swarm.ml import (
    build_data_prep_proof,
    build_fallback_policy_proposal,
    build_perception_training_proof,
    build_release_gate_proof,
    build_rl_training_proof,
)


def test_data_and_perception_proofs_are_json_serializable() -> None:
    data = json.loads(build_data_prep_proof(git_sha="abc123").to_json())
    perception = json.loads(build_perception_training_proof(git_sha="abc123").to_json())

    assert data["simulation_only"] is True
    assert data["trained_result"] is False
    assert perception["trained_result"] is True
    assert perception["payload"]["model_revision"] == "2b5ac0a"


def test_rl_training_proof_beats_baseline_without_safety_failures() -> None:
    proof = build_rl_training_proof(git_sha="abc123", seeds=(11, 17, 23, 29))

    gate = proof.payload["release_gate"]
    assert proof.trained_result is True
    assert gate["passed"] is True
    assert gate["safety_failures"] == 0
    assert gate["comparison"]["candidate_mean"] > gate["comparison"]["baseline_mean"]


def test_release_gate_proof_contains_active_model_manifest() -> None:
    proof = build_release_gate_proof(git_sha="abc123")

    assert proof.payload["passed"] is True
    assert proof.payload["active_models"]["policy_alias"] == "production"
    assert proof.payload["active_models"]["simulation_only"] is True


def test_fallback_policy_proposal_stays_simulation_only() -> None:
    proposal = build_fallback_policy_proposal("mission-1", git_sha="abc123")

    assert proposal["simulation_only"] is True
    assert proposal["proposal"]["action"] == "search"
    assert proposal["safety"]["shield_status"] is True
