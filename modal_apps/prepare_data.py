from __future__ import annotations

import modal

from modal_apps.common import DATA_PATH, data_volume, git_sha, training_image

app = modal.App("flood-rescue-training")


@app.function(image=training_image(), volumes={str(DATA_PATH): data_volume}, timeout=20 * 60)
def prepare_data(stage: str = "smoke") -> str:
    from rescue_swarm.ml import build_data_prep_proof

    DATA_PATH.mkdir(parents=True, exist_ok=True)
    proof = build_data_prep_proof(stage=stage, git_sha=git_sha())
    target = DATA_PATH / f"data_prep_{stage}.json"
    target.write_text(proof.to_json(), encoding="utf-8")
    data_volume.commit()
    return proof.to_json()


@app.local_entrypoint()
def main(stage: str = "smoke") -> None:
    print(prepare_data.remote(stage))
