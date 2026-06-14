"""Evaluation metrics and release gates for simulation evidence."""

from rescue_swarm.evaluation.metrics import (
    ComparisonResult,
    EpisodeMetrics,
    ReleaseGateResult,
    bootstrap_mean_difference,
    compare_metric,
    evaluate_episode,
    evaluate_release_gate,
    summarize_episodes,
)

__all__ = [
    "ComparisonResult",
    "EpisodeMetrics",
    "ReleaseGateResult",
    "bootstrap_mean_difference",
    "compare_metric",
    "evaluate_episode",
    "evaluate_release_gate",
    "summarize_episodes",
]

