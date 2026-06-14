from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rescue_swarm.ml.datasets import load_sen1floods_manifest

MODEL_FAMILY = "small-conv-s1-flood-head"
SYNTHETIC_UNIT_SOURCE = "synthetic_unit"


class PerceptionDependencyError(RuntimeError):
    """Raised when optional training dependencies are not installed."""


def train_perception_model(
    stage: str = "smoke",
    data_root: str | Path = "data",
    artifact_root: str | Path = "artifacts",
    git_sha: str = "unknown",
) -> dict[str, Any]:
    """Train a small flood segmentation head from a prepared Sen1Floods11 manifest."""

    artifacts = Path(artifact_root)
    if stage == "unit":
        manifest: dict[str, Any] | None = None
        samples = _synthetic_unit_samples()
        dataset_source = SYNTHETIC_UNIT_SOURCE
    else:
        manifest = load_sen1floods_manifest(stage, data_root)
        samples = list(manifest.get("samples", []))
        dataset_source = str(manifest.get("dataset_source", "sen1floods11_gcs_v1.1"))
        if not samples:
            raise ValueError(f"Sen1Floods11 manifest for stage {stage!r} contains no samples")

    sample_counts = _sample_counts(samples)
    artifact_id = _artifact_id(stage=stage, git_sha=git_sha, dataset_source=dataset_source)
    try:
        return _run_torch_training(
            stage=stage,
            samples=samples,
            artifact_root=artifacts,
            artifact_id=artifact_id,
            git_sha=git_sha,
            dataset_source=dataset_source,
            manifest=manifest,
            synthetic_unit_mode=stage == "unit",
        )
    except PerceptionDependencyError as exc:
        return {
            "model_family": MODEL_FAMILY,
            "stage": stage,
            "git_sha": git_sha,
            "dataset_source": dataset_source,
            "synthetic_unit_mode": stage == "unit",
            "trained_result": False,
            "optimizer_steps": 0,
            "train_loss_history": [],
            "validation_iou": None,
            "validation_f1": None,
            "samples": sample_counts,
            "artifact_id": artifact_id,
            "checkpoint_path": None,
            "failure_reason": str(exc),
        }


