from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

SEN1FLOODS_VERSION = "v1.1"
SEN1FLOODS_BASE_URL = f"https://storage.googleapis.com/sen1floods11/{SEN1FLOODS_VERSION}"
SPLIT_FOLDER = "splits/flood_handlabeled"
HAND_LABELED_FOLDER = "data/flood_events/HandLabeled"
MANIFEST_SCHEMA_VERSION = "sen1floods11-subset-v1"

SPLIT_URLS = {
    "train": f"{SEN1FLOODS_BASE_URL}/{SPLIT_FOLDER}/flood_train_data.csv",
    "valid": f"{SEN1FLOODS_BASE_URL}/{SPLIT_FOLDER}/flood_valid_data.csv",
    "test": f"{SEN1FLOODS_BASE_URL}/{SPLIT_FOLDER}/flood_test_data.csv",
}

STAGE_LIMITS = {
    "unit": {"train": 0, "valid": 0, "test": 0},
    "smoke": {"train": 8, "valid": 4, "test": 4},
    "modal-smoke": {"train": 24, "valid": 8, "test": 8},
    "medium": {"train": 24, "valid": 8, "test": 8},
    "evidence": {"train": 96, "valid": 24, "test": 24},
}


@dataclass(frozen=True, slots=True)
class Sen1FloodsFile:
    split: str
    role: str
    filename: str
    local_path: str
    source_url: str
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class Sen1FloodsSample:
    split: str
    image_path: str
    label_path: str
    image_url: str
    label_url: str
    image_sha256: str
    label_sha256: str


def prepare_sen1floods_subset(
    stage: str = "smoke",
    root: str | Path = "data",
    *,
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    """Download a bounded Sen1Floods11 hand-labeled subset and write a manifest."""

    root_path = Path(data_root) if data_root is not None else Path(root)
    limits = _stage_limits(stage)
    dataset_root = root_path / "sen1floods11" / SEN1FLOODS_VERSION
    files: list[Sen1FloodsFile] = []
    samples: list[Sen1FloodsSample] = []

    for split, split_url in SPLIT_URLS.items():
        split_path = dataset_root / SPLIT_FOLDER / Path(split_url).name
        _download_file(split_url, split_path)
        files.append(
            _file_entry(split=split, role="split_csv", path=split_path, source_url=split_url)
        )

        for image_name, label_name in _read_split_rows(split_path, limit=limits[split]):
            image_url = f"{SEN1FLOODS_BASE_URL}/{HAND_LABELED_FOLDER}/S1Hand/{image_name}"
            label_url = f"{SEN1FLOODS_BASE_URL}/{HAND_LABELED_FOLDER}/LabelHand/{label_name}"
            image_path = dataset_root / HAND_LABELED_FOLDER / "S1Hand" / image_name
            label_path = dataset_root / HAND_LABELED_FOLDER / "LabelHand" / label_name

            _download_file(image_url, image_path)
            _download_file(label_url, label_path)
            image_file = _file_entry(
                split=split,
                role="s1_image",
                path=image_path,
                source_url=image_url,
            )
            label_file = _file_entry(
                split=split,
                role="hand_label",
                path=label_path,
                source_url=label_url,
            )
            files.extend((image_file, label_file))
            samples.append(
                Sen1FloodsSample(
                    split=split,
                    image_path=str(image_path),
                    label_path=str(label_path),
                    image_url=image_url,
                    label_url=label_url,
                    image_sha256=image_file.sha256,
                    label_sha256=label_file.sha256,
                )
            )

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset": "Sen1Floods11",
        "dataset_version": SEN1FLOODS_VERSION,
        "dataset_source": "sen1floods11_gcs_v1.1",
        "source_base_url": SEN1FLOODS_BASE_URL,
        "stage": stage,
        "split_policy": "official_flood_handlabeled_splits",
        "bounded": stage != "full",
        "limits": limits,
        "sample_count": len(samples),
        "samples_by_split": _count_by_split(samples),
        "files": [asdict(file) for file in files],
        "samples": [asdict(sample) for sample in samples],
    }
    manifest["manifest_sha256"] = _stable_json_hash(manifest)

    target = manifest_path_for(stage, root_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    manifest["manifest_path"] = str(target)
    return manifest


def manifest_path_for(stage: str, root: str | Path = "data") -> Path:
    return Path(root) / "sen1floods11" / SEN1FLOODS_VERSION / "manifests" / f"{stage}.json"


def load_sen1floods_manifest(stage: str, root: str | Path = "data") -> dict[str, Any]:
    path = manifest_path_for(stage, root)
    if not path.exists():
        raise FileNotFoundError(f"Sen1Floods11 manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(data_root: str | Path, stage: str) -> dict[str, Any]:
    """Compatibility alias for older local callers."""

    return load_sen1floods_manifest(stage, data_root)


def _stage_limits(stage: str) -> dict[str, int | None]:
    if stage == "full":
        return {"train": None, "valid": None, "test": None}
    if stage not in STAGE_LIMITS:
        known = ", ".join(sorted([*STAGE_LIMITS, "full"]))
        raise ValueError(f"Unknown Sen1Floods11 stage {stage!r}; expected one of: {known}")
    return dict(STAGE_LIMITS[stage])


def _read_split_rows(path: Path, *, limit: int | None) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if not row:
                continue
            if len(row) < 2:
                raise ValueError(f"Expected image,label columns in {path}: {row!r}")
            rows.append((row[0].strip(), row[1].strip()))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _download_file(source_url: str, target_path: Path) -> None:
    if target_path.exists() and target_path.stat().st_size > 0:
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(source_url, headers={"User-Agent": "flood-rescue-swarm"})
    with urlopen(request, timeout=90) as response:
        target_path.write_bytes(response.read())


def _file_entry(*, split: str, role: str, path: Path, source_url: str) -> Sen1FloodsFile:
    return Sen1FloodsFile(
        split=split,
        role=role,
        filename=path.name,
        local_path=str(path),
        source_url=source_url,
        sha256=_sha256_file(path),
        bytes=path.stat().st_size,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_json_hash(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone.pop("manifest_sha256", None)
    encoded = json.dumps(clone, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _count_by_split(samples: list[Sen1FloodsSample]) -> dict[str, int]:
    counts = {"train": 0, "valid": 0, "test": 0}
    for sample in samples:
        counts[sample.split] = counts.get(sample.split, 0) + 1
    return counts
