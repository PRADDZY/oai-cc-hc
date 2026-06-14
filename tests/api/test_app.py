from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient


def create_mission(client: TestClient, mission_payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/missions", json=mission_payload)
    assert response.status_code == 201
    return response.json()


def test_health_and_mission_crud(
    client: TestClient,
    mission_payload: dict[str, Any],
) -> None:
    assert client.get("/health").json() == {
        "status": "ok",
        "storage": "sqlite",
        "simulation_only": True,
    }

    created = create_mission(client, mission_payload)
    assert created["mission_id"] == mission_payload["mission_id"]
    assert created["simulation_only"] is True
    assert client.get("/missions").json() == [created]
    assert client.get(f"/missions/{created['mission_id']}").json() == created


def test_event_ingest_list_snapshot_and_replay_preserve_contract_labels(
    client: TestClient,
    mission_payload: dict[str, Any],
    golden_event: dict[str, Any],
) -> None:
    mission = create_mission(client, mission_payload)
    mission_id = mission["mission_id"]

    ingested = client.post(f"/missions/{mission_id}/events", json=golden_event)
    assert ingested.status_code == 201
    assert ingested.json()["sequence"] == 1
    assert ingested.json()["event"]["data_label"] == "simulated"
    assert ingested.json()["event"]["simulation_only"] is True

    now = datetime.now(UTC).isoformat()
    snapshot_event = deepcopy(golden_event)
    snapshot_event.update(
        {
            "event_id": "462e1c52-622d-4c9c-84c8-979b4aed5bd8",
            "event_type": "world.snapshot",
            "observed_at": now,
            "received_at": now,
            "payload": {
                "mission_id": mission_id,
                "sequence": 2,
                "generated_at": now,
                "flood_cells": [{"cell_id": "pune-01", "depth_m": 1.4}],
                "victim_hypotheses": [],
                "hazards": [{"kind": "fast_water"}],
                "drones": [{"drone_id": "drone-1", "status": "search"}],
                "communication_links": [],
                "data_freshness": {"telemetry": 0.5},
                "confidence": 0.82,
                "simulation_only": True,
            },
        }
    )
    assert client.post(f"/missions/{mission_id}/events", json=snapshot_event).status_code == 201

    events = client.get(f"/missions/{mission_id}/events").json()
    assert [item["sequence"] for item in events["events"]] == [1, 2]
    assert len(events["event_log_hash"]) == 64

    snapshot = client.get(f"/missions/{mission_id}/world").json()
    assert snapshot["sequence"] == 2
    assert snapshot["confidence"] == 0.82
    assert snapshot["simulation_only"] is True

    replay = client.get(f"/missions/{mission_id}/replay").json()
    assert replay["manifest"]["event_log_hash"] == events["event_log_hash"]
    assert replay["manifest"]["simulation_only"] is True
    assert [item["event"]["data_label"] for item in replay["events"]] == [
        "simulated",
        "simulated",
    ]


def test_policy_and_operator_paths_preserve_model_shield_and_human_labels(
    client: TestClient,
    mission_payload: dict[str, Any],
) -> None:
    mission_id = create_mission(client, mission_payload)["mission_id"]
    policy = {
        "mission_id": mission_id,
        "drone_id": "drone-1",
        "action": "aid_drop",
        "parameters": {"target": "shelter-2"},
        "confidence": 0.2,
        "coordination_message": [0.1, 0.2],
    }

    policy_response = client.post(
        f"/missions/{mission_id}/policy-proposals",
        json=policy,
    )
    assert policy_response.status_code == 201
    policy_result = policy_response.json()
    assert policy_result["proposal_event"]["event"]["data_label"] == "model_generated"
    assert policy_result["decision"]["status"] == "replaced"
    assert policy_result["decision"]["executed_action"] == "hold"
    assert policy_result["decision"]["shield_status"] is True
    assert policy_result["safety_event"]["event"]["payload"]["shield_status"] is True

    operator = {
        "mission_id": mission_id,
        "decision": "approve_hold",
        "operator_id": "operator-pune-1",
        "decided_at": datetime.now(UTC).isoformat(),
        "rationale": "Hold until the target is visually confirmed.",
        "human_approved": True,
    }
    operator_response = client.post(
        f"/missions/{mission_id}/operator-decisions",
        json=operator,
    )
    assert operator_response.status_code == 201
    assert operator_response.json()["event"]["payload"]["human_approved"] is True
    assert operator_response.json()["event"]["source"] == "human-operator"


def test_api_returns_not_found_conflict_and_mission_mismatch_errors(
    client: TestClient,
    mission_payload: dict[str, Any],
    golden_event: dict[str, Any],
) -> None:
    missing = "4e9968e6-c0d9-4f39-bf32-a94df9aa77c2"
    assert client.get(f"/missions/{missing}").status_code == 404
    assert client.get(f"/missions/{missing}/events").status_code == 404

    mission_id = create_mission(client, mission_payload)["mission_id"]
    assert client.post("/missions", json=mission_payload).status_code == 409
    assert client.post(f"/missions/{mission_id}/events", json=golden_event).status_code == 201
    assert client.post(f"/missions/{mission_id}/events", json=golden_event).status_code == 409

    mismatched = deepcopy(golden_event)
    mismatched["event_id"] = "5f659c35-b234-47dd-a8d5-3d29152bd5af"
    mismatched["mission_id"] = missing
    response = client.post(f"/missions/{mission_id}/events", json=mismatched)
    assert response.status_code == 422
    assert response.json()["detail"] == "mission_id does not match the path"
