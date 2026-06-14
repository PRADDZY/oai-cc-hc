import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rescue_swarm.contracts import DataLabel, EventEnvelope, ObservationManifest


def test_golden_event_round_trips() -> None:
    payload = json.loads(Path("data/fixtures/golden_mission.json").read_text())
    event = EventEnvelope.model_validate(payload)

    assert event.data_label is DataLabel.SIMULATED
    assert EventEnvelope.model_validate_json(event.model_dump_json()) == event


def test_event_rejects_impossible_timestamp_order() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError, match="received_at cannot be earlier"):
        EventEnvelope(
            mission_id=uuid4(),
            source="test",
            event_type="telemetry",
            observed_at=now,
            received_at=datetime(2020, 1, 1, tzinfo=UTC),
            ttl_seconds=5,
            data_label=DataLabel.SIMULATED,
        )


def test_observation_manifest_requires_positive_validity_window() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError, match="valid_until must be later"):
        ObservationManifest(
            model_id="terramind-v1-tiny",
            model_revision="2b5ac0a",
            modality="S1GRD",
            bands=("VV", "VH"),
            units="dB",
            normalization="terramind-pretraining",
            ground_sample_distance_m=10,
            crop_size=(224, 224),
            nodata_policy="mask",
            calibration_version="none",
            observed_at=now,
            valid_until=now,
        )
