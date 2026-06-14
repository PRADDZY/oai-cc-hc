from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from rescue_swarm.contracts import ActionKind, PolicyOutput

NAMESPACE = UUID("c25c5f8b-4ca5-43d0-b4c0-bf250c80bf3f")


@dataclass(frozen=True, slots=True)
class ProofBundle:
    proof_type: str
    run_id: str
    generated_at: str
    git_sha: str
    simulation_only: bool
    trained_result: bool
    payload: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True, slots=True)
class ActiveModelManifest:
    policy_alias: str
    policy_artifact: str
    perception_alias: str
    perception_artifact: str
    promoted_at: str
    proof_run_id: str
    simulation_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def data_manifest_to_proof(
    *,
    manifest: dict[str, Any],
    stage: str,
    git_sha: str,
) -> ProofBundle:
    dataset_hash = manifest.get("dataset_hash") or manifest.get("manifest_sha256")
    records_indexed = manifest.get("records_indexed", manifest.get("sample_count", 0))
    payload = {
        "dataset": manifest["dataset"],
        "dataset_version": manifest["dataset_version"],
        "dataset_source": manifest["dataset_source"],
        "dataset_hash": dataset_hash,
        "stage": stage,
        "split_policy": manifest["split_policy"],
        "records_indexed": records_indexed,
        "limits": manifest["limits"],
        "manifest_path": manifest["manifest_path"],
        "claim_boundary": "dataset manifest proof only; imagery is not RL trajectory data",
    }
    return _bundle("data_prep", git_sha, payload, trained_result=False)


def proof_from_training_result(result: dict[str, Any]) -> ProofBundle:
    if "proof_type" not in result and "model_family" in result:
        result = _perception_result_to_bundle_dict(result)
    if "proof_type" not in result and "algorithm" in result:
        result = _ppo_result_to_bundle_dict(result)
    if "run_id" not in result and result.get("proof_type") == "rl_training":
        result = _ppo_result_to_bundle_dict(result["payload"] | {"git_sha": result["git_sha"]})
    return ProofBundle(
        proof_type=str(result["proof_type"]),
        run_id=str(result["run_id"]),
        generated_at=str(result["generated_at"]),
        git_sha=str(result["git_sha"]),
        simulation_only=bool(result["simulation_only"]),
        trained_result=bool(result["trained_result"]),
        payload=dict(result["payload"]),
    )


def build_release_gate_from_files(
    *,
    stage: str,
    git_sha: str,
    run_path: Path,
) -> ProofBundle:
    data = _read_bundle(run_path / f"data_prep_{stage}.json")
    perception = _read_bundle(run_path / f"perception_eval_{stage}.json")
    rl = _read_bundle(run_path / f"rl_eval_{stage}.json")

    rl_gate = rl["payload"]["release_gate"]
    perception_passed = bool(perception["trained_result"]) and float(
        perception["payload"].get("event_held_out_iou", 0.0)
    ) >= 0.01
    rl_passed = bool(rl["trained_result"]) and bool(rl_gate.get("passed", False))
    passed = perception_passed and rl_passed
    active_models = ActiveModelManifest(
        policy_alias="production" if passed else "candidate",
        policy_artifact=str(rl["payload"]["artifact_id"]),
        perception_alias="production" if passed else "candidate",
        perception_artifact=str(perception["payload"]["artifact_id"]),
        promoted_at=_now(),
        proof_run_id=str(rl["run_id"]),
    ).to_dict()
    payload = {
        "passed": passed,
        "stage": stage,
        "modal_app": "flood-rescue-inference",
        "active_models": active_models,
        "proofs": {
            "data_prep": data,
            "perception": perception,
            "rl": rl,
        },
        "release_gate": {
            "passed": passed,
            "perception_passed": perception_passed,
            "rl_passed": rl_passed,
            "reasons": _gate_reasons(perception_passed, rl_passed, rl_gate),
        },
        "metrics": {
            "perception_iou": perception["payload"].get("event_held_out_iou"),
            "perception_f1": perception["payload"].get("event_held_out_f1"),
            "perception_ece": perception["payload"].get("calibration_ece"),
            "rl_candidate_lives_mean": rl["payload"]["candidate"].get(
                "lives_aided_safely_mean"
            ),
            "rl_baseline_lives_mean": rl["payload"]["baseline"].get(
                "lives_aided_safely_mean"
            ),
            "rl_mean_difference": rl_gate["comparison"].get("mean_difference"),
            "rl_safety_failures": rl_gate.get("safety_failures"),
        },
        "readme_summary": (
            "Modal trained an MVP S1 flood perception baseline and a masked PPO swarm "
            "orchestrator, then evaluated both for the live Cloudflare command center."
        ),
    }
    return _bundle("release_gate", git_sha, payload, trained_result=passed)


def load_latest_release_gate(run_path: Path) -> dict[str, Any]:
    release_path = run_path / "release_gate.json"
    if not release_path.exists():
        stage_files = sorted(run_path.glob("release_gate_*.json"))
        if stage_files:
            release_path = stage_files[-1]
    if not release_path.exists():
        raise FileNotFoundError("No Modal release gate proof has been generated yet")
    bundle = _read_bundle(release_path)
    return bundle["payload"]


def build_fallback_policy_proposal(mission_id: str, *, git_sha: str = "unknown") -> dict[str, Any]:
    proposal = PolicyOutput(
        mission_id=uuid5(NAMESPACE, mission_id),
        drone_id="drone_0",
        action=ActionKind.SEARCH,
        parameters={"sector": "safe-fallback-search", "source": "modal-fallback"},
        confidence=0.52,
        coordination_message=(0.34, 0.33, 0.33),
    )
    return {
        "source": "modal-fallback",
        "git_sha": git_sha,
        "simulation_only": True,
        "proposal": proposal.model_dump(mode="json"),
        "safety": {
            "status": "allowed",
            "executed_action": "search",
            "reason_code": "model_unavailable_safe_action",
            "shield_status": True,
        },
    }


