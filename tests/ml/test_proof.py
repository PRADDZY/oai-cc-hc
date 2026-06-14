from __future__ import annotations

import json
from pathlib import Path

from rescue_swarm.ml import (
    build_fallback_policy_proposal,
    build_release_gate_from_files,
    data_manifest_to_proof,
    proof_from_training_result,
)


def test_data_manifest_proof_is_json_serializable() -> None:
    data = json.loads(
        data_manifest_to_proof(
            manifest={
                "dataset": "Sen1Floods11",
                "dataset_version": "v1.1",
                "dataset_source": "gs://sen1floods11 via public HTTPS",
                "dataset_hash": "abc",
                "split_policy": "official",
                "records_indexed": 4,
                "limits": {"train": 2, "valid": 1, "test": 1},
                "manifest_path": "/tmp/manifest.json",
            },
            stage="smoke",
            git_sha="abc123",
        ).to_json()
    )

    assert data["simulation_only"] is True
    assert data["trained_result"] is False
    assert data["payload"]["dataset"] == "Sen1Floods11"


def test_training_result_wraps_as_proof_bundle() -> None:
    proof = proof_from_training_result(
        {
            "proof_type": "perception_training",
            "run_id": "run-1",
            "generated_at": "2026-06-14T00:00:00+00:00",
            "git_sha": "abc123",
            "simulation_only": True,
            "trained_result": True,
            "payload": {"artifact_id": "artifact-1"},
        }
    )

    assert proof.trained_result is True
    assert proof.payload["artifact_id"] == "artifact-1"


def test_release_gate_proof_contains_active_model_manifest(tmp_path: Path) -> None:
    (tmp_path / "data_prep_smoke.json").write_text(
        json.dumps(
            {
                "proof_type": "data_prep",
                "run_id": "data",
                "simulation_only": True,
                "trained_result": False,
                "payload": {"dataset": "Sen1Floods11"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "perception_eval_smoke.json").write_text(
        json.dumps(
            {
                "proof_type": "perception_training",
                "run_id": "perception",
                "simulation_only": True,
                "trained_result": True,
                "payload": {
                    "artifact_id": "perception-a",
                    "event_held_out_iou": 0.5,
                    "event_held_out_f1": 0.66,
                    "calibration_ece": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "rl_eval_smoke.json").write_text(
        json.dumps(
            {
                "proof_type": "rl_training",
                "run_id": "rl",
                "simulation_only": True,
                "trained_result": True,
                "payload": {
                    "artifact_id": "policy-a",
                    "candidate": {"lives_aided_safely_mean": 2.0},
                    "baseline": {"lives_aided_safely_mean": 0.0},
                    "release_gate": {
                        "passed": True,
                        "reasons": [],
                        "safety_failures": 0,
                        "comparison": {"mean_difference": 2.0},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    proof = build_release_gate_from_files(stage="smoke", git_sha="abc123", run_path=tmp_path)

    assert proof.payload["passed"] is True
    assert proof.payload["active_models"]["policy_alias"] == "production"
    assert proof.payload["active_models"]["simulation_only"] is True


def test_fallback_policy_proposal_stays_simulation_only() -> None:
    proposal = build_fallback_policy_proposal("mission-1", git_sha="abc123")

    assert proposal["simulation_only"] is True
    assert proposal["proposal"]["action"] == "search"
    assert proposal["safety"]["shield_status"] is True
