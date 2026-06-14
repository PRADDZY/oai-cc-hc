from __future__ import annotations

import random
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

Cell = tuple[int, int]
Position = tuple[int, int, int]


class RescueAction(IntEnum):
    SEARCH = 0
    RELAY = 1
    AID_DROP = 2
    MOVE = 3
    HOLD = 4
    RETURN = 5


class _DiscreteSpace:
    def __init__(self, n: int) -> None:
        self.n = n

    def contains(self, value: object) -> bool:
        return isinstance(value, int) and 0 <= value < self.n


class _ObservationSpace:
    def contains(self, value: object) -> bool:
        if not isinstance(value, dict):
            return False
        required = {"position", "battery", "known_victims", "action_mask", "link_quality"}
        return required.issubset(value) and len(value["action_mask"]) == len(RescueAction)


@dataclass(frozen=True, slots=True)
class FloodRescueConfig:
    num_drones: int = 8
    width: int = 12
    height: int = 12
    altitude_levels: int = 3
    victim_count: int = 6
    victim_positions: tuple[Cell, ...] | None = None
    drone_positions: tuple[Position, ...] | None = None
    no_fly_cells: tuple[Cell, ...] = ()
    initial_flood_cells: tuple[Cell, ...] = ()
    flood_spread_probability: float = 0.15
    search_radius: int = 2
    initial_battery: float = 100
    battery_reserve: float = 12
    battery_per_step: float = 1
    rescue_reward: float = 20
    search_reward: float = 3
    invalid_action_penalty: float = -5
    step_penalty: float = -0.1
    max_steps: int = 100

    def __post_init__(self) -> None:
        if not 2 <= self.num_drones <= 8:
            raise ValueError("num_drones must be between 2 and 8")
        if self.width <= 0 or self.height <= 0 or self.altitude_levels <= 0:
            raise ValueError("world dimensions must be positive")
        if self.victim_count < 0:
            raise ValueError("victim_count cannot be negative")
        if not 0 <= self.flood_spread_probability <= 1:
            raise ValueError("flood_spread_probability must be between 0 and 1")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")


@dataclass
class _DroneState:
    position: Position
    battery: float
    has_payload: bool = True
    link_quality: float = 1.0


