from __future__ import annotations

import modal

from modal_apps.common import RUN_PATH, git_sha, run_volume, training_image

app = modal.App("flood-rescue-training")


@app.function(image=training_image(), volumes={str(RUN_PATH): run_volume}, timeout=30 * 60)
def evaluate(candidate: str = "latest", baseline: str = "heuristic", stage: str = "smoke") -> str:
    del candidate, baseline
    from rescue_swarm.ml import build_release_gate_from_files

    RUN_PATH.mkdir(parents=True, exist_ok=True)
    proof = build_release_gate_from_files(stage=stage, git_sha=git_sha(), run_path=RUN_PATH)
    (RUN_PATH / "release_gate.json").write_text(proof.to_json(), encoding="utf-8")
    (RUN_PATH / f"release_gate_{stage}.json").write_text(proof.to_json(), encoding="utf-8")
    run_volume.commit()
    return proof.to_json()


@app.local_entrypoint()
def main(candidate: str = "latest", baseline: str = "heuristic", stage: str = "smoke") -> str:
    return evaluate.remote(candidate, baseline, stage)
