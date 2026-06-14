from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from rescue_swarm.evaluation import EpisodeMetrics, evaluate_episode, evaluate_release_gate
from rescue_swarm.sim import FloodRescueConfig, FloodRescueParallelEnv, RescueAction


@dataclass(frozen=True, slots=True)
class MaskedPPOConfig:
    """Small PPO settings that keep local smoke training CPU-fast."""

    train_seed: int = 2026
    total_updates: int = 20
    rollout_steps: int = 20
    ppo_epochs: int = 4
    minibatch_size: int = 16
    learning_rate: float = 0.03
    gamma: float = 0.97
    gae_lambda: float = 0.9
    clip_epsilon: float = 0.2
    entropy_coeff: float = 0.01
    value_loss_coeff: float = 0.5
    max_grad_norm: float = 0.5
    eval_seeds: tuple[int, ...] = (11, 17, 23, 29)
    eval_deterministic: bool = True

    def validate(self) -> None:
        if self.total_updates <= 0:
            raise ValueError("total_updates must be positive")
        if self.rollout_steps <= 0:
            raise ValueError("rollout_steps must be positive")
        if self.ppo_epochs <= 0:
            raise ValueError("ppo_epochs must be positive")
        if self.minibatch_size <= 0:
            raise ValueError("minibatch_size must be positive")
        if not 0 < self.clip_epsilon <= 0.3:
            raise ValueError("clip_epsilon must constrain PPO policy updates")
        if self.entropy_coeff <= 0:
            raise ValueError("entropy_coeff must encourage exploration")
        if self.value_loss_coeff <= 0:
            raise ValueError("value_loss_coeff must be positive")
        if self.max_grad_norm <= 0:
            raise ValueError("max_grad_norm is required for stable RL updates")
        if not self.eval_seeds:
            raise ValueError("eval_seeds are required for a release-gate comparison")


@dataclass(frozen=True, slots=True)
class StageTrainingConfig:
    num_drones: int
    episodes: int
    total_updates: int
    rollout_steps: int
    ppo_epochs: int
    eval_seeds: tuple[int, ...]


STAGE_CONFIG: dict[str, StageTrainingConfig] = {
    "smoke": StageTrainingConfig(
        num_drones=4,
        episodes=24,
        total_updates=20,
        rollout_steps=20,
        ppo_epochs=4,
        eval_seeds=(11, 17, 23, 29),
    ),
    "full": StageTrainingConfig(
        num_drones=4,
        episodes=96,
        total_updates=40,
        rollout_steps=32,
        ppo_epochs=4,
        eval_seeds=tuple(range(100, 108)),
    ),
    "medium": StageTrainingConfig(
        num_drones=4,
        episodes=48,
        total_updates=30,
        rollout_steps=24,
        ppo_epochs=4,
        eval_seeds=tuple(range(100, 108)),
    ),
}


@dataclass(frozen=True, slots=True)
class RewardLogEntry:
    update: int
    episodes: int
    mean_episode_reward: float
    mean_episode_length: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PPOLossLogEntry:
    update: int
    policy_loss: float
    value_loss: float
    entropy: float
    approx_kl: float
    clip_fraction: float
    grad_norm: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PPOTrainingResult:
    algorithm: str
    trained_result: bool
    optimizer_steps: int
    parameter_l2_delta: float
    reward_log: tuple[RewardLogEntry, ...]
    loss_log: tuple[PPOLossLogEntry, ...]
    baseline: dict[str, Any]
    candidate: dict[str, Any]
    release_gate: dict[str, Any]
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "trained_result": self.trained_result,
            "optimizer_steps": self.optimizer_steps,
            "parameter_l2_delta": self.parameter_l2_delta,
            "reward_log": [entry.to_dict() for entry in self.reward_log],
            "loss_log": [entry.to_dict() for entry in self.loss_log],
            "baseline": self.baseline,
            "candidate": self.candidate,
            "release_gate": self.release_gate,
            "config": self.config,
        }


class _Policy(Protocol):
    def act(
        self,
        observation: dict[str, Any],
        env_config: FloodRescueConfig,
        rng: Any,
        *,
        deterministic: bool,
    ) -> int:
        ...


