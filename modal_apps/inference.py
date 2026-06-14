from __future__ import annotations

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
        from rescue_swarm.ml import build_release_gate_proof

        return build_release_gate_proof(git_sha=self.git_sha).payload["active_models"]

    @modal.fastapi_endpoint(method="GET")
    def proof_latest(self) -> dict[str, Any]:
        from rescue_swarm.ml import build_release_gate_proof

        return build_release_gate_proof(git_sha=self.git_sha).payload

    @modal.fastapi_endpoint(method="POST")
    def policy_propose(self, payload: dict[str, Any]) -> dict[str, Any]:
        from rescue_swarm.ml import build_fallback_policy_proposal

        mission_id = str(payload.get("mission_id", "modal-demo-mission"))
        return build_fallback_policy_proposal(mission_id, git_sha=self.git_sha)
