from __future__ import annotations

from datetime import datetime, timedelta

from rescue_swarm.contracts import ObservationManifest

TERRAMIND_MODEL_ID = "ibm-esa-geospatial/TerraMind-1.0-tiny"
TERRAMIND_MODEL_REVISION = "2b5ac0a"


def build_s1_observation_manifest(
    *,
    observed_at: datetime,
    calibration_version: str,
    valid_for: timedelta = timedelta(hours=3),
) -> ObservationManifest:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    if valid_for.total_seconds() <= 0:
        raise ValueError("valid_for must be positive")

    return ObservationManifest(
        model_id=TERRAMIND_MODEL_ID,
        model_revision=TERRAMIND_MODEL_REVISION,
        modality="S1GRD",
        bands=("VV", "VH"),
        units="dB",
        normalization="terramind-pretraining-statistics",
        ground_sample_distance_m=10,
        crop_size=(224, 224),
        nodata_policy="validity-mask",
        calibration_version=calibration_version,
        observed_at=observed_at,
        valid_until=observed_at + valid_for,
        validity_mask_present=True,
    )