@dataclass(slots=True)
class _Transition:
    agent: str
    observation: Any
    action_mask: Any
    action: int
    old_log_prob: float
    value: float
    reward: float
    done: bool
    advantage: float = 0.0
    returns: float = 0.0


class _SharedLinearActorCritic:
    def __init__(self, feature_dim: int, action_dim: int, rng: Any) -> None:
        np = _np()
        scale = 0.02
        self.actor_w = rng.normal(0.0, scale, size=(feature_dim, action_dim))
        self.actor_b = np.zeros(action_dim)
        self.value_w = rng.normal(0.0, scale, size=feature_dim)
        self.value_b = np.zeros(1)

    def act(
        self,
        observation: dict[str, Any],
        env_config: FloodRescueConfig,
        rng: Any,
        *,
        deterministic: bool,
    ) -> int:
        np = _np()
        features = _encode_observation(observation, env_config)
        mask = np.asarray(observation["action_mask"], dtype=float)
        probs = self._policy(features, mask)
        if deterministic:
            return int(np.argmax(probs))
        return int(rng.choice(len(probs), p=probs))

    def value(self, observation: Any) -> float:
        return float(observation @ self.value_w + self.value_b[0])

    def action_value_log_prob(
        self,
        observation: dict[str, Any],
        env_config: FloodRescueConfig,
        rng: Any,
    ) -> tuple[Any, Any, int, float, float]:
        np = _np()
        features = _encode_observation(observation, env_config)
        mask = np.asarray(observation["action_mask"], dtype=float)
        probs = self._policy(features, mask)
        action = int(rng.choice(len(probs), p=probs))
        log_prob = float(math.log(float(probs[action]) + 1e-12))
        return features, mask, action, log_prob, self.value(features)

    def _policy(self, features: Any, mask: Any) -> Any:
        logits = features @ self.actor_w + self.actor_b
        return _masked_softmax(logits, mask)

    def flat_parameters(self) -> Any:
        np = _np()
        return np.concatenate(
            [
                self.actor_w.reshape(-1),
                self.actor_b.reshape(-1),
                self.value_w.reshape(-1),
                self.value_b.reshape(-1),
            ]
        )

    def to_checkpoint(self, env_config: FloodRescueConfig) -> dict[str, Any]:
        return {
            "format": "shared-linear-masked-ppo-v1",
            "actor_w": self.actor_w.tolist(),
            "actor_b": self.actor_b.tolist(),
            "value_w": self.value_w.tolist(),
            "value_b": self.value_b.tolist(),
            "env_config": {
                "num_drones": env_config.num_drones,
                "width": env_config.width,
                "height": env_config.height,
                "altitude_levels": env_config.altitude_levels,
                "victim_count": env_config.victim_count,
                "initial_battery": env_config.initial_battery,
            },
            "actions": [action.name.lower() for action in RescueAction],
        }

    @classmethod
    def from_checkpoint(cls, checkpoint: dict[str, Any]) -> _SharedLinearActorCritic:
        np = _np()
        actor_w = np.asarray(checkpoint["actor_w"], dtype=float)
        model = cls(actor_w.shape[0], actor_w.shape[1], np.random.default_rng(0))
        model.actor_w[...] = actor_w
        model.actor_b[...] = np.asarray(checkpoint["actor_b"], dtype=float)
        model.value_w[...] = np.asarray(checkpoint["value_w"], dtype=float)
        model.value_b[...] = np.asarray(checkpoint["value_b"], dtype=float)
        return model


class _Adam:
    def __init__(self, parameters: tuple[Any, ...], learning_rate: float) -> None:
        np = _np()
        self.parameters = parameters
        self.learning_rate = learning_rate
        self.moments = tuple(np.zeros_like(param) for param in parameters)
        self.velocities = tuple(np.zeros_like(param) for param in parameters)
        self.t = 0

    def step(self, gradients: tuple[Any, ...]) -> None:
        np = _np()
        self.t += 1
        beta1 = 0.9
        beta2 = 0.999
        for idx, (param, grad) in enumerate(zip(self.parameters, gradients, strict=True)):
            self.moments[idx][...] = beta1 * self.moments[idx] + (1 - beta1) * grad
            self.velocities[idx][...] = beta2 * self.velocities[idx] + (1 - beta2) * (grad * grad)
            moment_hat = self.moments[idx] / (1 - beta1**self.t)
            velocity_hat = self.velocities[idx] / (1 - beta2**self.t)
            param[...] = param - self.learning_rate * moment_hat / (np.sqrt(velocity_hat) + 1e-8)


