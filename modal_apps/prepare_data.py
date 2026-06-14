from __future__ import annotations

import modal

from modal_apps.common import DATA_PATH, RUN_PATH, data_volume, git_sha, run_volume, training_image

app = modal.App("flood-rescue-training")


@app.function(
    image=training_image(),
    volumes={str(DATA_PATH): data_volume, str(RUN_PATH): run_volume},
    timeout=20 * 60,
)
def prepare_data(stage: str = "smoke") -> str:
    from rescue_swarm.ml import data_manifest_to_proof
    from rescue_swarm.ml.datasets import prepare_sen1floods_subset

    DATA_PATH.mkdir(parents=True, exist_ok=True)
    RUN_PATH.mkdir(parents=True, exist_ok=True)
    manifest = prepare_sen1floods_subset(stage, DATA_PATH)
    proof = data_manifest_to_proof(manifest=manifest, stage=stage, git_sha=git_sha())
    target = RUN_PATH / f"data_prep_{stage}.json"
    target.write_text(proof.to_json(), encoding="utf-8")
    data_volume.commit()
    run_volume.commit()
    return proof.to_json()


@app.local_entrypoint()
def main(stage: str = "smoke") -> str:
    return prepare_data.remote(stage)