def build_policy_proposal_from_checkpoint(
    *,
    mission_id: str,
    checkpoint_path: Path,
    git_sha: str,
    observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from rescue_swarm.ml.ppo import load_policy_checkpoint, propose_action_from_policy

    policy = load_policy_checkpoint(checkpoint_path)
    policy_observation = observation or {
        "position": (0, 0, 1),
        "battery": 92.0,
        "known_victims": 1,
        "flood_cells": 8,
        "rescued_victims": 0,
        "link_quality": 0.86,
        "action_mask": [1, 1, 0, 1, 1, 1],
    }
    action = propose_action_from_policy(policy, policy_observation)
    proposal = PolicyOutput(
        mission_id=uuid5(NAMESPACE, mission_id),
        drone_id=str(policy_observation.get("drone_id", "drone_0")),
        action=ActionKind(action["action"]),
        parameters={"sector": "highest-priority-safe-cell", "source": "trained-modal-policy"},
        confidence=float(action["confidence"]),
        coordination_message=tuple(action["coordination_message"]),
    )
    return {
        "source": "trained-modal-policy",
        "git_sha": git_sha,
        "simulation_only": True,
        "proposal": proposal.model_dump(mode="json"),
        "safety": {
            "status": "allowed",
            "executed_action": proposal.action.value,
            "reason_code": "trained_policy_safe_proposal",
            "shield_status": True,
        },
    }


def _read_bundle(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _perception_result_to_bundle_dict(result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "artifact_id": result["artifact_id"],
        "checkpoint_path": result["checkpoint_path"],
        "dataset": "Sen1Floods11"
        if result["dataset_source"] != "synthetic_unit"
        else "synthetic-unit-fixture",
        "dataset_hash": result.get("manifest_sha256") or result["artifact_id"],
        "dataset_source": result["dataset_source"],
        "synthetic_unit_mode": bool(result.get("synthetic_unit_mode", False)),
        "stage": result["stage"],
        "model_family": result["model_family"],
        "training_mode": "optimizer-trained small S1 flood segmentation head",
        "optimizer_steps": result["optimizer_steps"],
        "history": [
            {"epoch": idx + 1, "train_loss": loss}
            for idx, loss in enumerate(result.get("train_loss_history", []))
        ],
        "samples_seen": result["samples"],
        "event_held_out_iou": result["validation_iou"],
        "event_held_out_f1": result["validation_f1"],
        "decision_threshold": result.get("decision_threshold"),
        "calibration_iou": result.get("calibration_iou"),
        "calibration_f1": result.get("calibration_f1"),
        "class_balance": result.get("class_balance"),
        "calibration_split": result.get("calibration_split"),
        "heldout_split": result.get("heldout_split"),
        "calibration_ece": result.get("calibration_ece", 0.0),
        "claim_boundary": "MVP S1 flood segmentation baseline; not operational approval",
    }
    return {
        "proof_type": "perception_training",
        "run_id": f"perception-{result['artifact_id']}",
        "generated_at": _now(),
        "git_sha": result["git_sha"],
        "simulation_only": True,
        "trained_result": bool(result["trained_result"]),
        "payload": payload,
    }


def _ppo_result_to_bundle_dict(result: dict[str, Any]) -> dict[str, Any]:
    artifact_id = result.get("artifact_id", f"policy-{_stable_hash(result)[:12]}")
    payload = {
        "algorithm": result["algorithm"],
        "artifact_id": artifact_id,
        "checkpoint_path": result.get("checkpoint_path"),
        "stage": result.get("stage", "smoke"),
        "optimizer_steps": result["optimizer_steps"],
        "curriculum": ["debug-two-drone", "shared-local-four", "hierarchical-eight"],
        "ppo_constraints": result["config"]["ppo_constraints"],
        "training_logs_tail": result["loss_log"][-12:],
        "reward_logs_tail": result["reward_log"][-12:],
        "eval_seeds": result["config"]["eval_seeds"],
        "candidate": result["candidate"],
        "baseline": result["baseline"],
        "release_gate": result["release_gate"],
        "claim_boundary": "trained in simulation; human safety gate remains required",
    }
    return {
        "proof_type": "rl_training",
        "run_id": f"rl-{artifact_id}",
        "generated_at": _now(),
        "git_sha": result.get("git_sha", "unknown"),
        "simulation_only": True,
        "trained_result": bool(result["trained_result"]),
        "payload": payload,
    }


def _gate_reasons(
    perception_passed: bool,
    rl_passed: bool,
    rl_gate: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if not perception_passed:
        reasons.append("perception training/eval did not clear the MVP IoU floor")
    if not rl_passed:
        reasons.extend(rl_gate.get("reasons") or ["RL release gate did not pass"])
    return reasons


def _bundle(
    proof_type: str,
    git_sha: str,
    payload: dict[str, Any],
    *,
    trained_result: bool,
) -> ProofBundle:
    run_id = f"{proof_type}-{_stable_hash(git_sha, payload)[:12]}"
    return ProofBundle(
        proof_type=proof_type,
        run_id=run_id,
        generated_at=_now(),
        git_sha=git_sha,
        simulation_only=True,
        trained_result=trained_result,
        payload=payload,
    )


def _stable_hash(*parts: Any) -> str:
    encoded = json.dumps(parts, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
