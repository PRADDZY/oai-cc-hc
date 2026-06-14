import pytest

from rescue_swarm.data import (
    DatasetSplit,
    LeakageSafeSample,
    assert_no_split_leakage,
    split_by_event_geography,
)


def _samples() -> tuple[LeakageSafeSample, ...]:
    return (
        LeakageSafeSample("chip-a1", "event-a", "geo-a", "scene-a"),
        LeakageSafeSample("chip-a2", "event-a", "geo-b", "scene-b"),
        LeakageSafeSample("chip-b1", "event-b", "geo-b", "scene-c"),
        LeakageSafeSample("frame-c1", "event-c", "geo-c", "flight-c"),
        LeakageSafeSample("frame-c2", "event-d", "geo-d", "flight-c"),
        LeakageSafeSample("chip-e1", "event-e", "geo-e", "scene-e"),
        LeakageSafeSample("chip-f1", "event-f", "geo-f", "scene-f"),
    )


def test_connected_event_geography_and_source_groups_never_leak() -> None:
    splits = split_by_event_geography(_samples(), seed="unit-test")

    assert_no_split_leakage(splits)
    memberships = {
        sample.sample_id: split
        for split, samples in splits.items()
        for sample in samples
    }

    assert memberships["chip-a1"] == memberships["chip-a2"]
    assert memberships["chip-a2"] == memberships["chip-b1"]
    assert memberships["frame-c1"] == memberships["frame-c2"]


def test_split_assignment_is_deterministic_and_order_independent() -> None:
    forward = split_by_event_geography(_samples(), seed="stable-seed")
    reverse = split_by_event_geography(tuple(reversed(_samples())), seed="stable-seed")

    forward_ids = {
        split: tuple(sample.sample_id for sample in samples)
        for split, samples in forward.items()
    }
    reverse_ids = {
        split: tuple(sample.sample_id for sample in samples)
        for split, samples in reverse.items()
    }

    assert forward_ids == reverse_ids
    assert set(forward) == set(DatasetSplit)


def test_duplicate_sample_id_is_rejected() -> None:
    duplicate = LeakageSafeSample("chip-a1", "event-z", "geo-z", "scene-z")

    with pytest.raises(ValueError, match="Duplicate sample_id"):
        split_by_event_geography((*_samples(), duplicate))


def test_invalid_split_fractions_are_rejected() -> None:
    with pytest.raises(ValueError, match="sum to 1.0"):
        split_by_event_geography(_samples(), fractions=(0.8, 0.2, 0.2))
