import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rescue_swarm.api.app import create_app
from rescue_swarm.eventlog import EventStore


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    store = EventStore(tmp_path / "api.sqlite3")
    with TestClient(create_app(store)) as test_client:
        yield test_client


@pytest.fixture
def golden_event() -> dict[str, Any]:
    return json.loads(Path("data/fixtures/golden_mission.json").read_text(encoding="utf-8"))


@pytest.fixture
def mission_payload(golden_event: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": golden_event["mission_id"],
        "name": "Mula-Mutha urban flood",
        "scenario_seed": 14062026,
        "dataset_revisions": {"flood-map": "fixture-v1"},
        "model_revisions": {"coordinator": "mock-v1"},
        "configuration": {"active_drones": 8},
        "simulation_only": True,
    }
