import pytest

from rescue_swarm.learning import PPOTrainingConfig, build_training_plan


def test_default_ppo_config_encodes_rl_stability_constraints() -> None:
    config = PPOTrainingConfig()
    rllib_config = config.to_rllib_dict()

    assert rllib_config["clip_param"] == 0.2
    assert rllib_config["entropy_coeff"] > 0
    assert rllib_config["grad_clip"] > 0
    assert rllib_config["model"]["use_lstm"] is True


def test_rejects_unconstrained_policy_updates() -> None:
    with pytest.raises(ValueError, match="clip_param"):
        PPOTrainingConfig(clip_param=1.0).validate()


def test_curriculum_stays_inside_training_scale() -> None:
    assert [stage.active_drones for stage in build_training_plan()] == [2, 4, 8]