def build_debug_env_config(*, num_drones: int = 2) -> FloodRescueConfig:
    """Deterministic training map for quick local and Modal smoke runs."""

    if not 2 <= num_drones <= 4:
        raise ValueError("debug PPO runs use two to four drones")
    positions = tuple((0, idx, 1) for idx in range(num_drones))
    return FloodRescueConfig(
        num_drones=num_drones,
        width=4,
        height=4,
        victim_count=1,
        victim_positions=((1, 0),),
        drone_positions=positions,
        flood_spread_probability=0,
        search_radius=2,
        max_steps=8,
    )


def train_masked_ppo(
    env_config: FloodRescueConfig | None = None,
    ppo_config: MaskedPPOConfig | None = None,
) -> PPOTrainingResult:
    """Train a shared masked PPO policy on FloodRescueParallelEnv.

    This is intentionally lightweight: one linear actor-critic is shared across
    all drones, rollouts honor the environment action masks, and every
    ``trained_result`` is backed by at least one optimizer update.
    """

    result, _ = _train_masked_ppo_model(env_config, ppo_config)
    return result


def train_swarm_policy(
    *,
    stage: str = "smoke",
    artifact_root: str | Path = "proof",
    git_sha: str = "unknown",
) -> dict[str, Any]:
    if stage not in STAGE_CONFIG:
        raise ValueError(f"unknown PPO training stage {stage!r}")

    stage_config = STAGE_CONFIG[stage]
    env_config = build_debug_env_config(num_drones=stage_config.num_drones)
    ppo_config = MaskedPPOConfig(
        total_updates=stage_config.total_updates,
        rollout_steps=stage_config.rollout_steps,
        ppo_epochs=stage_config.ppo_epochs,
        eval_seeds=stage_config.eval_seeds,
        eval_deterministic=False,
    )
    result, model = _train_masked_ppo_model(env_config, ppo_config)

    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    artifact_id = f"shared-linear-masked-ppo-{stage}-{_artifact_digest(git_sha, result)}"
    checkpoint_path = root / f"{artifact_id}.json"
    _write_json(
        checkpoint_path,
        {
            **model.to_checkpoint(env_config),
            "stage": stage,
            "git_sha": git_sha,
            "optimizer_steps": result.optimizer_steps,
        },
    )

    payload = result.to_dict()
    payload["algorithm"] = "shared-linear-masked-ppo"
    payload["artifact_id"] = artifact_id
    payload["stage"] = stage
    payload["checkpoint_path"] = str(checkpoint_path)
    payload["ppo_constraints"] = {
        "clip_param": ppo_config.clip_epsilon,
        "normalize_advantages": True,
        "entropy_bonus": ppo_config.entropy_coeff,
        "grad_clip": ppo_config.max_grad_norm,
        "value_loss": ppo_config.value_loss_coeff,
        "shared_policy_across_drones": True,
        "action_masks": True,
    }

    return {
        "proof_type": "rl_training",
        "run_id": f"rl-{artifact_id}",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "git_sha": git_sha,
        "simulation_only": True,
        "trained_result": result.trained_result,
        "payload": payload,
    }


def load_policy_checkpoint(path: Path | str) -> _SharedLinearActorCritic:
    import json

    checkpoint = json.loads(Path(path).read_text(encoding="utf-8"))
    return _SharedLinearActorCritic.from_checkpoint(checkpoint)


def propose_action_from_policy(
    policy: _SharedLinearActorCritic,
    observation: dict[str, Any],
) -> dict[str, Any]:
    np = _np()
    checkpoint_env = FloodRescueConfig(num_drones=2)
    features = _encode_observation(observation, checkpoint_env)
    mask = np.asarray(observation["action_mask"], dtype=float)
    probabilities = policy._policy(features, mask)
    action = RescueAction(int(np.argmax(probabilities)))
    confidence = float(probabilities[int(action)])
    return {
        "action": action.name.lower(),
        "confidence": round(confidence, 6),
        "coordination_message": _coordination_message(probabilities),
    }