def _run_torch_training(
    *,
    stage: str,
    samples: list[dict[str, Any]],
    artifact_root: Path,
    artifact_id: str,
    git_sha: str,
    dataset_source: str,
    manifest: dict[str, Any] | None,
    synthetic_unit_mode: bool,
) -> dict[str, Any]:
    try:
        import torch
        from torch import nn
        from torch.nn import functional as nn_functional
    except ModuleNotFoundError as exc:
        raise PerceptionDependencyError("PyTorch is required for perception training") from exc

    torch.manual_seed(17)
    train_records = [record for record in samples if record.get("split") == "train"]
    calibration_records = [record for record in samples if record.get("split") == "valid"]
    heldout_records = [record for record in samples if record.get("split") == "test"]
    calibration_split = "valid" if calibration_records else "train"
    heldout_split = "test" if heldout_records else calibration_split
    if not calibration_records:
        calibration_records = train_records
    if not heldout_records:
        heldout_records = calibration_records
    if not train_records:
        raise ValueError("At least one training sample is required")

    first_image, _, _ = _load_training_tensors(
        train_records[0],
        torch=torch,
        nn_functional=nn_functional,
        synthetic_unit_mode=synthetic_unit_mode,
    )
    model = nn.Sequential(
        nn.Conv2d(int(first_image.shape[0]), 8, kernel_size=3, padding=1),
        nn.ReLU(),
        nn.Conv2d(8, 1, kernel_size=1),
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    class_balance = _class_balance(
        records=train_records,
        torch=torch,
        nn_functional=nn_functional,
        synthetic_unit_mode=synthetic_unit_mode,
    )
    pos_weight = torch.tensor(
        [class_balance["loss_pos_weight"]],
        dtype=torch.float32,
    )
    criterion = nn.BCEWithLogitsLoss(reduction="none", pos_weight=pos_weight)

    train_loss_history: list[float] = []
    optimizer_steps = 0
    epochs = _epochs_for_stage(stage, synthetic_unit_mode=synthetic_unit_mode)
    for _ in range(epochs):
        epoch_losses: list[float] = []
        model.train()
        for record in train_records:
            image, target, valid = _load_training_tensors(
                record,
                torch=torch,
                nn_functional=nn_functional,
                synthetic_unit_mode=synthetic_unit_mode,
            )
            if float(valid.sum().item()) <= 0:
                continue
            optimizer.zero_grad()
            logits = model(image.unsqueeze(0))
            loss = _segmentation_loss(
                logits=logits,
                target=target.unsqueeze(0),
                valid=valid.unsqueeze(0),
                criterion=criterion,
            )
            loss.backward()
            optimizer.step()
            optimizer_steps += 1
            epoch_losses.append(float(loss.detach().item()))
        if epoch_losses:
            train_loss_history.append(round(sum(epoch_losses) / len(epoch_losses), 6))

    decision_threshold, calibration_iou, calibration_f1 = _calibrate_threshold(
        model=model,
        records=calibration_records,
        torch=torch,
        nn_functional=nn_functional,
        synthetic_unit_mode=synthetic_unit_mode,
    )
    validation_iou, validation_f1 = _evaluate_records(
        model=model,
        records=heldout_records,
        torch=torch,
        nn_functional=nn_functional,
        synthetic_unit_mode=synthetic_unit_mode,
        threshold=decision_threshold,
    )

    trained_result = optimizer_steps > 0
    checkpoint_path: str | None = None
    if trained_result:
        artifact_root.mkdir(parents=True, exist_ok=True)
        checkpoint = artifact_root / f"{artifact_id}.pt"
        torch.save(
            {
                "model_family": MODEL_FAMILY,
                "model_state_dict": model.state_dict(),
                "git_sha": git_sha,
                "dataset_source": dataset_source,
                "manifest_sha256": None if manifest is None else manifest.get("manifest_sha256"),
                "synthetic_unit_mode": synthetic_unit_mode,
            },
            checkpoint,
        )
        checkpoint_path = str(checkpoint)

    result = {
        "model_family": MODEL_FAMILY,
        "stage": stage,
        "git_sha": git_sha,
        "dataset_source": dataset_source,
        "synthetic_unit_mode": synthetic_unit_mode,
        "trained_result": trained_result,
        "optimizer_steps": optimizer_steps,
        "train_loss_history": train_loss_history,
        "validation_iou": validation_iou,
        "validation_f1": validation_f1,
        "calibration_iou": calibration_iou,
        "calibration_f1": calibration_f1,
        "decision_threshold": decision_threshold,
        "class_balance": class_balance,
        "calibration_split": calibration_split,
        "heldout_split": heldout_split,
        "samples": _sample_counts(samples),
        "artifact_id": artifact_id,
        "checkpoint_path": checkpoint_path,
        "manifest_sha256": None if manifest is None else manifest.get("manifest_sha256"),
    }
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / f"{artifact_id}.metrics.json").write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def _evaluate_records(
    *,
    model: Any,
    records: list[dict[str, Any]],
    torch: Any,
    nn_functional: Any,
    synthetic_unit_mode: bool,
    threshold: float = 0.5,
) -> tuple[float, float]:
    true_positive = 0.0
    false_positive = 0.0
    false_negative = 0.0
    model.eval()
    with torch.no_grad():
        for record in records:
            image, target, valid = _load_training_tensors(
                record,
                torch=torch,
                nn_functional=nn_functional,
                synthetic_unit_mode=synthetic_unit_mode,
            )
            probabilities = torch.sigmoid(model(image.unsqueeze(0))).squeeze(0)
            prediction = probabilities >= threshold
            target_bool = target >= 0.5
            valid_bool = valid >= 0.5
            true_positive += float((prediction & target_bool & valid_bool).sum().item())
            false_positive += float((prediction & ~target_bool & valid_bool).sum().item())
            false_negative += float((~prediction & target_bool & valid_bool).sum().item())

    iou_denominator = true_positive + false_positive + false_negative
    f1_denominator = (2.0 * true_positive) + false_positive + false_negative
    iou = 0.0 if iou_denominator == 0 else true_positive / iou_denominator
    f1 = 0.0 if f1_denominator == 0 else (2.0 * true_positive) / f1_denominator
    return round(iou, 6), round(f1, 6)


