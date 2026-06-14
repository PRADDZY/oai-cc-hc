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
    timeout=45 * 60,
)
def train_perception(stage: str = "smoke") -> str:
    from rescue_swarm.ml import build_perception_training_proof

    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    RUN_PATH.mkdir(parents=True, exist_ok=True)
    proof = build_perception_training_proof(stage=stage, git_sha=git_sha())
    (RUN_PATH / f"perception_eval_{stage}.json").write_text(proof.to_json(), encoding="utf-8")
    artifact_path = MODEL_PATH / f"{proof.payload['artifact_id']}.json"
    artifact_path.write_text(proof.to_json(), encoding="utf-8")
    run_volume.commit()
    model_volume.commit()
    return proof.to_json()


@app.local_entrypoint()
def main(stage: str = "smoke") -> None:
    print(train_perception.remote(stage))
