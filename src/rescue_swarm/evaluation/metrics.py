from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EpisodeMetrics:
    mission_id: str
    policy_id: str
    mode: str
    lives_aided_safely: float
    rescue_rate: float
    time_to_rescue: float
    coverage: float
    collision_executions: int
    geofence_executions: int
    unsafe_drop_executions: int
    safety_interventions: int
    energy_per_rescue: float
    communication_continuity: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    metric: str
    candidate_mean: float
    baseline_mean: float
    mean_difference: float
    ci_low: float
    ci_high: float
    positive_confidence: bool


@dataclass(frozen=True, slots=True)
class ReleaseGateResult:
    passed: bool
    reasons: tuple[str, ...]
    comparison: ComparisonResult
    safety_failures: int


def evaluate_episode(record: dict[str, Any]) -> EpisodeMetrics:
    victims = max(int(record.get("victims_total", 0)), 0)
    rescued = max(int(record.get("victims_rescued", 0)), 0)
    unsafe_executions = int(record.get("unsafe_drop_executions", 0))
    collision_executions = int(record.get("collision_executions", 0))
    geofence_executions = int(record.get("geofence_executions", 0))
    has_executed_violation = bool(
        unsafe_executions or collision_executions or geofence_executions
    )
    safe_rescues = rescued if not has_executed_violation else 0
    energy_used = float(record.get("energy_used", 0.0))
    return EpisodeMetrics(
        mission_id=str(record.get("mission_id", "unknown")),
        policy_id=str(record.get("policy_id", "unknown")),
        mode=str(record.get("mode", "calibrated")),
        lives_aided_safely=float(safe_rescues),
        rescue_rate=(safe_rescues / victims) if victims else 0.0,
        time_to_rescue=float(record.get("time_to_rescue", 0.0)),
        coverage=float(record.get("coverage", 0.0)),
        collision_executions=collision_executions,
        geofence_executions=geofence_executions,
        unsafe_drop_executions=unsafe_executions,
        safety_interventions=int(record.get("safety_interventions", 0)),
        energy_per_rescue=energy_used / safe_rescues if safe_rescues else energy_used,
        communication_continuity=float(record.get("communication_continuity", 0.0)),
    )


def summarize_episodes(
    records: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[EpisodeMetrics, ...]:
    return tuple(evaluate_episode(record) for record in records)


def bootstrap_mean_difference(
    candidate_values: tuple[float, ...],
    baseline_values: tuple[float, ...],
    *,
    seed: int = 2026,
    samples: int = 1000,
) -> tuple[float, float, float]:
    if not candidate_values or not baseline_values:
        raise ValueError("candidate and baseline values are required")
    rng = random.Random(seed)
    diffs: list[float] = []
    for _ in range(samples):
        candidate_mean = _resampled_mean(candidate_values, rng)
        baseline_mean = _resampled_mean(baseline_values, rng)
        diffs.append(candidate_mean - baseline_mean)
    diffs.sort()
    low_idx = int(0.025 * (samples - 1))
    high_idx = int(0.975 * (samples - 1))
    observed = (
        sum(candidate_values) / len(candidate_values)
        - sum(baseline_values) / len(baseline_values)
    )
    return observed, diffs[low_idx], diffs[high_idx]


def compare_metric(
    candidate: tuple[EpisodeMetrics, ...],
    baseline: tuple[EpisodeMetrics, ...],
    *,
    metric: str = "lives_aided_safely",
    seed: int = 2026,
) -> ComparisonResult:
    candidate_values = tuple(float(getattr(item, metric)) for item in candidate)
    baseline_values = tuple(float(getattr(item, metric)) for item in baseline)
    diff, ci_low, ci_high = bootstrap_mean_difference(
        candidate_values,
        baseline_values,
        seed=seed,
    )
    return ComparisonResult(
        metric=metric,
        candidate_mean=sum(candidate_values) / len(candidate_values),
        baseline_mean=sum(baseline_values) / len(baseline_values),
        mean_difference=diff,
        ci_low=ci_low,
        ci_high=ci_high,
        positive_confidence=ci_low > 0,
    )


def evaluate_release_gate(
    candidate: tuple[EpisodeMetrics, ...],
    baseline: tuple[EpisodeMetrics, ...],
) -> ReleaseGateResult:
    comparison = compare_metric(candidate, baseline)
    safety_failures = sum(
        item.collision_executions + item.geofence_executions + item.unsafe_drop_executions
        for item in candidate
    )
    reasons: list[str] = []
    if not comparison.positive_confidence:
        reasons.append("lives_aided_safely confidence interval is not strictly positive")
    if safety_failures:
        reasons.append("executed safety violations were present")
    return ReleaseGateResult(
        passed=not reasons,
        reasons=tuple(reasons),
        comparison=comparison,
        safety_failures=safety_failures,
    )


def _resampled_mean(values: tuple[float, ...], rng: random.Random) -> float:
    return sum(rng.choice(values) for _ in values) / len(values)
