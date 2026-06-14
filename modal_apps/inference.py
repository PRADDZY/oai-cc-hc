from __future__ import annotations

from pathlib import Path
from typing import Any

import modal

from modal_apps.common import (
    MODEL_PATH,
    RUN_PATH,
    base_image,
    git_sha,
    model_volume,
    run_volume,
)

app = modal.App("flood-rescue-inference")


def inference_image() -> modal.Image:
    return base_image().pip_install("numpy>=2.1,<3")


@app.function(
    image=inference_image(),
    volumes={str(MODEL_PATH): model_volume, str(RUN_PATH): run_volume},
    timeout=10 * 60,
    scaledown_window=10 * 60,
)
@modal.asgi_app()
def api() -> Any:
    from fastapi import FastAPI, Request

    fastapi_app = FastAPI(title="Flood Rescue Modal Inference")
    deployed_git_sha = git_sha()

    @fastapi_app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "modal",
            "simulation_only": True,
            "git_sha": deployed_git_sha,
        }

    @fastapi_app.get("/models_active")
    def models_active() -> dict[str, Any]:
        return _models_active(deployed_git_sha)

    @fastapi_app.get("/proof_latest")
    def proof_latest() -> dict[str, Any]:
        return _proof_latest(deployed_git_sha)

    @fastapi_app.post("/policy_propose")
    async def policy_propose(request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return _policy_propose(payload, deployed_git_sha)

    return fastapi_app


def _models_active(deployed_git_sha: str) -> dict[str, Any]:
    from rescue_swarm.ml import build_fallback_policy_proposal, load_latest_release_gate

    try:
        return load_latest_release_gate(RUN_PATH)["active_models"]
    except FileNotFoundError:
        return {
            "policy_alias": "fallback",
            "policy_artifact": "not-trained-yet",
            "perception_alias": "fallback",
            "perception_artifact": "not-trained-yet",
            "promoted_at": "",
            "proof_run_id": build_fallback_policy_proposal(
                "health",
                git_sha=deployed_git_sha,
            )["git_sha"],
            "simulation_only": True,
        }


def _proof_latest(deployed_git_sha: str) -> dict[str, Any]:
    from rescue_swarm.ml import load_latest_release_gate

    try:
        return load_latest_release_gate(RUN_PATH)
    except FileNotFoundError:
        return {
            "passed": False,
            "source": "modal-fallback",
            "reason": "No trained Modal release gate proof has been generated yet",
            "simulation_only": True,
            "active_models": _models_active(deployed_git_sha),
            "readme_summary": "Run Modal training before using this endpoint as submission proof.",
        }


def _policy_propose(payload: dict[str, Any], deployed_git_sha: str) -> dict[str, Any]:
    from rescue_swarm.ml import (
        build_fallback_policy_proposal,
        build_policy_proposal_from_checkpoint,
        load_latest_release_gate,
    )

    mission_id = str(payload.get("mission_id", "modal-demo-mission"))
    try:
        proof = load_latest_release_gate(RUN_PATH)
        checkpoint_value = proof["proofs"]["rl"]["payload"].get("checkpoint_path")
        checkpoint_path = (
            Path(str(checkpoint_value))
            if checkpoint_value
            else MODEL_PATH / f"{proof['active_models']['policy_artifact']}.json"
        )
        observation = payload.get("observation")
        if not isinstance(observation, dict):
            observation = None
        return build_policy_proposal_from_checkpoint(
            mission_id=mission_id,
            checkpoint_path=checkpoint_path,
            git_sha=deployed_git_sha,
            observation=observation,
        )
    except Exception:
        return build_fallback_policy_proposal(mission_id, git_sha=deployed_git_sha)