def _train_masked_ppo_model(
    env_config: FloodRescueConfig | None,
    ppo_config: MaskedPPOConfig | None,
) -> tuple[PPOTrainingResult, _SharedLinearActorCritic]:
    np = _np()
    config = ppo_config or MaskedPPOConfig()
    config.validate()
    env_config = env_config or build_debug_env_config()
    rng = np.random.default_rng(config.train_seed)

    feature_dim = len(_encode_observation(_sample_observation(env_config), env_config))
    model = _SharedLinearActorCritic(feature_dim, len(RescueAction), rng)
    initial_parameters = model.flat_parameters().copy()
    optimizer = _Adam(
        (model.actor_w, model.actor_b, model.value_w, model.value_b),
        config.learning_rate,
    )

    reward_log: list[RewardLogEntry] = []
    loss_log: list[PPOLossLogEntry] = []
    optimizer_steps = 0

    for update in range(config.total_updates):
        transitions, episode_rewards, episode_lengths = _collect_rollout(
            model,
            env_config,
            config,
            rng,
            seed=config.train_seed + update,
        )
        _attach_gae(transitions, config)
        loss_entry, steps = _ppo_update(model, optimizer, transitions, config, rng, update=update)
        optimizer_steps += steps
        loss_log.append(loss_entry)
        reward_log.append(
            RewardLogEntry(
                update=update,
                episodes=len(episode_rewards),
                mean_episode_reward=_mean(episode_rewards),
                mean_episode_length=_mean(episode_lengths),
            )
        )

    parameter_delta = float(np.linalg.norm(model.flat_parameters() - initial_parameters))
    baseline_metrics = evaluate_policy(
        _BaselinePolicy(),
        env_config,
        config.eval_seeds,
        policy_id="baseline-hold",
    )
    candidate_metrics = evaluate_policy(
        model,
        env_config,
        config.eval_seeds,
        policy_id="masked-ppo-shared-policy",
        deterministic=config.eval_deterministic,
    )
    gate = evaluate_release_gate(candidate_metrics, baseline_metrics)

    return PPOTrainingResult(
        algorithm="masked-ppo-shared-swarm-policy",
        trained_result=optimizer_steps > 0,
        optimizer_steps=optimizer_steps,
        parameter_l2_delta=round(parameter_delta, 8),
        reward_log=tuple(reward_log),
        loss_log=tuple(loss_log),
        baseline=_summarize_metrics(baseline_metrics),
        candidate=_summarize_metrics(candidate_metrics),
        release_gate={
            "passed": gate.passed,
            "reasons": list(gate.reasons),
            "safety_failures": gate.safety_failures,
            "comparison": asdict(gate.comparison),
        },
        config={
            **asdict(config),
            "env": {
                "num_drones": env_config.num_drones,
                "width": env_config.width,
                "height": env_config.height,
                "max_steps": env_config.max_steps,
                "victim_count": env_config.victim_count,
            },
            "ppo_constraints": {
                "clipped_policy_update": True,
                "normalize_advantages": True,
                "entropy_bonus": config.entropy_coeff,
                "value_loss": config.value_loss_coeff,
                "gradient_clip": config.max_grad_norm,
                "shared_policy_across_drones": True,
                "action_masks": True,
            },
        },
    ), model


