"""Dataset policy and leakage-safe split utilities."""

from rescue_swarm.data.registry import (
    DatasetManifest,
    DatasetRole,
    PerceptionTask,
    get_dataset_manifest,
    iter_dataset_manifests,
)
from rescue_swarm.data.splits import (
    DatasetSplit,
    LeakageSafeSample,
    assert_no_split_leakage,
    split_by_event_geography,
)

__all__ = [
    "DatasetManifest",
    "DatasetRole",
    "DatasetSplit",
    "LeakageSafeSample",
    "PerceptionTask",
    "assert_no_split_leakage",
    "get_dataset_manifest",
    "iter_dataset_manifests",
    "split_by_event_geography",
]
