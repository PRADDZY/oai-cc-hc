from __future__ import annotations

import modal

from modal_apps.common import (
    DATA_PATH,
    MODEL_PATH,
    RUN_PATH,
    data_volume,
    git_sha,
    model_volume,
    run_volume,
    training_image,
)

app = modal.App("flood-rescue-training")


@app.function(
    image=training_image(),
    volumes={
        str(DATA_PATH): data_volume,
        str(MODEL_PATH): model_volume,
        str(RUN_PATH): run_volume,
    },
    timeout=45 * 60,
)
def train_perception(stage: str = "smoke") -> str:
    from rescue_swarm.ml import proof_from_training_result
    from rescue_swarm.ml.perception import train_perception_model

    DATA_PATH.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    RUN_PATH.mkdir(parents=True, exist_ok=True)
    result = train_perception_model(
        stage=stage,
        data_root=DATA_PATH,
        artifact_root=MODEL_PATH,
        git_sha=git_sha(),
    )
    proof = proof_from_training_result(result)
    (RUN_PATH / f"perception_eval_{stage}.json").write_text(proof.to_json(), encoding="utf-8")
    run_volume.commit()
    model_volume.commit()
    data_volume.commit()
    return proof.to_json()


@app.local_entrypoint()
def main(stage: str = "smoke") -> str:
    return train_perception.remote(stage)
