from __future__ import annotations

import modal

from modal_apps.common import (
    MODEL_PATH,
    RUN_PATH,
    git_sha,
    model_volume,
    run_volume,
    training_image,
)

app = modal.App("flood-rescue-training")


@app.function(
    image=training_image(),
    volumes={str(MODEL_PATH): model_volume, str(RUN_PATH): run_volume},
    timeout=90 * 60,
)
def train_rl(stage: str = "smoke") -> str:
    from rescue_swarm.ml import proof_from_training_result
    from rescue_swarm.ml.ppo import train_swarm_policy

    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    RUN_PATH.mkdir(parents=True, exist_ok=True)
    result = train_swarm_policy(stage=stage, artifact_root=MODEL_PATH, git_sha=git_sha())
    proof = proof_from_training_result(result)
    (RUN_PATH / f"rl_eval_{stage}.json").write_text(proof.to_json(), encoding="utf-8")
    run_volume.commit()
    model_volume.commit()
    return proof.to_json()


@app.local_entrypoint()
def main(stage: str = "smoke") -> str:
    return train_rl.remote(stage)
