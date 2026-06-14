from rescue_swarm.evaluation import (
    bootstrap_mean_difference,
    evaluate_episode,
    evaluate_release_gate,
    summarize_episodes,
)


def test_episode_metrics_zero_out_unsafe_rescue_claims() -> None:
    metrics = evaluate_episode(
        {
            "mission_id": "m1",
            "policy_id": "candidate",
            "victims_total": 4,
            "victims_rescued": 3,
            "unsafe_drop_executions": 1,
            "energy_used": 40,
        }
    )

    assert metrics.lives_aided_safely == 0
    assert metrics.rescue_rate == 0


def test_bootstrap_difference_is_deterministic() -> None:
    first = bootstrap_mean_difference((2, 2, 3), (1, 1, 1), seed=7, samples=200)
    second = bootstrap_mean_difference((2, 2, 3), (1, 1, 1), seed=7, samples=200)

    assert first == second
    assert first[0] > 0


def test_release_gate_requires_positive_ci_and_no_executed_safety_violations() -> None:
    baseline = summarize_episodes(
        [
            {"mission_id": "b1", "policy_id": "baseline", "victims_total": 2, "victims_rescued": 1},
            {"mission_id": "b2", "policy_id": "baseline", "victims_total": 2, "victims_rescued": 1},
        ]
    )
    candidate = summarize_episodes(
        [
            {
                "mission_id": "c1",
                "policy_id": "candidate",
                "victims_total": 2,
                "victims_rescued": 2,
            },
            {
                "mission_id": "c2",
                "policy_id": "candidate",
                "victims_total": 2,
                "victims_rescued": 2,
                "collision_executions": 1,
            },
        ]
    )

    gate = evaluate_release_gate(candidate, baseline)

    assert gate.passed is False
    assert gate.safety_failures == 1
    assert "executed safety violations were present" in gate.reasons
