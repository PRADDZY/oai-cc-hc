import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from rescue_swarm.contracts import DataLabel, EventEnvelope
from rescue_swarm.eventlog import (
    DuplicateEventError,
    EventIntegrityError,
    EventStore,
    MissionNotFoundError,
)


def make_event(mission_id: UUID, *, event_type: str, marker: int) -> EventEnvelope:
    now = datetime.now(UTC)
    return EventEnvelope(
        mission_id=mission_id,
        source="eventlog-test",
        event_type=event_type,
        observed_at=now,
        received_at=now,
        payload={"marker": marker},
        ttl_seconds=300,
        data_label=DataLabel.SIMULATED,
    )


@pytest.fixture
def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "events.sqlite3")
    event_store.initialize()
    return event_store


def test_uses_wal_and_replays_events_in_mission_order(store: EventStore) -> None:
    mission_id = uuid4()
    store.create_mission(mission_id=mission_id, name="ordered-replay")
    first, second = store.append_events(
        [
            make_event(mission_id, event_type="mission.started", marker=1),
            make_event(mission_id, event_type="telemetry.received", marker=2),
        ]
    )

    with sqlite3.connect(store.database_path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    replay = store.replay(mission_id)
    assert journal_mode == "wal"
    assert [record.sequence for record in replay.events] == [1, 2]
    assert [record.event.payload["marker"] for record in replay.events] == [1, 2]
    assert second.previous_hash == first.integrity_hash
    assert replay.event_log_hash == second.integrity_hash


def test_event_rows_are_append_only(store: EventStore) -> None:
    mission_id = uuid4()
    store.create_mission(mission_id=mission_id, name="immutable")
    record = store.append_event(make_event(mission_id, event_type="mission.started", marker=1))

    with sqlite3.connect(store.database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="events are append-only"):
            connection.execute(
                "UPDATE events SET envelope_json = ? WHERE event_id = ?",
                (json.dumps({"tampered": True}), str(record.event.event_id)),
            )


def test_integrity_verification_detects_tampering(store: EventStore) -> None:
    mission_id = uuid4()
    store.create_mission(mission_id=mission_id, name="tamper-check")
    store.append_event(make_event(mission_id, event_type="mission.started", marker=1))

    with sqlite3.connect(store.database_path) as connection:
        connection.execute("DROP TRIGGER events_no_update")
        connection.execute(
            "UPDATE events SET envelope_json = ? WHERE mission_id = ? AND sequence = 1",
            (json.dumps({"tampered": True}), str(mission_id)),
        )
        connection.commit()

    with pytest.raises(EventIntegrityError, match="integrity hash mismatch"):
        store.replay(mission_id)


def test_rejects_unknown_mission_and_duplicate_event_id(store: EventStore) -> None:
    mission_id = uuid4()
    event = make_event(mission_id, event_type="mission.started", marker=1)

    with pytest.raises(MissionNotFoundError):
        store.append_event(event)

    store.create_mission(mission_id=mission_id, name="duplicates")
    store.append_event(event)

    with pytest.raises(DuplicateEventError):
        store.append_event(event)
