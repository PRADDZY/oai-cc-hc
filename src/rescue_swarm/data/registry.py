"""Immutable dataset manifests and task-use policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class DatasetRole(StrEnum):
    """How a dataset is allowed to contribute to training and evaluation."""

    PRIMARY = "primary"
    AUXILIARY_ONLY = "auxiliary_only"
    SEPARATE_TASK = "separate_task"
    OPTIONAL_BRANCH = "optional_branch"


class PerceptionTask(StrEnum):
    """Perception tasks kept separate to avoid label or objective conflation."""

    FLOOD_SEGMENTATION = "flood_segmentation"
    INFRASTRUCTURE_ACCESSIBILITY = "infrastructure_accessibility"
    UAV_SCENE_SEGMENTATION = "uav_scene_segmentation"
    VICTIM_DETECTION = "victim_detection"


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Provenance and policy metadata for one dataset branch."""

    dataset_id: str
    name: str
    release: str
    task: PerceptionTask
    role: DatasetRole
    modality: str
    label_kind: str
    source_url: str
    citation_url: str
    leakage_keys: tuple[str, ...]
    primary_metrics_allowed: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return asdict(self)


_MANIFESTS = (
    DatasetManifest(
        dataset_id="sen1floods11-hand",
        name="Sen1Floods11 hand-labeled chips",
        release="cvprw-2020",
        task=PerceptionTask.FLOOD_SEGMENTATION,
        role=DatasetRole.PRIMARY,
        modality="S1GRD",
        label_kind="expert_hand_mask",
        source_url="https://github.com/cloudtostreet/Sen1Floods11",
        citation_url=(
            "https://openaccess.thecvf.com/content_CVPRW_2020/html/w11/"
            "Bonafilia_Sen1Floods11_A_Georeferenced_Dataset_to_Train_and_Test_"
            "Deep_Learning_CVPRW_2020_paper.html"
        ),
        leakage_keys=("event_id", "geography_id", "source_asset_id"),
        primary_metrics_allowed=True,
        notes="Primary flood-segmentation labels and the only Sen1Floods11 evaluation source.",
    ),
    DatasetManifest(
        dataset_id="sen1floods11-weak",
        name="Sen1Floods11 weak masks",
        release="cvprw-2020",
        task=PerceptionTask.FLOOD_SEGMENTATION,
        role=DatasetRole.AUXILIARY_ONLY,
        modality="S1GRD",
        label_kind="weak_generated_mask",
        source_url="https://github.com/cloudtostreet/Sen1Floods11",
        citation_url=(
            "https://openaccess.thecvf.com/content_CVPRW_2020/html/w11/"
            "Bonafilia_Sen1Floods11_A_Georeferenced_Dataset_to_Train_and_Test_"
            "Deep_Learning_CVPRW_2020_paper.html"
        ),
        leakage_keys=("event_id", "geography_id", "source_asset_id"),
        primary_metrics_allowed=False,
        notes="May pretrain or regularize; never report weak-mask validation as a primary metric.",
    ),
    DatasetManifest(
        dataset_id="spacenet8",
        name="SpaceNet 8 flooded roads and buildings",
        release="challenge-release-v1",
        task=PerceptionTask.INFRASTRUCTURE_ACCESSIBILITY,
        role=DatasetRole.SEPARATE_TASK,
        modality="SATELLITE_RGB",
        label_kind="road_building_flood_state",
        source_url="https://github.com/SpaceNetChallenge/SpaceNet8",
        citation_url=(
            "https://openaccess.thecvf.com/content/CVPR2022W/EarthVision/html/"
            "Hansch_SpaceNet_8_-_The_Detection_of_Flooded_Roads_and_Buildings_"
            "CVPRW_2022_paper.html"
        ),
        leakage_keys=("event_id", "geography_id", "source_asset_id"),
        primary_metrics_allowed=True,
        notes="Train and evaluate as accessibility, not as extra Sen1Floods11 flood masks.",
    ),
    DatasetManifest(
        dataset_id="floodnet",
        name="FloodNet supervised UAV scenes",
        release="supervised-v1.0",
        task=PerceptionTask.UAV_SCENE_SEGMENTATION,
        role=DatasetRole.OPTIONAL_BRANCH,
        modality="UAV_RGB",
        label_kind="post_flood_scene_mask",
        source_url="https://github.com/BinaLab/FloodNet-Supervised_v1.0",
        citation_url="https://arxiv.org/abs/2012.02951",
        leakage_keys=("event_id", "geography_id", "source_asset_id"),
        primary_metrics_allowed=False,
        notes="Optional low-altitude scene branch; exclude from the default S1 training path.",
    ),
    DatasetManifest(
        dataset_id="seadronessee-odv2",
        name="SeaDronesSee object detection v2",
        release="object-detection-v2",
        task=PerceptionTask.VICTIM_DETECTION,
        role=DatasetRole.AUXILIARY_ONLY,
        modality="UAV_RGB",
        label_kind="maritime_object_boxes",
        source_url="https://seadronessee.cs.uni-tuebingen.de/dataset",
        citation_url=(
            "https://openaccess.thecvf.com/content/WACV2022/html/"
            "Varga_SeaDronesSee_A_Maritime_Benchmark_for_Detecting_Humans_in_"
            "Open_Water_WACV_2022_paper.html"
        ),
        leakage_keys=("event_id", "geography_id", "source_asset_id"),
        primary_metrics_allowed=False,
        notes="Auxiliary victim detector only; maritime domain shift must remain explicit.",
    ),
)

DATASET_REGISTRY = MappingProxyType(
    {manifest.dataset_id: manifest for manifest in _MANIFESTS}
)


def get_dataset_manifest(dataset_id: str) -> DatasetManifest:
    """Return one manifest with an actionable error for unknown identifiers."""

    try:
        return DATASET_REGISTRY[dataset_id]
    except KeyError as error:
        known = ", ".join(sorted(DATASET_REGISTRY))
        raise KeyError(f"Unknown dataset id {dataset_id!r}. Known dataset ids: {known}") from error


def iter_dataset_manifests(
    *,
    task: PerceptionTask | None = None,
    include_optional: bool = False,
) -> tuple[DatasetManifest, ...]:
    """Return stable registry entries filtered by task and optional-branch policy."""

    manifests = (
        manifest
        for manifest in _MANIFESTS
        if (task is None or manifest.task is task)
        and (include_optional or manifest.role is not DatasetRole.OPTIONAL_BRANCH)
    )
    return tuple(manifests)
