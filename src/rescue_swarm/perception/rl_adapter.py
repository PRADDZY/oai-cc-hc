from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

from rescue_swarm.perception.projection import DeterministicEmbeddingProjector


@dataclass(frozen=True, slots=True)
class CalibrationNoiseConfig:
    version: str
    temperature: float = 1.0
    bias: float = 0.0
    logit_noise_std: float = 0.0
    feature_noise_std: float = 0.0

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("calibration version is required")
        if self.temperature <= 0:
            raise ValueError("temperature must be positive")
        if self.logit_noise_std < 0 or self.feature_noise_std < 0:
            raise ValueError("noise standard deviations cannot be negative")


@dataclass(frozen=True, slots=True)
class RLObservation:
    embedding: tuple[float, ...]
    flood_probability: float
    uncertainty: float
    calibration_version: str
    end_to_end_gradients: bool = False


class RLPerceptionAdapter:
    """Convert frozen perception outputs into policy-safe features."""

    def __init__(
        self,
        *,
        projector: DeterministicEmbeddingProjector,
        calibration: CalibrationNoiseConfig,
    ) -> None:
        self.projector = projector
        self.calibration = calibration

    def adapt(
        self,
        embedding: Sequence[float] | object,
        *,
        flood_logit: float,
        uncertainty: float,
        noise_key: str | None = None,
    ) -> RLObservation:
        if not 0 <= uncertainty <= 1:
            raise ValueError("uncertainty must be between 0 and 1")
        noise_enabled = self.calibration.logit_noise_std or self.calibration.feature_noise_std
        if noise_enabled and not noise_key:
            raise ValueError("noise_key is required when deterministic noise is configured")

        values = self._detach_to_tuple(embedding)
        rng = self._rng(noise_key)
        noisy_values = tuple(
            value + rng.gauss(0, self.calibration.feature_noise_std)
            for value in values
        )
        noisy_logit = flood_logit + rng.gauss(0, self.calibration.logit_noise_std)
        calibrated_logit = noisy_logit / self.calibration.temperature + self.calibration.bias
        return RLObservation(
            embedding=self.projector.project(noisy_values),
            flood_probability=1 / (1 + math.exp(-calibrated_logit)),
            uncertainty=float(uncertainty),
            calibration_version=self.calibration.version,
        )

    @staticmethod
    def _detach_to_tuple(embedding: Sequence[float] | object) -> tuple[float, ...]:
        value = embedding
        detach = getattr(value, "detach", None)
        if callable(detach):
            value = detach()
        cpu = getattr(value, "cpu", None)
        if callable(cpu):
            value = cpu()
        tolist = getattr(value, "tolist", None)
        if callable(tolist):
            value = tolist()
        return tuple(float(item) for item in value)  # type: ignore[arg-type]

    @staticmethod
    def _rng(noise_key: str | None) -> random.Random:
        digest = hashlib.sha256((noise_key or "no-noise").encode()).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))
