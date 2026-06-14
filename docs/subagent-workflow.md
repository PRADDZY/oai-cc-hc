# Subagent Implementation Workflow

The parent agent owns shared contracts, root manifests, dependency locks,
architecture decisions, integration, release claims, and the `main` branch.

Each bounded task follows:

```text
implementer -> specification review -> quality review -> parent integration
```

Concurrent implementers receive non-overlapping write leases. They must return:

- changed paths,
- contract version consumed,
- exact test commands and outputs,
- deterministic seeds and artifact provenance,
- limitations and simulation/truthfulness status.

Review agents are read-only. A failed review returns to a fresh repair agent
with an exclusive sequential lease. No worker self-declares the project ready.

Integration checkpoints:

1. Golden events round-trip through storage, simulator, and safety.
2. Simulator events reach API, WebSocket, and command center.
3. Perception features feed policies without oracle state.
4. Every policy proposal passes through the safety shield.
5. Replays, baselines, and reports reproduce from pinned fixtures.

