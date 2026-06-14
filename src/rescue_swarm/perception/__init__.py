"""Dependency-light perception contracts for training-serving parity."""

from rescue_swarm.perception.manifest import (
    TERRAMIND_MODEL_ID,
    TERRAMIND_MODEL_REVISION,
    build_s1_observation_manifest,
)
from rescue_swarm.perception.projection import DeterministicEmbeddingProjector
from rescue_swarm.perception.rl_adapter import (
    CalibrationNoiseConfig,
    RLObservation,
    RLPerceptionAdapter,
)

__all__ = [
    "CalibrationNoiseConfig",
    "DeterministicEmbeddingProjector",
    "RLObservation",
    "RLPerceptionAdapter",
    "TERRAMIND_MODEL_ID",
    "TERRAMIND_MODEL_REVISION",
    "build_s1_observation_manifest",
]

