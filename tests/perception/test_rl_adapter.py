from dataclasses import dataclass

import pytest

from rescue_swarm.perception import (
    CalibrationNoiseConfig,
    DeterministicEmbeddingProjector,
    RLPerceptionAdapter,
)


@dataclass
class FakeTensor:
    values: list[float]
    detached: bool = False
    moved_to_cpu: bool = False

    def detach(self) -> "FakeTensor":
        self.detached = True
        return self

    def cpu(self) -> "FakeTensor":
        self.moved_to_cpu = True
        return self

    def tolist(self) -> list[float]:
        return self.values


def test_rl_adapter_breaks_gradient_boundary_and_is_reproducible() -> None:
    source = FakeTensor([0.1, 0.2, 0.3, 0.4])
    adapter = RLPerceptionAdapter(
        projector=DeterministicEmbeddingProjector(4, 2, seed="projection-v1"),
        calibration=CalibrationNoiseConfig(
            version="validation-v1",
            temperature=2.0,
            bias=-0.25,
            logit_noise_std=0.1,
            feature_noise_std=0.01,
        ),
    )

    first = adapter.adapt(
        source,
        flood_logit=1.5,
        uncertainty=0.2,
        noise_key="mission-1:observation-7",
    )
    second = adapter.adapt(
        FakeTensor([0.1, 0.2, 0.3, 0.4]),
        flood_logit=1.5,
        uncertainty=0.2,
        noise_key="mission-1:observation-7",
    )

    assert source.detached is True
    assert source.moved_to_cpu is True
    assert first == second
    assert isinstance(first.embedding, tuple)
    assert 0.0 <= first.flood_probability <= 1.0
    assert first.calibration_version == "validation-v1"
    assert first.end_to_end_gradients is False


def test_noise_configuration_requires_stable_key() -> None:
    adapter = RLPerceptionAdapter(
        projector=DeterministicEmbeddingProjector(2, 2),
        calibration=CalibrationNoiseConfig(
            version="noise-v1",
            logit_noise_std=0.1,
        ),
    )

    with pytest.raises(ValueError, match="noise_key"):
        adapter.adapt((0.1, 0.2), flood_logit=0.0, uncertainty=0.5)


def test_adapter_validates_uncertainty() -> None:
    adapter = RLPerceptionAdapter(
        projector=DeterministicEmbeddingProjector(2, 2),
        calibration=CalibrationNoiseConfig(version="no-noise"),
    )

    with pytest.raises(ValueError, match="uncertainty"):
        adapter.adapt((0.1, 0.2), flood_logit=0.0, uncertainty=1.1)
