from __future__ import annotations

from uuid import UUID

import pytest

from rescue_swarm.contracts import ActionKind, PolicyOutput, SafetyStatus
from rescue_swarm.safety import (
    DroneSafetyFacts,
    SafetyRules,
    WorldSafetyFacts,
    apply_safety_shield,
)

MISSION_ID = UUID("31a6d5e5-f0ad-45f4-9b67-5f6bd7523220")


def policy(action: ActionKind, **parameters: object) -> PolicyOutput:
    return PolicyOutput(
        mission_id=MISSION_ID,
        drone_id="drone_0",
        action=action,
        parameters=parameters,
        confidence=0.9,
    )


def drone(**overrides: object) -> DroneSafetyFacts:
    values: dict[str, object] = {
        "drone_id": "drone_0",
        "position": (1, 1, 1),
        "battery": 80,
        "localization_age_seconds": 0.5,
        "link_quality": 1,
        "has_aid_payload": True,
    }
    values.update(overrides)
    return DroneSafetyFacts(**values)


def world(**overrides: object) -> WorldSafetyFacts:
    values: dict[str, object] = {
        "width": 5,
        "height": 5,
        "altitude_levels": 3,
        "base_position": (0, 0, 1),
        "victim_cells": frozenset({(2, 1)}),
    }
    values.update(overrides)
    return WorldSafetyFacts(**values)


def test_safe_action_is_allowed_without_mutating_policy() -> None:
    proposed = policy(ActionKind.MOVE, target=(2, 1, 1))

    decision = apply_safety_shield(proposed, drone(), world())

    assert decision.status is SafetyStatus.ALLOWED
    assert decision.executed_action is ActionKind.MOVE
    assert decision.reason_code == "allowed"
    assert decision.mission_id == proposed.mission_id
    assert decision.drone_id == proposed.drone_id
    assert proposed.parameters == {"target": (2, 1, 1)}


def test_battery_reserve_replaces_action_with_return() -> None:
    decision = apply_safety_shield(
        policy(ActionKind.SEARCH),
        drone(battery=11),
        world(),
        SafetyRules(battery_reserve=10, battery_per_grid_unit=2),
    )

    assert decision.status is SafetyStatus.REPLACED
    assert decision.executed_action is ActionKind.RETURN
    assert decision.reason_code == "battery_reserve"
    assert decision.evidence["required_battery"] == pytest.approx(14)


@pytest.mark.parametrize(
    ("target", "reason_code"),
    [
        ((5, 1, 1), "geofence_violation"),
        ((2, 2, 1), "no_fly_violation"),
    ],
)
def test_geofence_and_no_fly_moves_are_rejected(
    target: tuple[int, int, int], reason_code: str
) -> None:
    decision = apply_safety_shield(
        policy(ActionKind.MOVE, target=target),
        drone(),
        world(no_fly_cells=frozenset({(2, 2)})),
    )

    assert decision.status is SafetyStatus.REJECTED
    assert decision.executed_action is ActionKind.HOLD
    assert decision.reason_code == reason_code


@pytest.mark.parametrize(
    ("drone_overrides", "world_overrides", "unsafe_reason"),
    [
        ({"has_aid_payload": False}, {}, "payload_missing"),
        ({}, {"victim_cells": frozenset()}, "no_victim_at_target"),
        ({}, {"flood_depths": {(2, 1): 0.9}}, "flood_depth"),
        ({"position": (2, 1, 2)}, {}, "drop_altitude"),
    ],
)
def test_unsafe_aid_drop_is_rejected(
    drone_overrides: dict[str, object],
    world_overrides: dict[str, object],
    unsafe_reason: str,
) -> None:
    decision = apply_safety_shield(
        policy(ActionKind.AID_DROP, target=(2, 1)),
        drone(**drone_overrides),
        world(**world_overrides),
    )

    assert decision.status is SafetyStatus.REJECTED
    assert decision.executed_action is ActionKind.HOLD
    assert decision.reason_code == "unsafe_aid_drop"
    assert decision.evidence["unsafe_reason"] == unsafe_reason


def test_stale_localization_rejects_position_dependent_action() -> None:
    decision = apply_safety_shield(
        policy(ActionKind.MOVE, target=(2, 1, 1)),
        drone(localization_age_seconds=8),
        world(),
        SafetyRules(max_localization_age_seconds=5),
    )

    assert decision.status is SafetyStatus.REJECTED
    assert decision.executed_action is ActionKind.HOLD
    assert decision.reason_code == "stale_localization"


def test_link_loss_replaces_action_with_return() -> None:
    decision = apply_safety_shield(
        policy(ActionKind.RELAY),
        drone(link_quality=0.05),
        world(),
        SafetyRules(min_link_quality=0.2),
    )

    assert decision.status is SafetyStatus.REPLACED
    assert decision.executed_action is ActionKind.RETURN
    assert decision.reason_code == "link_loss"


def test_policy_and_fact_drone_ids_must_match() -> None:
    with pytest.raises(ValueError, match="drone_id"):
        apply_safety_shield(
            policy(ActionKind.HOLD),
            drone(drone_id="drone_1"),
            world(),
        )