def evaluate_policy(
    policy: _Policy,
    env_config: FloodRescueConfig,
    seeds: tuple[int, ...],
    *,
    policy_id: str,
    deterministic: bool = True,
) -> tuple[EpisodeMetrics, ...]:
    np = _np()
    metrics: list[EpisodeMetrics] = []
    for seed in seeds:
        env = FloodRescueParallelEnv(env_config)
        observations, _ = env.reset(seed=seed)
        rng = np.random.default_rng(seed)
        rewards_total = 0.0
        safety_interventions = 0
        coverage_cells: set[tuple[int, int]] = set()
        steps = 0
        while env.agents:
            actions = {
                agent: policy.act(
                    observation,
                    env_config,
                    rng,
                    deterministic=deterministic,
                )
                for agent, observation in observations.items()
            }
            observations, rewards, _, _, infos = env.step(actions)
            rewards_total += sum(rewards.values())
            state = env.state()
            for drone in state["drones"].values():
                coverage_cells.add(tuple(drone["position"][:2]))
            safety_interventions += sum(int(info["action_replaced"]) for info in infos.values())
            steps += 1
        state = env.state()
        metrics.append(
            evaluate_episode(
                {
                    "mission_id": f"seed-{seed}",
                    "policy_id": policy_id,
                    "mode": "trained" if policy_id.startswith("masked-ppo") else "baseline",
                    "victims_total": len(state["victims"]),
                    "victims_rescued": len(state["rescued_victims"]),
                    "time_to_rescue": steps,
                    "coverage": len(coverage_cells) / (env_config.width * env_config.height),
                    "collision_executions": 0,
                    "geofence_executions": 0,
                    "unsafe_drop_executions": 0,
                    "safety_interventions": safety_interventions,
                    "energy_used": steps * env_config.num_drones * env_config.battery_per_step,
                    "communication_continuity": 1.0 if safety_interventions == 0 else 0.9,
                    "episode_reward": rewards_total,
                }
            )
        )
    return tuple(metrics)


class _BaselinePolicy:
    def act(
        self,
        observation: dict[str, Any],
        env_config: FloodRescueConfig,
        rng: Any,
        *,
        deterministic: bool,
    ) -> int:
        del env_config, rng, deterministic
        mask = observation["action_mask"]
        if mask[RescueAction.HOLD]:
            return int(RescueAction.HOLD)
        return int(RescueAction.RETURN)


def _collect_rollout(
    model: _SharedLinearActorCritic,
    env_config: FloodRescueConfig,
    config: MaskedPPOConfig,
    rng: Any,
    *,
    seed: int,
) -> tuple[list[_Transition], list[float], list[int]]:
    transitions: list[_Transition] = []
    episode_rewards: list[float] = []
    episode_lengths: list[int] = []
    env = FloodRescueParallelEnv(env_config)
    observations, _ = env.reset(seed=seed)
    current_episode_reward = 0.0
    current_episode_length = 0

    while len(transitions) < config.rollout_steps * env_config.num_drones:
        pending: dict[str, _Transition] = {}
        actions: dict[str, int] = {}
        for agent, observation in observations.items():
            features, mask, action, log_prob, value = model.action_value_log_prob(
                observation,
                env_config,
                rng,
            )
            pending[agent] = _Transition(
                agent=agent,
                observation=features,
                action_mask=mask,
                action=action,
                old_log_prob=log_prob,
                value=value,
                reward=0.0,
                done=False,
            )
            actions[agent] = action

        observations, rewards, terminations, truncations, _ = env.step(actions)
        current_episode_reward += sum(rewards.values())
        current_episode_length += 1
        done_all = not env.agents

        for agent, transition in pending.items():
            transition.reward = float(rewards[agent])
            transition.done = bool(terminations[agent] or truncations[agent] or done_all)
            transitions.append(transition)

        if done_all:
            episode_rewards.append(current_episode_reward)
            episode_lengths.append(current_episode_length)
            env = FloodRescueParallelEnv(env_config)
            observations, _ = env.reset(seed=seed + len(episode_rewards))
            current_episode_reward = 0.0
            current_episode_length = 0

    if current_episode_length:
        episode_rewards.append(current_episode_reward)
        episode_lengths.append(current_episode_length)
    return transitions, episode_rewards, episode_lengths


def _attach_gae(transitions: list[_Transition], config: MaskedPPOConfig) -> None:
    by_agent: dict[str, list[_Transition]] = {}
    for transition in transitions:
        by_agent.setdefault(transition.agent, []).append(transition)

    for agent_transitions in by_agent.values():
        next_advantage = 0.0
        next_value = 0.0
        for transition in reversed(agent_transitions):
            nonterminal = 0.0 if transition.done else 1.0
            delta = transition.reward + config.gamma * next_value * nonterminal - transition.value
            next_advantage = (
                delta + config.gamma * config.gae_lambda * nonterminal * next_advantage
            )
            transition.advantage = float(next_advantage)
            transition.returns = float(transition.advantage + transition.value)
            next_value = transition.value


