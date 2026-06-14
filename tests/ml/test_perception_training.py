from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from rescue_swarm.ml import datasets, perception


def test_prepare_sen1floods_subset_records_official_urls_and_sha256(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_download(source_url: str, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_url.endswith(".csv"):
            split_name = target_path.stem.replace("flood_", "").replace("_data", "")
            target_path.write_text(
                (
                    f"{split_name}_001_S1Hand.tif,{split_name}_001_LabelHand.tif\n"
                    f"{split_name}_002_S1Hand.tif,{split_name}_002_LabelHand.tif\n"
                ),
                encoding="utf-8",
            )
            return
        target_path.write_bytes(f"downloaded from {source_url}".encode())

    monkeypatch.setattr(datasets, "_download_file", fake_download)

    manifest = datasets.prepare_sen1floods_subset(stage="smoke", root=tmp_path)

    assert manifest["dataset_source"] == "sen1floods11_gcs_v1.1"
    assert manifest["sample_count"] == 6
    assert manifest["samples_by_split"] == {"train": 2, "valid": 2, "test": 2}
    assert manifest["manifest_sha256"]
    first_sample = manifest["samples"][0]
    assert first_sample["image_url"].startswith(
        "https://storage.googleapis.com/sen1floods11/v1.1/"
    )
    image_path = Path(first_sample["image_path"])
    assert first_sample["image_sha256"] == hashlib.sha256(image_path.read_bytes()).hexdigest()
    assert datasets.manifest_path_for("smoke", tmp_path).exists()


def test_train_perception_model_requires_real_manifest_outside_unit(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Sen1Floods11 manifest not found"):
        perception.train_perception_model(
            stage="smoke",
            data_root=tmp_path / "missing-data",
            artifact_root=tmp_path / "artifacts",
            git_sha="abc123",
        )


def test_train_perception_model_reports_untrained_when_dependencies_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_torch(**_: Any) -> dict[str, Any]:
        raise perception.PerceptionDependencyError("PyTorch is required for perception training")

    monkeypatch.setattr(perception, "_run_torch_training", missing_torch)

    result = perception.train_perception_model(
        stage="unit",
        data_root=tmp_path / "data",
        artifact_root=tmp_path / "artifacts",
        git_sha="abc123",
    )

    assert result["dataset_source"] == "synthetic_unit"
    assert result["synthetic_unit_mode"] is True
    assert result["trained_result"] is False
    assert result["optimizer_steps"] == 0
    assert result["checkpoint_path"] is None
    assert result["validation_iou"] is None


def test_train_perception_model_passes_synthetic_unit_samples_to_trainer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_trainer(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["dataset_source"] == "synthetic_unit"
        assert kwargs["synthetic_unit_mode"] is True
        assert kwargs["manifest"] is None
        assert len(kwargs["samples"]) == 6
        assert kwargs["samples"][0]["split"] == "train"
        return {
            "model_family": perception.MODEL_FAMILY,
            "stage": kwargs["stage"],
            "git_sha": kwargs["git_sha"],
            "dataset_source": kwargs["dataset_source"],
            "synthetic_unit_mode": kwargs["synthetic_unit_mode"],
            "trained_result": True,
            "optimizer_steps": 3,
            "train_loss_history": [0.9, 0.7],
            "validation_iou": 0.5,
            "validation_f1": 0.66,
            "samples": {"train": 4, "valid": 2, "test": 0},
            "artifact_id": kwargs["artifact_id"],
            "checkpoint_path": str(kwargs["artifact_root"] / "checkpoint.pt"),
        }

    monkeypatch.setattr(perception, "_run_torch_training", fake_trainer)

    result = perception.train_perception_model(
        stage="unit",
        data_root=tmp_path / "data",
        artifact_root=tmp_path / "artifacts",
        git_sha="abc123",
    )

    assert result["trained_result"] is True
    assert result["optimizer_steps"] > 0
    assert result["dataset_source"] == "synthetic_unit"
    assert result["artifact_id"].startswith("perception-unit-")
