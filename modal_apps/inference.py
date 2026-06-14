from __future__ import annotations

from pathlib import Path
from typing import Any

import modal

from modal_apps.common import (
    MODEL_PATH,
    RUN_PATH,
    git_sha,
    model_volume,
    run_volume,
    training_image,
)

app = modal.App("flood-rescue-inference")


@app.cls(
    image=training_image(),
    volumes={str(MODEL_PATH): model_volume, str(RUN_PATH): run_volume},
    timeout=10 * 60,
    scaledown_window=10 * 60,
)
class InferenceService:
    @modal.enter()
    def load(self) -> None:
        self.git_sha = git_sha()

    @modal.fastapi_endpoint(method="GET")
    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "modal",
            "simulation_only": True,
            "git_sha": self.git_sha,
        }

    @modal.fastapi_endpoint(method="GET")
    def models_active(self) -> dict[str, Any]:
        from rescue_swarm.ml import load_latest_release_gate

        try:
            return load_latest_release_gate(RUN_PATH)["active_models"]
        except FileNotFoundError:
            from rescue_swarm.ml import build_fallback_policy_proposal

            return {
                "policy_alias": "fallback",
                "policy_artifact": "not-trained-yet",
                "perception_alias": "fallback",
                "perception_artifact": "not-trained-yet",
                "promoted_at": "",
                "proof_run_id": build_fallback_policy_proposal("health", git_sha=self.git_sha)[
                    "git_sha"
                ],
                "simulation_only": True,
            }

    @modal.fastapi_endpoint(method="GET")
    def proof_latest(self) -> dict[str, Any]:
        from rescue_swarm.ml import load_latest_release_gate

        try:
            return load_latest_release_gate(RUN_PATH)
        except FileNotFoundError:
            return {
                "passed": False,
                "source": "modal-fallback",
                "reason": "No trained Modal release gate proof has been generated yet",
                "simulation_only": True,
                "active_models": self.models_active(),
                "readme_summary": (
                    "Run Modal training before using this endpoint as submission proof."
                ),
            }

    @modal.fastapi_endpoint(method="POST")
    def policy_propose(self, payload: dict[str, Any]) -> dict[str, Any]:
        from rescue_swarm.ml import (
            build_fallback_policy_proposal,
            build_policy_proposal_from_checkpoint,
            load_latest_release_gate,
        )

        mission_id = str(payload.get("mission_id", "modal-demo-mission"))
        try:
            proof = load_latest_release_gate(RUN_PATH)
            checkpoint_value = proof["proofs"]["rl"]["payload"].get("checkpoint_path")
            checkpoint_path = Path(str(checkpoint_value)) if checkpoint_value else (
                MODEL_PATH / f"{proof['active_models']['policy_artifact']}.json"
            )
            observation = payload.get("observation")
            if not isinstance(observation, dict):
                observation = None
            return build_policy_proposal_from_checkpoint(
                mission_id=mission_id,
                checkpoint_path=checkpoint_path,
                git_sha=self.git_sha,
                observation=observation,
            )
        except Exception:
            return build_fallback_policy_proposal(mission_id, git_sha=self.git_sha)
