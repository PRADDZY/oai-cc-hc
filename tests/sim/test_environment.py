from __future__ import annotations

import pytest

from rescue_swarm.sim import FloodRescueConfig, FloodRescueParallelEnv, RescueAction


def test_environment_requires_between_two_and_eight_drones() -> None:
    with pytest.raises(ValueError, match="between 2 and 8"):
        FloodRescueConfig(num_drones=1)

    with pytest.raises(ValueError, match="between 2 and 8"):
        FloodRescueConfig(num_drones=9)


def test_reset_is_reproducible_and_exposes_parallel_api() -> None:
    config = FloodRescueConfig(num_drones=3, width=6, height=5, victim_count=4)
    first = FloodRescueParallelEnv(config)
    second = FloodRescueParallelEnv(config)

    first_observations, first_infos = first.reset(seed=2026)
    second_observations, second_infos = second.reset(seed=2026)

    assert first.possible_agents == ["drone_0", "drone_1", "drone_2"]
    assert first.agents == first.possible_agents
    assert first_observations == second_observations
    assert first_infos == second_infos
    assert first.state() == second.state()

    for agent in first.agents:
        assert first.action_space(agent).n == len(RescueAction)
        assert first.observation_space(agent).contains(first_observations[agent])


def test_same_seed_and_actions_replay_identically() -> None:
    config = FloodRescueConfig(num_drones=2, width=5, height=5, victim_count=2)
    first = FloodRescueParallelEnv(config)
    second = FloodRescueParallelEnv(config)
    first.reset(seed=77)
    second.reset(seed=77)

    action_sequence = (
        {"drone_0": RescueAction.SEARCH, "drone_1": RescueAction.RELAY},
        {"drone_0": RescueAction.MOVE, "drone_1": RescueAction.HOLD},
        {"drone_0": RescueAction.RETURN, "drone_1": RescueAction.SEARCH},
    )

    for actions in action_sequence:
        assert first.step(actions) == second.step(actions)
        assert first.state() == second.state()


def test_search_move_and_aid_drop_complete_a_fixed_mission() -> None:
    config = FloodRescueConfig(
        num_drones=2,
        width=4,
        height=4,
        victim_count=1,
        victim_positions=((1, 0),),
        drone_positions=((0, 0, 1), (3, 3, 1)),
        no_fly_cells=((2, 2),),
        initial_flood_cells=((3, 0),),
        flood_spread_probability=0,
        search_radius=2,
    )
    env = FloodRescueParallelEnv(config)
    observations, _ = env.reset(seed=5)

    assert observations["drone_0"]["action_mask"][RescueAction.AID_DROP] == 0

    observations, rewards, _, _, _ = env.step(
        {"drone_0": RescueAction.SEARCH, "drone_1": RescueAction.HOLD}
    )
    assert rewards["drone_0"] > 0
    assert observations["drone_0"]["known_victims"] == 1

    observations, _, _, _, _ = env.step(
        {"drone_0": RescueAction.MOVE, "drone_1": RescueAction.HOLD}
    )
    assert observations["drone_0"]["position"] == (1, 0, 1)
    assert observations["drone_0"]["action_mask"][RescueAction.AID_DROP] == 1

    _, rewards, terminations, truncations, infos = env.step(
        {"drone_0": RescueAction.AID_DROP, "drone_1": RescueAction.HOLD}
    )
    assert rewards["drone_0"] >= config.rescue_reward
    assert all(terminations.values())
    assert not any(truncations.values())
    assert infos["drone_0"]["rescued_victim"] is True
    assert env.agents == []


def test_flood_cells_evolve_and_no_fly_cells_never_flood() -> None:
    config = FloodRescueConfig(
        num_drones=2,
        width=3,
        height=3,
        victim_count=0,
        initial_flood_cells=((1, 1),),
        no_fly_cells=((1, 0),),
        flood_spread_probability=1,
        max_steps=3,
    )
    env = FloodRescueParallelEnv(config)
    env.reset(seed=9)

    before = env.state()
    env.step({agent: RescueAction.HOLD for agent in env.agents})
    after = env.state()

    assert len(after["flood_cells"]) > len(before["flood_cells"])
    assert (1, 0) not in after["flood_cells"]


def test_invalid_or_masked_action_is_replaced_by_hold() -> None:
    config = FloodRescueConfig(
        num_drones=2,
        width=3,
        height=3,
        victim_count=0,
        initial_battery=5,
        battery_reserve=10,
        max_steps=2,
    )
    env = FloodRescueParallelEnv(config)
    observations, _ = env.reset(seed=11)

    assert observations["drone_0"]["action_mask"][RescueAction.MOVE] == 0

    _, rewards, _, _, infos = env.step(
        {"drone_0": RescueAction.MOVE, "drone_1": 999}
    )

    assert infos["drone_0"]["action_replaced"] is True
    assert infos["drone_0"]["executed_action"] == RescueAction.HOLD.name.lower()
    assert infos["drone_1"]["action_replaced"] is True
    assert rewards["drone_0"] <= config.invalid_action_penalty


def test_max_steps_truncates_all_live_agents() -> None:
    env = FloodRescueParallelEnv(
        FloodRescueConfig(num_drones=2, victim_count=1, max_steps=1)
    )
    env.reset(seed=19)

    _, _, terminations, truncations, _ = env.step(
        {agent: RescueAction.HOLD for agent in env.agents}
    )

    assert not any(terminations.values())
    assert all(truncations.values())
    assert env.agents == []
