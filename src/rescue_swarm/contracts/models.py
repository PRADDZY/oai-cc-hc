from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataLabel(StrEnum):
    LIVE = "live"
    DELAYED = "delayed"
    SIMULATED = "simulated"
    REPLAY = "replay"
    MODEL_GENERATED = "model_generated"


class ActionKind(StrEnum):
    SEARCH = "search"
    RELAY = "relay"
    AID_DROP = "aid_drop"
    MOVE = "move"
    HOLD = "hold"
    RETURN = "return"


class SafetyStatus(StrEnum):
    ALLOWED = "allowed"
    REPLACED = "replaced"
    REJECTED = "rejected"


class ObservationManifest(StrictModel):
    contract_version: str = "1.0"
    model_id: str
    model_revision: str
    modality: str
    bands: tuple[str, ...] = ()
    units: str
    normalization: str
    ground_sample_distance_m: float | None = Field(default=None, gt=0)
    crop_size: tuple[int, int]
    nodata_policy: str
    calibration_version: str
    observed_at: datetime
    valid_until: datetime
    validity_mask_present: bool = True

    @model_validator(mode="after")
    def validate_window(self) -> ObservationManifest:
        if self.valid_until <= self.observed_at:
            raise ValueError("valid_until must be later than observed_at")
        return self


class PerceptionSnapshot(StrictModel):
    contract_version: str = "1.0"
    snapshot_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    observed_at: datetime
    received_at: datetime
    data_label: DataLabel
    flood_probability: float = Field(ge=0, le=1)
    infrastructure_accessibility: dict[str, float] = Field(default_factory=dict)
    victim_hypotheses: tuple[dict[str, Any], ...] = ()
    uncertainty: float = Field(ge=0, le=1)
    source_age_seconds: float = Field(ge=0)
    validity: dict[str, bool] = Field(default_factory=dict)
    provenance: tuple[str, ...] = ()


class EventEnvelope(StrictModel):
    contract_version: str = "1.0"
    event_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    source: str
    event_type: str
    observed_at: datetime
    received_at: datetime
    geometry: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    uncertainty: float = Field(default=0, ge=0, le=1)
    provenance: tuple[str, ...] = ()
    ttl_seconds: int = Field(gt=0)
    data_label: DataLabel
    simulation_only: bool = True

    @property
    def is_stale(self) -> bool:
        age = (datetime.now(UTC) - self.observed_at).total_seconds()
        return age > self.ttl_seconds

    @model_validator(mode="after")
    def validate_timestamps(self) -> EventEnvelope:
        if self.received_at < self.observed_at:
            raise ValueError("received_at cannot be earlier than observed_at")
        return self


class MissionAssignment(StrictModel):
    contract_version: str = "1.0"
    assignment_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    drone_id: str
    role: ActionKind
    target: dict[str, Any]
    valid_from: datetime
    valid_until: datetime
    rationale: str
    requires_human_approval: bool = False


class PolicyOutput(StrictModel):
    contract_version: str = "1.0"
    mission_id: UUID
    drone_id: str
    action: ActionKind
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    recurrent_state_ref: str | None = None
    coordination_message: tuple[float, ...] = ()


class SafetyDecision(StrictModel):
    contract_version: str = "1.0"
    mission_id: UUID
    drone_id: str
    proposed_action: ActionKind
    status: SafetyStatus
    executed_action: ActionKind
    reason_code: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    shield_status: bool = True


class OperatorDecision(StrictModel):
    contract_version: str = "1.0"
    mission_id: UUID
    assignment_id: UUID | None = None
    decision: str
    operator_id: str
    decided_at: datetime
    rationale: str
    human_approved: bool


class CodexProposal(StrictModel):
    contract_version: str = "1.0"
    mission_id: UUID
    proposal_type: str
    summary: str
    rationale: str
    proposed_change: dict[str, Any]
    evidence_refs: tuple[str, ...] = ()
    model_generated: bool = True
    requires_human_approval: bool = True


class WorldStateSnapshot(StrictModel):
    contract_version: str = "1.0"
    mission_id: UUID
    sequence: int = Field(ge=0)
    generated_at: datetime
    flood_cells: tuple[dict[str, Any], ...] = ()
    victim_hypotheses: tuple[dict[str, Any], ...] = ()
    hazards: tuple[dict[str, Any], ...] = ()
    drones: tuple[dict[str, Any], ...] = ()
    communication_links: tuple[dict[str, Any], ...] = ()
    data_freshness: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    simulation_only: bool = True


class ReplayManifest(StrictModel):
    contract_version: str = "1.0"
    replay_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    scenario_seed: int
    dataset_revisions: dict[str, str]
    model_revisions: dict[str, str]
    configuration_hash: str
    event_log_hash: str
    created_at: datetime
    simulation_only: bool = True