def _calibrate_threshold(
    *,
    model: Any,
    records: list[dict[str, Any]],
    torch: Any,
    nn_functional: Any,
    synthetic_unit_mode: bool,
) -> tuple[float, float, float]:
    best_threshold = 0.5
    best_iou, best_f1 = _evaluate_records(
        model=model,
        records=records,
        torch=torch,
        nn_functional=nn_functional,
        synthetic_unit_mode=synthetic_unit_mode,
        threshold=best_threshold,
    )
    for threshold in (0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.55, 0.6, 0.65):
        iou, f1 = _evaluate_records(
            model=model,
            records=records,
            torch=torch,
            nn_functional=nn_functional,
            synthetic_unit_mode=synthetic_unit_mode,
            threshold=threshold,
        )
        if (f1, iou) > (best_f1, best_iou):
            best_threshold = threshold
            best_iou = iou
            best_f1 = f1
    return round(best_threshold, 2), best_iou, best_f1


def _class_balance(
    *,
    records: list[dict[str, Any]],
    torch: Any,
    nn_functional: Any,
    synthetic_unit_mode: bool,
) -> dict[str, float | int]:
    positive_pixels = 0.0
    valid_pixels = 0.0
    for record in records:
        _, target, valid = _load_training_tensors(
            record,
            torch=torch,
            nn_functional=nn_functional,
            synthetic_unit_mode=synthetic_unit_mode,
        )
        positive_pixels += float((target * valid).sum().item())
        valid_pixels += float(valid.sum().item())
    negative_pixels = max(0.0, valid_pixels - positive_pixels)
    positive_ratio = 0.0 if valid_pixels == 0 else positive_pixels / valid_pixels
    raw_pos_weight = 1.0 if positive_pixels <= 0 else negative_pixels / positive_pixels
    return {
        "valid_pixels": int(valid_pixels),
        "positive_pixels": int(positive_pixels),
        "negative_pixels": int(negative_pixels),
        "positive_ratio": round(positive_ratio, 6),
        "loss_pos_weight": round(min(max(raw_pos_weight, 1.0), 50.0), 6),
    }


def _segmentation_loss(*, logits: Any, target: Any, valid: Any, criterion: Any) -> Any:
    loss_map = criterion(logits, target)
    bce = (loss_map * valid).sum() / valid.sum().clamp_min(1.0)
    probabilities = logits.sigmoid()
    intersection = (probabilities * target * valid).sum()
    denominator = ((probabilities + target) * valid).sum().clamp_min(1.0e-6)
    dice_loss = 1.0 - ((2.0 * intersection + 1.0e-6) / (denominator + 1.0e-6))
    return bce + (0.5 * dice_loss)


def _epochs_for_stage(stage: str, *, synthetic_unit_mode: bool) -> int:
    if synthetic_unit_mode:
        return 3
    if stage == "smoke":
        return 8
    if stage in {"modal-smoke", "medium"}:
        return 6
    return 4


