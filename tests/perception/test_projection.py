import math

import pytest

from rescue_swarm.perception import DeterministicEmbeddingProjector


def test_projection_is_deterministic_compact_and_finite() -> None:
    projector = DeterministicEmbeddingProjector(
        input_dim=8,
        output_dim=3,
        seed="terramind-to-rl-v1",
    )
    embedding = (0.1, -0.2, 0.3, 0.4, -0.5, 0.6, 0.7, -0.8)

    first = projector.project(embedding)
    second = projector.project(embedding)

    assert first == second
    assert len(first) == 3
    assert all(math.isfinite(value) for value in first)
    assert math.isclose(sum(value * value for value in first), 1.0)


def test_projection_seed_changes_basis() -> None:
    embedding = (1.0, 2.0, 3.0, 4.0)
    first = DeterministicEmbeddingProjector(4, 2, seed="a").project(embedding)
    second = DeterministicEmbeddingProjector(4, 2, seed="b").project(embedding)

    assert first != second


def test_projection_rejects_wrong_or_non_finite_input() -> None:
    projector = DeterministicEmbeddingProjector(3, 2)

    with pytest.raises(ValueError, match="Expected 3 embedding values"):
        projector.project((1.0, 2.0))

    with pytest.raises(ValueError, match="finite"):
        projector.project((1.0, math.nan, 3.0))
