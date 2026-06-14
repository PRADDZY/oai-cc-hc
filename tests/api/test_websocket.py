from copy import deepcopy
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.api.test_app import create_mission


def test_websocket_replays_cursor_then_streams_live_events_in_order(
    client: TestClient,
    mission_payload: dict[str, Any],
    golden_event: dict[str, Any],
) -> None:
    mission_id = create_mission(client, mission_payload)["mission_id"]
    assert client.post(f"/missions/{mission_id}/events", json=golden_event).status_code == 201

    with client.websocket_connect(f"/ws/missions/{mission_id}?after_sequence=0") as socket:
        first = socket.receive_json()
        assert first["sequence"] == 1

    second_event = deepcopy(golden_event)
    second_event["event_id"] = "81cab389-b1fd-479f-bc60-4ca0956091c8"
    second_event["event_type"] = "telemetry.received"
    assert client.post(f"/missions/{mission_id}/events", json=second_event).status_code == 201

    with client.websocket_connect(f"/ws/missions/{mission_id}?after_sequence=1") as socket:
        second = socket.receive_json()
        assert second["sequence"] == 2

        third_event = deepcopy(golden_event)
        third_event["event_id"] = "b347d7bf-7a44-49af-a212-78fdab407f30"
        third_event["event_type"] = "drone.position"
        assert client.post(f"/missions/{mission_id}/events", json=third_event).status_code == 201

        third = socket.receive_json()
        assert third["sequence"] == 3
        assert third["event"]["event_type"] == "drone.position"


def test_websocket_rejects_unknown_mission(client: TestClient) -> None:
    mission_id = "4e9968e6-c0d9-4f39-bf32-a94df9aa77c2"

    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/ws/missions/{mission_id}"):
            pass

    assert error.value.code == 4404