class FloodRescueParallelEnv:
    """Small PettingZoo-style ParallelEnv without a hard PettingZoo dependency."""

    metadata = {"name": "flood_rescue_parallel_v0", "is_parallelizable": True}

    def __init__(self, config: FloodRescueConfig | None = None) -> None:
        self.config = config or FloodRescueConfig()
        self.possible_agents = [f"drone_{idx}" for idx in range(self.config.num_drones)]
        self.agents: list[str] = []
        self._action_space = _DiscreteSpace(len(RescueAction))
        self._observation_space = _ObservationSpace()
        self._rng = random.Random(0)
        self._step = 0
        self._drones: dict[str, _DroneState] = {}
        self._victims: set[Cell] = set()
        self._known_victims: set[Cell] = set()
        self._rescued_victims: set[Cell] = set()
        self._flood_cells: set[Cell] = set()
        self._no_fly_cells: set[Cell] = set(self.config.no_fly_cells)

    def action_space(self, agent: str) -> _DiscreteSpace:
        self._require_known_agent(agent)
        return self._action_space

    def observation_space(self, agent: str) -> _ObservationSpace:
        self._require_known_agent(agent)
        return self._observation_space

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        del options
        self._rng = random.Random(seed)
        self._step = 0
        self.agents = list(self.possible_agents)
        self._no_fly_cells = set(self.config.no_fly_cells)
        self._flood_cells = set(self.config.initial_flood_cells)
        self._victims = self._initial_victims()
        self._known_victims = set()
        self._rescued_victims = set()
        self._drones = {
            agent: _DroneState(position=position, battery=self.config.initial_battery)
            for agent, position in zip(self.possible_agents, self._initial_positions(), strict=True)
        }
        return self._observations(), {agent: {"seed": seed} for agent in self.agents}

    def step(
        self,
        actions: dict[str, int | RescueAction],
    ) -> tuple[
        dict[str, dict[str, Any]],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, dict[str, Any]],
    ]:
        live_agents = list(self.agents)
        rewards = {agent: 0.0 for agent in live_agents}
        terminations = {agent: False for agent in live_agents}
        truncations = {agent: False for agent in live_agents}
        infos = {agent: {"action_replaced": False} for agent in live_agents}

        for agent in live_agents:
            action = self._parse_action(actions.get(agent, RescueAction.HOLD))
            mask = self._action_mask(agent)
            if action is None or mask[int(action)] == 0:
                action = RescueAction.HOLD
                rewards[agent] += self.config.invalid_action_penalty
                infos[agent]["action_replaced"] = True

            infos[agent]["executed_action"] = action.name.lower()
            self._drones[agent].battery = max(
                0,
                self._drones[agent].battery - self.config.battery_per_step,
            )
            rewards[agent] += self._apply_action(agent, action, infos[agent])

        self._spread_flood()
        self._step += 1

        all_rescued = self._victims and self._victims == self._rescued_victims
        maxed = self._step >= self.config.max_steps
        if all_rescued or maxed:
            for agent in live_agents:
                terminations[agent] = bool(all_rescued)
                truncations[agent] = bool(maxed and not all_rescued)
            self.agents = []

        return self._observations(), rewards, terminations, truncations, infos

    def state(self) -> dict[str, Any]:
        return {
            "step": self._step,
            "flood_cells": tuple(sorted(self._flood_cells)),
            "known_victims": tuple(sorted(self._known_victims)),
            "rescued_victims": tuple(sorted(self._rescued_victims)),
            "victims": tuple(sorted(self._victims)),
            "drones": {
                agent: {
                    "position": self._drones[agent].position,
                    "battery": round(self._drones[agent].battery, 4),
                    "has_payload": self._drones[agent].has_payload,
                    "link_quality": self._drones[agent].link_quality,
                }
                for agent in self.possible_agents
            },
        }

    def _require_known_agent(self, agent: str) -> None:
        if agent not in self.possible_agents:
            raise KeyError(f"unknown agent {agent!r}")

    def _initial_positions(self) -> tuple[Position, ...]:
        if self.config.drone_positions is not None:
            if len(self.config.drone_positions) != self.config.num_drones:
                raise ValueError("drone_positions length must match num_drones")
            return self.config.drone_positions
        return tuple((0, idx % self.config.height, 1) for idx in range(self.config.num_drones))

    def _initial_victims(self) -> set[Cell]:
        if self.config.victim_positions is not None:
            return set(self.config.victim_positions)
        candidates = [
            (x, y)
            for x in range(self.config.width)
            for y in range(self.config.height)
            if (x, y) not in self._no_fly_cells
        ]
        self._rng.shuffle(candidates)
        return set(candidates[: self.config.victim_count])

    def _observations(self) -> dict[str, dict[str, Any]]:
        return {
            agent: {
                "position": self._drones[agent].position,
                "battery": round(self._drones[agent].battery, 4),
                "known_victims": len(self._known_victims - self._rescued_victims),
                "flood_cells": len(self._flood_cells),
                "rescued_victims": len(self._rescued_victims),
                "link_quality": self._drones[agent].link_quality,
                "action_mask": self._action_mask(agent),
            }
            for agent in self.agents
        }

    def _action_mask(self, agent: str) -> list[int]:
        drone = self._drones[agent]
        can_spend = drone.battery >= self.config.battery_reserve
        current_cell = drone.position[:2]
        return [
            int(can_spend),
            int(can_spend),
            int(
                can_spend
                and drone.has_payload
                and current_cell in self._known_victims
                and current_cell not in self._rescued_victims
            ),
            int(can_spend),
            1,
            1,
        ]

    def _parse_action(self, value: int | RescueAction | None) -> RescueAction | None:
        try:
            return RescueAction(int(value))
        except (TypeError, ValueError):
            return None

    def _apply_action(self, agent: str, action: RescueAction, info: dict[str, Any]) -> float:
        drone = self._drones[agent]
        if action is RescueAction.SEARCH:
            before = len(self._known_victims)
            for victim in self._victims - self._rescued_victims:
                if self._distance(drone.position[:2], victim) <= self.config.search_radius:
                    self._known_victims.add(victim)
            found = len(self._known_victims) - before
            info["found_victims"] = found
            return found * self.config.search_reward

        if action is RescueAction.MOVE:
            drone.position = self._next_move_position(drone.position)
            return 0.2

        if action is RescueAction.AID_DROP:
            cell = drone.position[:2]
            if cell in self._known_victims and cell not in self._rescued_victims:
                self._rescued_victims.add(cell)
                drone.has_payload = False
                info["rescued_victim"] = True
                return self.config.rescue_reward
            info["rescued_victim"] = False
            return self.config.invalid_action_penalty

        if action is RescueAction.RELAY:
            drone.link_quality = min(1.0, drone.link_quality + 0.1)
            return 0.1

        if action is RescueAction.RETURN:
            drone.position = (0, 0, min(drone.position[2], self.config.altitude_levels - 1))
            return 0.0

        return 0.0

    def _next_move_position(self, position: Position) -> Position:
        x, y, z = position
        candidates = (
            (x + 1, y, z),
            (x, y + 1, z),
            (x - 1, y, z),
            (x, y - 1, z),
        )
        for candidate in candidates:
            if self._contains(candidate) and candidate[:2] not in self._no_fly_cells:
                return candidate
        return position

    def _spread_flood(self) -> None:
        additions: set[Cell] = set()
        for cell in self._flood_cells:
            for neighbor in self._neighbors(cell):
                if neighbor in self._no_fly_cells:
                    continue
                if self._rng.random() <= self.config.flood_spread_probability:
                    additions.add(neighbor)
        self._flood_cells.update(additions)

    def _neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        x, y = cell
        return tuple(
            candidate
            for candidate in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
            if 0 <= candidate[0] < self.config.width and 0 <= candidate[1] < self.config.height
        )

    def _contains(self, position: Position) -> bool:
        x, y, z = position
        return (
            0 <= x < self.config.width
            and 0 <= y < self.config.height
            and 0 <= z < self.config.altitude_levels
        )

    @staticmethod
    def _distance(left: Cell, right: Cell) -> int:
        return abs(left[0] - right[0]) + abs(left[1] - right[1])
