from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from rescue_swarm.contracts import EventEnvelope

GENESIS_HASH = "0" * 64


class EventStoreError(RuntimeError):
    """Base exception for event storage failures."""


class MissionNotFoundError(EventStoreError):
    """Raised when a mission does not exist."""


class DuplicateMissionError(EventStoreError):
    """Raised when a mission identifier already exists."""


class DuplicateEventError(EventStoreError):
    """Raised when an event identifier already exists."""


class EventIntegrityError(EventStoreError):
    """Raised when the persisted hash chain cannot be verified."""


@dataclass(frozen=True, slots=True)
class MissionRecord:
    mission_id: UUID
    name: str
    scenario_seed: int
    dataset_revisions: dict[str, str]
    model_revisions: dict[str, str]
    configuration: dict[str, Any]
    created_at: datetime
    simulation_only: bool


@dataclass(frozen=True, slots=True)
class StoredEvent:
    sequence: int
    event: EventEnvelope
    previous_hash: str
    integrity_hash: str
    appended_at: datetime


@dataclass(frozen=True, slots=True)
class EventReplay:
    mission_id: UUID
    events: tuple[StoredEvent, ...]
    event_log_hash: str


class EventStore:
    """SQLite-backed append-only mission event storage."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path) if database_path != ":memory:" else ":memory:"
        self._lock = threading.RLock()
        self._memory_connection: sqlite3.Connection | None = None

    def initialize(self) -> None:
        if isinstance(self.database_path, Path):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    scenario_seed INTEGER NOT NULL,
                    dataset_revisions_json TEXT NOT NULL,
                    model_revisions_json TEXT NOT NULL,
                    configuration_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    mission_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_id TEXT NOT NULL UNIQUE,
                    envelope_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL,
                    appended_at TEXT NOT NULL,
                    PRIMARY KEY (mission_id, sequence),
                    FOREIGN KEY (mission_id) REFERENCES missions(mission_id)
                );

                CREATE INDEX IF NOT EXISTS events_mission_type
                    ON events(mission_id, sequence);

                CREATE TRIGGER IF NOT EXISTS events_no_update
                BEFORE UPDATE ON events
                BEGIN
                    SELECT RAISE(ABORT, 'events are append-only');
                END;

                CREATE TRIGGER IF NOT EXISTS events_no_delete
                BEFORE DELETE ON events
                BEGIN
                    SELECT RAISE(ABORT, 'events are append-only');
                END;
                """
            )

    def close(self) -> None:
        with self._lock:
            if self._memory_connection is not None:
                self._memory_connection.close()
                self._memory_connection = None

    def create_mission(
        self,
        *,
        mission_id: UUID,
        name: str,
        scenario_seed: int = 0,
        dataset_revisions: dict[str, str] | None = None,
        model_revisions: dict[str, str] | None = None,
        configuration: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        simulation_only: bool = True,
    ) -> MissionRecord:
        created_at = created_at or datetime.now(UTC)
        values = (
            str(mission_id),
            name,
            scenario_seed,
            self._canonical_json(dataset_revisions or {}),
            self._canonical_json(model_revisions or {}),
            self._canonical_json(configuration or {}),
            created_at.isoformat(),
            int(simulation_only),
        )

        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO missions (
                        mission_id,
                        name,
                        scenario_seed,
                        dataset_revisions_json,
                        model_revisions_json,
                        configuration_json,
                        created_at,
                        simulation_only
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise DuplicateMissionError(f"mission {mission_id} already exists") from error

        return MissionRecord(
            mission_id=mission_id,
            name=name,
            scenario_seed=scenario_seed,
            dataset_revisions=dataset_revisions or {},
            model_revisions=model_revisions or {},
            configuration=configuration or {},
            created_at=created_at,
            simulation_only=simulation_only,
        )

    def get_mission(self, mission_id: UUID) -> MissionRecord:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM missions WHERE mission_id = ?",
                (str(mission_id),),
            ).fetchone()

        if row is None:
            raise MissionNotFoundError(f"mission {mission_id} was not found")
        return self._row_to_mission(row)

    def list_missions(self) -> tuple[MissionRecord, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM missions ORDER BY created_at, mission_id"
            ).fetchall()
        return tuple(self._row_to_mission(row) for row in rows)

    def append_event(self, event: EventEnvelope) -> StoredEvent:
        return self.append_events([event])[0]

    def append_events(self, events: Iterable[EventEnvelope]) -> tuple[StoredEvent, ...]:
        pending = tuple(events)
        if not pending:
            return ()

        mission_id = pending[0].mission_id
        if any(event.mission_id != mission_id for event in pending):
            raise ValueError("all events in an atomic append must share a mission_id")

        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if (
                    connection.execute(
                        "SELECT 1 FROM missions WHERE mission_id = ?",
                        (str(mission_id),),
                    ).fetchone()
                    is None
                ):
                    raise MissionNotFoundError(f"mission {mission_id} was not found")

                row = connection.execute(
                    """
                    SELECT sequence, integrity_hash
                    FROM events
                    WHERE mission_id = ?
                    ORDER BY sequence DESC
                    LIMIT 1
                    """,
                    (str(mission_id),),
                ).fetchone()
                sequence = 0 if row is None else int(row["sequence"])
                previous_hash = GENESIS_HASH if row is None else str(row["integrity_hash"])
                stored: list[StoredEvent] = []

                for event in pending:
                    sequence += 1
                    envelope_json = self._canonical_json(event.model_dump(mode="json"))
                    integrity_hash = self._event_hash(
                        mission_id=mission_id,
                        sequence=sequence,
                        previous_hash=previous_hash,
                        envelope_json=envelope_json,
                    )
                    appended_at = datetime.now(UTC)
                    connection.execute(
                        """
                        INSERT INTO events (
                            mission_id,
                            sequence,
                            event_id,
                            envelope_json,
                            previous_hash,
                            integrity_hash,
                            appended_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(mission_id),
                            sequence,
                            str(event.event_id),
                            envelope_json,
                            previous_hash,
                            integrity_hash,
                            appended_at.isoformat(),
                        ),
                    )
                    stored.append(
                        StoredEvent(
                            sequence=sequence,
                            event=event,
                            previous_hash=previous_hash,
                            integrity_hash=integrity_hash,
                            appended_at=appended_at,
                        )
                    )
                    previous_hash = integrity_hash

                connection.commit()
                return tuple(stored)
            except MissionNotFoundError:
                connection.rollback()
                raise
            except sqlite3.IntegrityError as error:
                connection.rollback()
                if "event_id" in str(error) or "UNIQUE constraint failed" in str(error):
                    raise DuplicateEventError("event_id already exists") from error
                raise EventStoreError("event append failed") from error
            except Exception:
                connection.rollback()
                raise

    def list_events(
        self,
        mission_id: UUID,
        *,
        after_sequence: int = 0,
        limit: int = 1000,
    ) -> EventReplay:
        replay = self.replay(mission_id)
        events = tuple(
            record for record in replay.events if record.sequence > after_sequence
        )[:limit]
        return EventReplay(
            mission_id=mission_id,
            events=events,
            event_log_hash=replay.event_log_hash,
        )

    def latest_event(
        self,
        mission_id: UUID,
        *,
        event_type: str,
    ) -> StoredEvent | None:
        replay = self.replay(mission_id)
        return next(
            (
                record
                for record in reversed(replay.events)
                if record.event.event_type == event_type
            ),
            None,
        )

    def replay(self, mission_id: UUID) -> EventReplay:
        self.get_mission(mission_id)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT sequence, envelope_json, previous_hash, integrity_hash, appended_at
                FROM events
                WHERE mission_id = ?
                ORDER BY sequence
                """,
                (str(mission_id),),
            ).fetchall()

        previous_hash = GENESIS_HASH
        stored: list[StoredEvent] = []
        for expected_sequence, row in enumerate(rows, start=1):
            sequence = int(row["sequence"])
            persisted_previous_hash = str(row["previous_hash"])
            envelope_json = str(row["envelope_json"])
            expected_hash = self._event_hash(
                mission_id=mission_id,
                sequence=sequence,
                previous_hash=persisted_previous_hash,
                envelope_json=envelope_json,
            )

            if sequence != expected_sequence:
                raise EventIntegrityError(
                    f"event sequence gap at {expected_sequence}: found {sequence}"
                )
            if persisted_previous_hash != previous_hash:
                raise EventIntegrityError(f"previous hash mismatch at sequence {sequence}")
            if str(row["integrity_hash"]) != expected_hash:
                raise EventIntegrityError(f"integrity hash mismatch at sequence {sequence}")

            try:
                event = EventEnvelope.model_validate_json(envelope_json)
            except ValueError as error:
                raise EventIntegrityError(
                    f"invalid event envelope at sequence {sequence}"
                ) from error
            if event.mission_id != mission_id:
                raise EventIntegrityError(f"mission mismatch at sequence {sequence}")

            stored.append(
                StoredEvent(
                    sequence=sequence,
                    event=event,
                    previous_hash=persisted_previous_hash,
                    integrity_hash=expected_hash,
                    appended_at=datetime.fromisoformat(str(row["appended_at"])),
                )
            )
            previous_hash = expected_hash

        return EventReplay(
            mission_id=mission_id,
            events=tuple(stored),
            event_log_hash=previous_hash,
        )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            if self.database_path == ":memory:":
                if self._memory_connection is None:
                    self._memory_connection = self._new_connection(":memory:")
                yield self._memory_connection
                return

            connection = self._new_connection(str(self.database_path))
            try:
                yield connection
            finally:
                connection.close()

    @staticmethod
    def _new_connection(database_path: str) -> sqlite3.Connection:
        connection = sqlite3.connect(
            database_path,
            isolation_level=None,
            check_same_thread=False,
            timeout=5,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @classmethod
    def _event_hash(
        cls,
        *,
        mission_id: UUID,
        sequence: int,
        previous_hash: str,
        envelope_json: str,
    ) -> str:
        material = f"{mission_id}:{sequence}:{previous_hash}:{envelope_json}".encode()
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    def _row_to_mission(row: sqlite3.Row) -> MissionRecord:
        return MissionRecord(
            mission_id=UUID(str(row["mission_id"])),
            name=str(row["name"]),
            scenario_seed=int(row["scenario_seed"]),
            dataset_revisions=json.loads(str(row["dataset_revisions_json"])),
            model_revisions=json.loads(str(row["model_revisions_json"])),
            configuration=json.loads(str(row["configuration_json"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            simulation_only=bool(row["simulation_only"]),
        )