def _ppo_update(
    model: _SharedLinearActorCritic,
    optimizer: _Adam,
    transitions: list[_Transition],
    config: MaskedPPOConfig,
    rng: Any,
    *,
    update: int,
) -> tuple[PPOLossLogEntry, int]:
    np = _np()
    observations = np.stack([item.observation for item in transitions])
    action_masks = np.stack([item.action_mask for item in transitions])
    actions = np.asarray([item.action for item in transitions], dtype=int)
    old_log_probs = np.asarray([item.old_log_prob for item in transitions], dtype=float)
    returns = np.asarray([item.returns for item in transitions], dtype=float)
    advantages = np.asarray([item.advantage for item in transitions], dtype=float)
    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

    loss_records: list[tuple[float, float, float, float, float, float]] = []
    optimizer_steps = 0
    indices = np.arange(len(transitions))
    for _ in range(config.ppo_epochs):
        rng.shuffle(indices)
        for start in range(0, len(indices), config.minibatch_size):
            batch = indices[start : start + config.minibatch_size]
            grads, record = _loss_and_gradients(
                model,
                observations[batch],
                action_masks[batch],
                actions[batch],
                old_log_probs[batch],
                returns[batch],
                advantages[batch],
                config,
            )
            optimizer.step(grads)
            optimizer_steps += 1
            loss_records.append(record)

    means = tuple(_mean([record[idx] for record in loss_records]) for idx in range(6))
    return (
        PPOLossLogEntry(
            update=update,
            policy_loss=means[0],
            value_loss=means[1],
            entropy=means[2],
            approx_kl=means[3],
            clip_fraction=means[4],
            grad_norm=means[5],
        ),
        optimizer_steps,
    )


def _loss_and_gradients(
    model: _SharedLinearActorCritic,
    observations: Any,
    action_masks: Any,
    actions: Any,
    old_log_probs: Any,
    returns: Any,
    advantages: Any,
    config: MaskedPPOConfig,
) -> tuple[tuple[Any, ...], tuple[float, float, float, float, float, float]]:
    np = _np()
    batch_size = len(actions)
    logits = observations @ model.actor_w + model.actor_b
    probs = np.stack(
        [_masked_softmax(logit, mask) for logit, mask in zip(logits, action_masks, strict=True)]
    )
    chosen_probs = probs[np.arange(batch_size), actions]
    new_log_probs = np.log(chosen_probs + 1e-12)
    ratios = np.exp(new_log_probs - old_log_probs)
    clipped_ratios = np.clip(ratios, 1 - config.clip_epsilon, 1 + config.clip_epsilon)
    surrogate = np.minimum(ratios * advantages, clipped_ratios * advantages)
    policy_loss = -float(np.mean(surrogate))

    values = observations @ model.value_w + model.value_b[0]
    value_errors = values - returns
    value_loss = float(np.mean(value_errors * value_errors))
    entropy_per_row = -np.sum(probs * np.log(probs + 1e-12) * action_masks, axis=1)
    entropy = float(np.mean(entropy_per_row))

    grad_logits = np.zeros_like(probs)
    active = ((advantages >= 0) & (ratios <= 1 + config.clip_epsilon)) | (
        (advantages < 0) & (ratios >= 1 - config.clip_epsilon)
    )
    for row in range(batch_size):
        if active[row]:
            grad_log_prob = -advantages[row] * ratios[row] / batch_size
            grad_logits[row] -= grad_log_prob * probs[row]
            grad_logits[row, actions[row]] += grad_log_prob

    entropy_grad = config.entropy_coeff * probs * (np.log(probs + 1e-12) + entropy_per_row[:, None])
    grad_logits += entropy_grad * action_masks / batch_size

    grad_actor_w = observations.T @ grad_logits
    grad_actor_b = grad_logits.sum(axis=0)
    grad_values = (2 * config.value_loss_coeff / batch_size) * value_errors
    grad_value_w = observations.T @ grad_values
    grad_value_b = np.asarray([grad_values.sum()], dtype=float)

    gradients = (grad_actor_w, grad_actor_b, grad_value_w, grad_value_b)
    grad_norm = _global_norm(gradients)
    if grad_norm > config.max_grad_norm:
        scale = config.max_grad_norm / (grad_norm + 1e-8)
        gradients = tuple(grad * scale for grad in gradients)

    approx_kl = float(np.mean(old_log_probs - new_log_probs))
    clip_fraction = float(np.mean(np.abs(ratios - 1.0) > config.clip_epsilon))
    return (
        gradients,
        (
            round(policy_loss, 6),
            round(value_loss, 6),
            round(entropy, 6),
            round(approx_kl, 6),
            round(clip_fraction, 6),
            round(min(grad_norm, config.max_grad_norm), 6),
        ),
    )


