"""Deterministic dataset splitting without event, geography, chip, or frame leakage."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class LeakageSafeSample:
    """A sample plus the grouping keys that must remain in one split."""

    sample_id: str
    event_id: str
    geography_id: str
    source_asset_id: str

    def __post_init__(self) -> None:
        for field_name in ("sample_id", "event_id", "geography_id", "source_asset_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")


class _DisjointSet:
    def __init__(self, values: Sequence[str]) -> None:
        self._parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self._parent[value]
        if parent != value:
            self._parent[value] = self.find(parent)
        return self._parent[value]

    def union(self, first: str, second: str) -> None:
        first_root = self.find(first)
        second_root = self.find(second)
        if first_root != second_root:
            keep, merge = sorted((first_root, second_root))
            self._parent[merge] = keep


def _validate_fractions(fractions: tuple[float, float, float]) -> None:
    if any(fraction <= 0 for fraction in fractions):
        raise ValueError("Split fractions must all be positive")
    if abs(sum(fractions) - 1.0) > 1e-9:
        raise ValueError("Split fractions must sum to 1.0")


def _stable_unit_interval(seed: str, component_ids: Sequence[str]) -> float:
    payload = "\0".join((seed, *sorted(component_ids))).encode()
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def split_by_event_geography(
    samples: Sequence[LeakageSafeSample],
    *,
    fractions: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: str = "rescue-swarm-split-v1",
) -> dict[DatasetSplit, tuple[LeakageSafeSample, ...]]:
    """Assign connected leakage groups to deterministic train/validation/test splits.

    Samples are connected when they share any event, geography, or source asset.
    The transitive closure is assigned together, preventing chips and video frames
    from crossing split boundaries even when multiple grouping keys overlap.
    """

    _validate_fractions(fractions)
    ordered = tuple(sorted(samples, key=lambda sample: sample.sample_id))
    sample_ids = [sample.sample_id for sample in ordered]
    if len(sample_ids) != len(set(sample_ids)):
        duplicates = sorted(
            sample_id for sample_id in set(sample_ids) if sample_ids.count(sample_id) > 1
        )
        raise ValueError(f"Duplicate sample_id values: {', '.join(duplicates)}")

    disjoint_set = _DisjointSet(sample_ids)
    group_owner: dict[tuple[str, str], str] = {}
    for sample in ordered:
        group_values = (
            ("event", sample.event_id),
            ("geography", sample.geography_id),
            ("source_asset", sample.source_asset_id),
        )
        for group_key in group_values:
            owner = group_owner.setdefault(group_key, sample.sample_id)
            disjoint_set.union(sample.sample_id, owner)

    components: dict[str, list[LeakageSafeSample]] = {}
    for sample in ordered:
        components.setdefault(disjoint_set.find(sample.sample_id), []).append(sample)

    train_limit = fractions[0]
    validation_limit = fractions[0] + fractions[1]
    assignments: dict[DatasetSplit, list[LeakageSafeSample]] = {
        split: [] for split in DatasetSplit
    }
    for component in components.values():
        score = _stable_unit_interval(
            seed,
            tuple(sample.sample_id for sample in component),
        )
        if score < train_limit:
            split = DatasetSplit.TRAIN
        elif score < validation_limit:
            split = DatasetSplit.VALIDATION
        else:
            split = DatasetSplit.TEST
        assignments[split].extend(component)

    result = {
        split: tuple(sorted(split_samples, key=lambda sample: sample.sample_id))
        for split, split_samples in assignments.items()
    }
    assert_no_split_leakage(result)
    return result


def assert_no_split_leakage(
    splits: Mapping[DatasetSplit, Sequence[LeakageSafeSample]],
) -> None:
    """Raise when an event, geography, source asset, or sample crosses splits."""

    owners: dict[tuple[str, str], DatasetSplit] = {}
    for split, samples in splits.items():
        for sample in samples:
            groups = (
                ("sample", sample.sample_id),
                ("event", sample.event_id),
                ("geography", sample.geography_id),
                ("source_asset", sample.source_asset_id),
            )
            for group in groups:
                previous = owners.setdefault(group, split)
                if previous is not split:
                    kind, value = group
                    raise ValueError(
                        f"Split leakage for {kind} {value!r}: {previous.value} and {split.value}"
                    )
