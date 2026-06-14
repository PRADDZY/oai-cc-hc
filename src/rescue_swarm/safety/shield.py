"""Deterministic operational safety checks for policy outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import dist

from rescue_swarm.contracts import (
    ActionKind,
    PolicyOutput,
    SafetyDecision,
    SafetyStatus,
)

Cell = tuple[int, int]
Position = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class DroneSafetyFacts:
    """Current facts required to assess one drone action."""

    drone_id: str
    position: Position
    battery: float
    localization_age_seconds: float
    link_quality: float
    has_aid_payload: bool = True

    def __post_init__(self) -> None:
        if not self.drone_id:
            raise ValueError("drone_id must not be empty")
        if len(self.position) != 3:
            raise ValueError("position must contain x, y, and altitude")
        if self.battery < 0:
            raise ValueError("battery cannot be negative")
        if self.localization_age_seconds < 0:
            raise ValueError("localization_age_seconds cannot be negative")
        if not 0 <= self.link_quality <= 1:
            raise ValueError("link_quality must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class WorldSafetyFacts:
    """World geometry and hazards used by the shield."""

    width: int
    height: int
    altitude_levels: int
    base_position: Position
    no_fly_cells: frozenset[Cell] = frozenset()
    victim_cells: frozenset[Cell] = frozenset()
    flood_depths: Mapping[Cell, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0 or self.altitude_levels <= 0:
            raise ValueError("world dimensions must be positive")
        if not self.contains(self.base_position):
            raise ValueError("base_position must be inside the geofence")
        if any(not self.contains_cell(cell) for cell in self.no_fly_cells):
            raise ValueError("no_fly_cells must be inside the geofence")
        if any(depth < 0 for depth in self.flood_depths.values()):
            raise ValueError("flood depths cannot be negative")

    def contains_cell(self, cell: Cell) -> bool:
        return 0 <= cell[0] < self.width and 0 <= cell[1] < self.height

    def contains(self, position: Position) -> bool:
        x, y, altitude = position
        return (
            0 <= x < self.width
            and 0 <= y < self.height
            and 0 <= altitude < self.altitude_levels
        )


@dataclass(frozen=True, slots=True)
class SafetyRules:
    """Thresholds for deterministic shield interventions."""

    battery_reserve: float = 15
    battery_per_grid_unit: float = 1
    max_localization_age_seconds: float = 5
    min_link_quality: float = 0.2
    max_safe_flood_depth: float = 0.5
    max_drop_altitude: int = 1
    max_drop_distance: float = 1.5

    def __post_init__(self) -> None:
        if self.battery_reserve < 0 or self.battery_per_grid_unit < 0:
            raise ValueError("battery thresholds cannot be negative")
        if self.max_localization_age_seconds < 0:
            raise ValueError("max_localization_age_seconds cannot be negative")
        if not 0 <= self.min_link_quality <= 1:
            raise ValueError("min_link_quality must be between 0 and 1")
        if self.max_safe_flood_depth < 0:
            raise ValueError("max_safe_flood_depth cannot be negative")
        if self.max_drop_altitude < 0 or self.max_drop_distance < 0:
            raise ValueError("drop thresholds cannot be negative")


def apply_safety_shield(
    policy: PolicyOutput,
    drone: DroneSafetyFacts,
    world: WorldSafetyFacts,
    rules: SafetyRules | None = None,
) -> SafetyDecision:
    """Return a deterministic safety decision without mutating inputs."""

    active_rules = rules or SafetyRules()
    if policy.drone_id != drone.drone_id:
        raise ValueError("policy and facts must have the same drone_id")

    if (
        policy.action not in {ActionKind.HOLD, ActionKind.RELAY}
        and drone.localization_age_seconds > active_rules.max_localization_age_seconds
    ):
        return _decision(
            policy,
            SafetyStatus.REJECTED,
            ActionKind.HOLD,
            "stale_localization",
            {
                "localization_age_seconds": drone.localization_age_seconds,
                "maximum_age_seconds": active_rules.max_localization_age_seconds,
            },
        )

    if policy.action is ActionKind.MOVE:
        target = _move_target(policy.parameters, drone.position)
        if target is None or not world.contains(target):
            return _decision(
                policy,
                SafetyStatus.REJECTED,
                ActionKind.HOLD,
                "geofence_violation",
                {"target": target},
            )
        if target[:2] in world.no_fly_cells:
            return _decision(
                policy,
                SafetyStatus.REJECTED,
                ActionKind.HOLD,
                "no_fly_violation",
                {"target": target},
            )

    if policy.action is ActionKind.AID_DROP:
        unsafe_reason, evidence = _unsafe_drop_reason(policy, drone, world, active_rules)
        if unsafe_reason is not None:
            return _decision(
                policy,
                SafetyStatus.REJECTED,
                ActionKind.HOLD,
                "unsafe_aid_drop",
                {"unsafe_reason": unsafe_reason, **evidence},
            )

    return_distance = _manhattan_distance(drone.position, world.base_position)
    required_battery = (
        active_rules.battery_reserve
        + return_distance * active_rules.battery_per_grid_unit
    )
    if (
        policy.action not in {ActionKind.HOLD, ActionKind.RETURN}
        and drone.battery < required_battery
    ):
        executed_action = (
            ActionKind.HOLD
            if drone.position == world.base_position
            else ActionKind.RETURN
        )
        return _decision(
            policy,
            SafetyStatus.REPLACED,
            executed_action,
            "battery_reserve",
            {
                "battery": drone.battery,
                "required_battery": required_battery,
                "return_distance": return_distance,
            },
        )

    if (
        policy.action not in {ActionKind.HOLD, ActionKind.RETURN}
        and drone.link_quality < active_rules.min_link_quality
    ):
        executed_action = (
            ActionKind.HOLD
            if drone.position == world.base_position
            else ActionKind.RETURN
        )
        return _decision(
            policy,
            SafetyStatus.REPLACED,
            executed_action,
            "link_loss",
            {
                "link_quality": drone.link_quality,
                "minimum_link_quality": active_rules.min_link_quality,
            },
        )

    return _decision(
        policy,
        SafetyStatus.ALLOWED,
        policy.action,
        "allowed",
        {},
    )


class DeterministicSafetyShield:
    """Reusable shield with fixed rules."""

    def __init__(self, rules: SafetyRules | None = None) -> None:
        self.rules = rules or SafetyRules()

    def evaluate(
        self,
        policy: PolicyOutput,
        drone: DroneSafetyFacts,
        world: WorldSafetyFacts,
    ) -> SafetyDecision:
        return apply_safety_shield(policy, drone, world, self.rules)

    __call__ = evaluate


def _decision(
    policy: PolicyOutput,
    status: SafetyStatus,
    executed_action: ActionKind,
    reason_code: str,
    evidence: dict[str, object],
) -> SafetyDecision:
    return SafetyDecision(
        mission_id=policy.mission_id,
        drone_id=policy.drone_id,
        proposed_action=policy.action,
        status=status,
        executed_action=executed_action,
        reason_code=reason_code,
        evidence=evidence,
    )


def _move_target(
    parameters: Mapping[str, object],
    current_position: Position,
) -> Position | None:
    target = parameters.get("target")
    parsed_target = _position_from_value(target, default_altitude=current_position[2])
    if parsed_target is not None:
        return parsed_target

    delta = parameters.get("delta")
    parsed_delta = _position_from_value(delta, default_altitude=0)
    if parsed_delta is not None:
        return tuple(
            current + change
            for current, change in zip(current_position, parsed_delta, strict=True)
        )

    if "x" in parameters and "y" in parameters:
        try:
            return (
                int(parameters["x"]),
                int(parameters["y"]),
                int(parameters.get("altitude", current_position[2])),
            )
        except (TypeError, ValueError):
            return None
    return None


def _drop_target(
    parameters: Mapping[str, object],
    current_position: Position,
) -> Cell | None:
    value = parameters.get("target", current_position[:2])
    if isinstance(value, Mapping):
        try:
            return int(value["x"]), int(value["y"])
        except (KeyError, TypeError, ValueError):
            return None
    if _is_coordinate_sequence(value) and len(value) >= 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return None
    return None


def _unsafe_drop_reason(
    policy: PolicyOutput,
    drone: DroneSafetyFacts,
    world: WorldSafetyFacts,
    rules: SafetyRules,
) -> tuple[str | None, dict[str, object]]:
    target = _drop_target(policy.parameters, drone.position)
    if not drone.has_aid_payload:
        return "payload_missing", {}
    if target is None or not world.contains_cell(target):
        return "invalid_target", {"target": target}
    if target in world.no_fly_cells:
        return "no_fly_cell", {"target": target}
    if target not in world.victim_cells:
        return "no_victim_at_target", {"target": target}

    flood_depth = world.flood_depths.get(target, 0)
    if flood_depth > rules.max_safe_flood_depth:
        return "flood_depth", {
            "target": target,
            "flood_depth": flood_depth,
            "maximum_depth": rules.max_safe_flood_depth,
        }
    if drone.position[2] > rules.max_drop_altitude:
        return "drop_altitude", {
            "altitude": drone.position[2],
            "maximum_altitude": rules.max_drop_altitude,
        }
    if dist(drone.position[:2], target) > rules.max_drop_distance:
        return "drop_distance", {
            "target": target,
            "maximum_distance": rules.max_drop_distance,
        }
    return None, {}


def _position_from_value(
    value: object,
    *,
    default_altitude: int,
) -> Position | None:
    if isinstance(value, Mapping):
        try:
            return (
                int(value["x"]),
                int(value["y"]),
                int(value.get("altitude", value.get("z", default_altitude))),
            )
        except (KeyError, TypeError, ValueError):
            return None
    if _is_coordinate_sequence(value) and len(value) in {2, 3}:
        try:
            altitude = value[2] if len(value) == 3 else default_altitude
            return int(value[0]), int(value[1]), int(altitude)
        except (TypeError, ValueError):
            return None
    return None


def _is_coordinate_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _manhattan_distance(first: Position, second: Position) -> int:
    return sum(abs(left - right) for left, right in zip(first, second, strict=True))