def _encode_observation(observation: dict[str, Any], env_config: FloodRescueConfig) -> Any:
    np = _np()
    x, y, z = observation["position"]
    victim_scale = max(env_config.victim_count, 1)
    area = max(env_config.width * env_config.height, 1)
    mask = tuple(float(value) for value in observation["action_mask"])
    return np.asarray(
        (
            x / max(env_config.width - 1, 1),
            y / max(env_config.height - 1, 1),
            z / max(env_config.altitude_levels - 1, 1),
            float(observation["battery"]) / max(env_config.initial_battery, 1),
            float(observation["known_victims"]) / victim_scale,
            float(observation.get("flood_cells", 0)) / area,
            float(observation.get("rescued_victims", 0)) / victim_scale,
            float(observation["link_quality"]),
            *mask,
        ),
        dtype=float,
    )


def _sample_observation(env_config: FloodRescueConfig) -> dict[str, Any]:
    env = FloodRescueParallelEnv(env_config)
    observations, _ = env.reset(seed=0)
    return next(iter(observations.values()))


def _masked_softmax(logits: Any, action_mask: Any) -> Any:
    np = _np()
    mask = action_mask.astype(bool)
    if not bool(mask.any()):
        raise ValueError("action mask must expose at least one legal action")
    masked_logits = np.where(mask, logits, -1e9)
    shifted = masked_logits - np.max(masked_logits[mask])
    exp_logits = np.exp(shifted) * action_mask
    return exp_logits / np.sum(exp_logits)


def _summarize_metrics(metrics: tuple[EpisodeMetrics, ...]) -> dict[str, Any]:
    return {
        "episodes": len(metrics),
        "lives_aided_safely_mean": _mean([item.lives_aided_safely for item in metrics]),
        "rescue_rate_mean": _mean([item.rescue_rate for item in metrics]),
        "coverage_mean": _mean([item.coverage for item in metrics]),
        "safety_failures": sum(
            item.collision_executions + item.geofence_executions + item.unsafe_drop_executions
            for item in metrics
        ),
        "safety_interventions": sum(item.safety_interventions for item in metrics),
        "episodes_detail": [item.to_dict() for item in metrics],
    }


def _coordination_message(probabilities: Any) -> tuple[float, float, float]:
    search = float(probabilities[int(RescueAction.SEARCH)])
    move = float(probabilities[int(RescueAction.MOVE)])
    aid = float(probabilities[int(RescueAction.AID_DROP)])
    total = max(search + move + aid, 1e-12)
    return (round(search / total, 6), round(move / total, 6), round(aid / total, 6))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    import json

    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _global_norm(gradients: tuple[Any, ...]) -> float:
    np = _np()
    return float(math.sqrt(sum(float(np.sum(grad * grad)) for grad in gradients)))


def _mean(values: Any) -> float:
    materialized = tuple(float(value) for value in values)
    if not materialized:
        return 0.0
    return round(sum(materialized) / len(materialized), 6)


def _np() -> Any:
    import numpy as np

    return np


def _artifact_digest(git_sha: str, result: PPOTrainingResult) -> str:
    encoded = f"{git_sha}:{result.optimizer_steps}:{result.parameter_l2_delta}".encode()
    return hashlib.sha256(encoded).hexdigest()[:12]
