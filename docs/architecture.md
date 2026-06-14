# System Architecture

## Release boundary

This release is a simulation-only decision-support demonstrator. It does not
send commands to aircraft, claim operational readiness, or train model weights
during a mission.

The runtime is split into four authority layers:

1. The global recurrent policy proposes search, relay, aid-drop, hold, and
   return assignments.
2. A shared local recurrent policy proposes high-level movement objectives.
3. The deterministic safety shield allows, rejects, or replaces proposals.
4. Conventional flight control remains responsible for stabilization and
   waypoint following outside this repository.

Codex is advisory. Mission Copilot explains state and proposes options. Eval
Engineer proposes scenarios, tests, and configuration changes. Neither has an
actuator, deployment, model-registry, or safety-bypass capability.

## Runtime flow

```text
satellite / rainfall / map context        simulated drone telemetry
                  |                               |
                  v                               v
          perception snapshots ------------> event log
                  |                               |
                  +----------> world state <------+
                                  |
                          global orchestrator
                                  |
                         local shared policies
                                  |
                           safety shield
                                  |
                    simulated action execution
                                  |
                  API / WebSocket / command center
```

Satellite imagery updates strategic context and can be delayed. Tactical
decisions use local telemetry, detections, responder events, and explicit data
age. Missing inputs reduce confidence instead of silently becoming zeros.

## Timing contract

| Component | Target cadence |
| --- | --- |
| Conventional flight controller | Outside project, faster than 10 Hz |
| Local high-level policy | 5-10 Hz |
| Safety evaluation | Every proposal and critical telemetry event |
| World-state fusion | 1 Hz plus event-driven updates |
| Global orchestration | Every 5 seconds or on a critical event |
| Satellite and rainfall adapters | Independent polling with source timestamps |

## Failure behavior

- Low battery replaces the proposal with return-to-base.
- Stale localization replaces movement/drop proposals with hold.
- Command-link loss permits bounded local behavior, then relay recovery and
  return according to battery reserve.
- No-fly or out-of-bounds targets are rejected.
- Aid drops require a valid safe zone and human approval.
- Codex, satellite, weather, or dashboard failure cannot stop safety handling.

## Future ROS2 boundary

ROS2/PX4 integration is intentionally excluded from this release. A later
adapter should use lifecycle-managed nodes, reliable command QoS, best-effort
sensor QoS, timestamped ENU/NED frame conversion, transform lookup timeouts,
and non-blocking callbacks. The typed contracts in this repository form the
boundary; they are not ROS messages yet.