def _load_training_tensors(
    record: dict[str, Any],
    *,
    torch: Any,
    nn_functional: Any,
    synthetic_unit_mode: bool,
) -> tuple[Any, Any, Any]:
    if synthetic_unit_mode:
        image_data = record["image"]
        label_data = record["label"]
    else:
        image_data = _read_tif(record["image_path"])
        label_data = _read_tif(record["label_path"])

    image = torch.as_tensor(image_data, dtype=torch.float32)
    label = torch.as_tensor(label_data, dtype=torch.float32)
    image = _channel_first_image(image)
    label = _single_channel_label(label)

    image = torch.nan_to_num(image, nan=0.0, posinf=0.0, neginf=0.0)
    target = (label > 0).to(dtype=torch.float32).unsqueeze(0)
    valid = (label >= 0).to(dtype=torch.float32).unsqueeze(0)
    image, target, valid = _resize_for_training(image, target, valid, nn_functional)

    mean = image.mean(dim=(1, 2), keepdim=True)
    std = image.std(dim=(1, 2), keepdim=True).clamp_min(1.0e-6)
    image = (image - mean) / std
    return image, target, valid


def _read_tif(path: str) -> Any:
    try:
        import rasterio

        with rasterio.open(path) as dataset:
            return dataset.read()
    except ModuleNotFoundError:
        pass

    try:
        import tifffile

        return tifffile.imread(path)
    except ModuleNotFoundError as exc:
        message = "rasterio or tifffile is required for GeoTIFF input"
        raise PerceptionDependencyError(message) from exc


def _channel_first_image(image: Any) -> Any:
    if image.ndim == 2:
        return image.unsqueeze(0)
    if image.ndim != 3:
        raise ValueError(f"Expected 2D or 3D image tensor, got shape {tuple(image.shape)}")
    if image.shape[0] <= 16:
        return image
    if image.shape[-1] <= 16:
        return image.permute(2, 0, 1)
    raise ValueError(f"Could not infer image channel axis from shape {tuple(image.shape)}")


def _single_channel_label(label: Any) -> Any:
    if label.ndim == 2:
        return label
    if label.ndim != 3:
        raise ValueError(f"Expected 2D or 3D label tensor, got shape {tuple(label.shape)}")
    if label.shape[0] == 1:
        return label[0]
    if label.shape[-1] == 1:
        return label[..., 0]
    return label[0]


def _resize_for_training(
    image: Any,
    target: Any,
    valid: Any,
    nn_functional: Any,
) -> tuple[Any, Any, Any]:
    max_size = 64
    height = int(image.shape[-2])
    width = int(image.shape[-1])
    if height <= max_size and width <= max_size:
        return image, target, valid

    scale = min(max_size / height, max_size / width)
    size = (max(1, int(height * scale)), max(1, int(width * scale)))
    image = nn_functional.interpolate(
        image.unsqueeze(0),
        size=size,
        mode="bilinear",
        align_corners=False,
    ).squeeze(0)
    target = nn_functional.interpolate(target.unsqueeze(0), size=size, mode="nearest").squeeze(0)
    valid = nn_functional.interpolate(valid.unsqueeze(0), size=size, mode="nearest").squeeze(0)
    return image, target, valid


def _synthetic_unit_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for index in range(6):
        image = [
            [[float((x + y + index) % 7) / 7.0 for x in range(16)] for y in range(16)],
            [[float((x * 2 + y + index) % 9) / 9.0 for x in range(16)] for y in range(16)],
        ]
        label = [
            [1.0 if (x + y + index) >= 16 else 0.0 for x in range(16)]
            for y in range(16)
        ]
        samples.append(
            {
                "split": "valid" if index >= 4 else "train",
                "image": image,
                "label": label,
                "source": SYNTHETIC_UNIT_SOURCE,
            }
        )
    return samples


def _sample_counts(samples: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"train": 0, "valid": 0, "test": 0}
    for sample in samples:
        split = str(sample.get("split", "unknown"))
        counts[split] = counts.get(split, 0) + 1
    return counts


def _artifact_id(*, stage: str, git_sha: str, dataset_source: str) -> str:
    source = f"{stage}:{git_sha}:{dataset_source}:{MODEL_FAMILY}"
    digest = hashlib.sha256(source.encode()).hexdigest()
    return f"perception-{stage}-{digest[:12]}"
