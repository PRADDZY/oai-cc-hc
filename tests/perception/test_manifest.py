from datetime import UTC, datetime, timedelta

import pytest

from rescue_swarm.perception import (
    TERRAMIND_MODEL_ID,
    TERRAMIND_MODEL_REVISION,
    build_s1_observation_manifest,
)


def test_s1_manifest_is_pinned_and_contract_compatible() -> None:
    observed_at = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)

    manifest = build_s1_observation_manifest(
        observed_at=observed_at,
        valid_for=timedelta(hours=3),
        calibration_version="s1-db-v1",
    )

    assert manifest.model_id == TERRAMIND_MODEL_ID
    assert manifest.model_revision == TERRAMIND_MODEL_REVISION == "2b5ac0a"
    assert manifest.modality == "S1GRD"
    assert manifest.bands == ("VV", "VH")
    assert manifest.valid_until == observed_at + timedelta(hours=3)
    assert manifest.validity_mask_present is True


def test_s1_manifest_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_s1_observation_manifest(
            observed_at=datetime(2026, 6, 14, 12, 0),
            calibration_version="s1-db-v1",
        )


def test_s1_manifest_rejects_non_positive_validity() -> None:
    with pytest.raises(ValueError, match="valid_for must be positive"):
        build_s1_observation_manifest(
            observed_at=datetime(2026, 6, 14, 12, 0, tzinfo=UTC),
            valid_for=timedelta(0),
            calibration_version="s1-db-v1",
        )
