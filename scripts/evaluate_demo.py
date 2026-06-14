from __future__ import annotations

import json
from dataclasses import asdict

from rescue_swarm.evaluation import evaluate_release_gate, summarize_episodes


def main() -> None:
    baseline = summarize_episodes(
        [
            {
                "mission_id": "b1",
                "policy_id": "heuristic",
                "victims_total": 3,
                "victims_rescued": 1,
            },
            {
                "mission_id": "b2",
                "policy_id": "heuristic",
                "victims_total": 3,
                "victims_rescued": 1,
            },
        ]
    )
    candidate = summarize_episodes(
        [
            {
                "mission_id": "c1",
                "policy_id": "hierarchical-demo",
                "victims_total": 3,
                "victims_rescued": 2,
            },
            {
                "mission_id": "c2",
                "policy_id": "hierarchical-demo",
                "victims_total": 3,
                "victims_rescued": 2,
            },
        ]
    )
    gate = evaluate_release_gate(candidate, baseline)
    print(
        json.dumps(
            {
                "simulation_only": True,
                "trained_result": False,
                "sample_records_gate_passed": gate.passed,
                "reasons": gate.reasons,
                "comparison": asdict(gate.comparison),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
