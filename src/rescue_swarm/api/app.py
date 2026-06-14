from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ConfigDict

from rescue_swarm.contracts import (
    ActionKind,
    DataLabel,
    EventEnvelope,
    OperatorDecision,
    PolicyOutput,
    ReplayManifest,
    SafetyDecision,
    SafetyStatus,
    WorldStateSnapshot,
)
from rescue_swarm.eventlog import (
    DuplicateEventError,
    DuplicateMissionError,
    EventReplay,
    EventStore,
    MissionNotFoundError,
    MissionRecord,
    StoredEvent,
)


class MissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: UUID
    name: str
    scenario_seed: int = 0
    dataset_revisions: dict[str, str] = {}
    model_revisions: dict[str, str] = {}
    configuration: dict[str, Any] = {}
    simulation_only: bool = True


def create_app(store: EventStore | None = None) -> FastAPI:
    event_store = store or EventStore(Path("artifacts/events.sqlite3"))
    event_store.initialize()
    app = FastAPI(title="Flood Rescue Swarm", version="0.1.0")
    app.state.event_store = event_store

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "storage": "sqlite", "simulation_only": True}

    @app.post("/missions", status_code=status.HTTP_201_CREATED)
    def create_mission(payload: MissionCreate) -> dict[str, Any]:
        try:
            mission = event_store.create_mission(**payload.model_dump())
        except DuplicateMissionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _mission_json(mission)

    @app.get("/missions")
    def list_missions() -> list[dict[str, Any]]:
        return [_mission_json(mission) for mission in event_store.list_missions()]

    @app.get("/missions/{mission_id}")
    def get_mission(mission_id: UUID) -> dict[str, Any]:
        try:
            return _mission_json(event_store.get_mission(mission_id))
        except MissionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/missions/{mission_id}/events", status_code=status.HTTP_201_CREATED)
    def ingest_event(mission_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            event = EventEnvelope.model_validate(payload)
            if event.mission_id != mission_id:
                raise HTTPException(status_code=422, detail="mission_id does not match the path")
            return _stored_event_json(event_store.append_event(event))
        except HTTPException:
            raise
        except MissionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DuplicateEventError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/missions/{mission_id}/events")
    def list_events(
        mission_id: UUID,
        after_sequence: int = 0,
        limit: int = 1000,
    ) -> dict[str, Any]:
        try:
            replay = event_store.list_events(
                mission_id,
                after_sequence=after_sequence,
                limit=limit,
            )
            return _replay_json(replay)
        except MissionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/missions/{mission_id}/world")
    def current_world(mission_id: UUID) -> dict[str, Any]:
        try:
            latest = event_store.latest_event(mission_id, event_type="world.snapshot")
        except MissionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if latest is None:
            raise HTTPException(status_code=404, detail="world snapshot not found")
        return WorldStateSnapshot.model_validate(latest.event.payload).model_dump(mode="json")

    @app.get("/missions/{mission_id}/replay")
    def replay(mission_id: UUID) -> dict[str, Any]:
        try:
            mission = event_store.get_mission(mission_id)
            event_replay = event_store.replay(mission_id)
        except MissionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        manifest = ReplayManifest(
            mission_id=mission_id,
            scenario_seed=mission.scenario_seed,
            dataset_revisions=mission.dataset_revisions,
            model_revisions=mission.model_revisions,
            configuration_hash=_hash_json(mission.configuration),
            event_log_hash=event_replay.event_log_hash,
            created_at=datetime.now(UTC),
        )
        return {
            "manifest": manifest.model_dump(mode="json"),
            "events": [_stored_event_json(record) for record in event_replay.events],
        }

    @app.post("/missions/{mission_id}/policy-proposals", status_code=status.HTTP_201_CREATED)
    def policy_proposal(mission_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            policy = PolicyOutput.model_validate(payload)
            if policy.mission_id != mission_id:
                raise HTTPException(status_code=422, detail="mission_id does not match the path")
            event_store.get_mission(mission_id)
            proposed = event_store.append_event(
                _event_from_payload(
                    mission_id=mission_id,
                    source="model-policy",
                    event_type="policy.proposed",
                    payload=policy.model_dump(mode="json"),
                    data_label=DataLabel.MODEL_GENERATED,
                )
            )
            decision = _mock_safety_decision(policy)
            safety = event_store.append_event(
                _event_from_payload(
                    mission_id=mission_id,
                    source="deterministic-shield",
                    event_type="safety.decision",
                    payload=decision.model_dump(mode="json"),
                    data_label=DataLabel.MODEL_GENERATED,
                )
            )
            return {
                "proposal_event": _stored_event_json(proposed),
                "decision": decision.model_dump(mode="json"),
                "safety_event": _stored_event_json(safety),
            }
        except HTTPException:
            raise
        except MissionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/missions/{mission_id}/operator-decisions", status_code=status.HTTP_201_CREATED)
    def operator_decision(mission_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            decision = OperatorDecision.model_validate(payload)
            if decision.mission_id != mission_id:
                raise HTTPException(status_code=422, detail="mission_id does not match the path")
            event_store.get_mission(mission_id)
            return _stored_event_json(
                event_store.append_event(
                    _event_from_payload(
                        mission_id=mission_id,
                        source="human-operator",
                        event_type="operator.decision",
                        payload=decision.model_dump(mode="json"),
                        data_label=DataLabel.LIVE,
                    )
                )
            )
        except HTTPException:
            raise
        except MissionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.websocket("/ws/missions/{mission_id}")
    async def mission_socket(
        websocket: WebSocket,
        mission_id: UUID,
        after_sequence: int = 0,
    ) -> None:
        try:
            event_store.get_mission(mission_id)
        except MissionNotFoundError:
            await websocket.close(code=4404)
            return
        await websocket.accept()

        cursor = after_sequence
        try:
            while True:
                replay = event_store.list_events(mission_id, after_sequence=cursor)
                for record in replay.events:
                    await websocket.send_json(_stored_event_json(record))
                    cursor = record.sequence
                await asyncio.sleep(0.05)
        except WebSocketDisconnect:
            return

    return app


def _mission_json(mission: MissionRecord) -> dict[str, Any]:
    return {
        "mission_id": str(mission.mission_id),
        "name": mission.name,
        "scenario_seed": mission.scenario_seed,
        "dataset_revisions": mission.dataset_revisions,
        "model_revisions": mission.model_revisions,
        "configuration": mission.configuration,
        "created_at": mission.created_at.isoformat(),
        "simulation_only": mission.simulation_only,
    }


def _stored_event_json(record: StoredEvent) -> dict[str, Any]:
    return {
        "sequence": record.sequence,
        "event": record.event.model_dump(mode="json"),
        "previous_hash": record.previous_hash,
        "integrity_hash": record.integrity_hash,
        "appended_at": record.appended_at.isoformat(),
    }


def _replay_json(replay: EventReplay) -> dict[str, Any]:
    return {
        "mission_id": str(replay.mission_id),
        "event_log_hash": replay.event_log_hash,
        "events": [_stored_event_json(record) for record in replay.events],
    }


def _event_from_payload(
    *,
    mission_id: UUID,
    source: str,
    event_type: str,
    payload: dict[str, Any],
    data_label: DataLabel,
) -> EventEnvelope:
    now = datetime.now(UTC)
    return EventEnvelope(
        mission_id=mission_id,
        source=source,
        event_type=event_type,
        observed_at=now,
        received_at=now,
        payload=payload,
        ttl_seconds=300,
        data_label=data_label,
        uncertainty=0.0,
    )


def _mock_safety_decision(policy: PolicyOutput) -> SafetyDecision:
    if policy.action is ActionKind.AID_DROP:
        return SafetyDecision(
            mission_id=policy.mission_id,
            drone_id=policy.drone_id,
            proposed_action=policy.action,
            status=SafetyStatus.REPLACED,
            executed_action=ActionKind.HOLD,
            reason_code="human_confirmation_required",
            evidence={"requires_human_approval": True},
        )
    return SafetyDecision(
        mission_id=policy.mission_id,
        drone_id=policy.drone_id,
        proposed_action=policy.action,
        status=SafetyStatus.ALLOWED,
        executed_action=policy.action,
        reason_code="allowed_mock",
        evidence={},
    )


def _hash_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
