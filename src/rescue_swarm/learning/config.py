from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PPOTrainingConfig:
    clip_param: float = 0.2
    entropy_coeff: float = 0.01
    vf_loss_coeff: float = 0.5
    grad_clip: float = 0.5
    gamma: float = 0.99
    lambda_: float = 0.95
    use_gae: bool = True
    normalize_advantages: bool = True
    central_critic: bool = True
    train_batch_size: int = 4096
    minibatch_size: int = 512

    def validate(self) -> None:
        if not 0 < self.clip_param <= 0.3:
            raise ValueError("PPO clip_param must constrain policy updates")
        if self.entropy_coeff <= 0:
            raise ValueError("entropy_coeff must encourage exploration")
        if self.grad_clip <= 0:
            raise ValueError("grad_clip is required for RL stability")
        if not self.normalize_advantages:
            raise ValueError("advantages must be normalized")
        if not self.central_critic:
            raise ValueError("hierarchical MARL requires centralized critics during training")

    def to_rllib_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "framework": "torch",
            "clip_param": self.clip_param,
            "entropy_coeff": self.entropy_coeff,
            "vf_loss_coeff": self.vf_loss_coeff,
            "grad_clip": self.grad_clip,
            "gamma": self.gamma,
            "lambda": self.lambda_,
            "use_gae": self.use_gae,
            "train_batch_size": self.train_batch_size,
            "sgd_minibatch_size": self.minibatch_size,
            "model": {"use_lstm": True, "max_seq_len": 32},
        }


@dataclass(frozen=True, slots=True)
class CurriculumStage:
    name: str
    active_drones: int
    description: str

    def __post_init__(self) -> None:
        if not 2 <= self.active_drones <= 8:
            raise ValueError("training stages must stay within 2-8 active drones")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_training_plan() -> tuple[CurriculumStage, ...]:
    return (
        CurriculumStage("debug-two-drone", 2, "Validate rewards, masks, and scripts."),
        CurriculumStage("shared-local-four", 4, "Train local shared policy."),
        CurriculumStage("hierarchical-eight", 8, "Train global orchestrator plus local policy."),
    )

