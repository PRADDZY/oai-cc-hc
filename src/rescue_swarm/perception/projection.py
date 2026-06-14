from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence


class DeterministicEmbeddingProjector:
    """Small deterministic projection for cached embeddings in RL tests."""

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        *,
        seed: str = "terramind-to-rl-v1",
    ) -> None:
        if input_dim <= 0 or output_dim <= 0:
            raise ValueError("projection dimensions must be positive")
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.seed = seed
        self._matrix = self._build_matrix()

    def project(self, embedding: Sequence[float]) -> tuple[float, ...]:
        if len(embedding) != self.input_dim:
            raise ValueError(f"Expected {self.input_dim} embedding values")
        values = tuple(float(value) for value in embedding)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("embedding values must be finite")

        projected = tuple(
            sum(weight * value for weight, value in zip(row, values, strict=True))
            for row in self._matrix
        )
        norm = math.sqrt(sum(value * value for value in projected))
        if norm == 0:
            return tuple(0.0 for _ in projected)
        return tuple(value / norm for value in projected)

    def _build_matrix(self) -> tuple[tuple[float, ...], ...]:
        rows: list[tuple[float, ...]] = []
        for row_idx in range(self.output_dim):
            digest = hashlib.sha256(f"{self.seed}:{row_idx}".encode()).digest()
            rng = random.Random(int.from_bytes(digest[:8], "big"))
            rows.append(tuple(rng.uniform(-1, 1) for _ in range(self.input_dim)))
        return tuple(rows)

