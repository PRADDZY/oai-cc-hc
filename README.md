# Flood Rescue Swarm

A simulation-only flood-response demonstrator built around hierarchical
multi-agent reinforcement learning. Eight drones coordinate search, radio
relay, and aid-drop missions from delayed Earth-observation context and live
simulated telemetry.

The project deliberately separates:

- overhead flood perception fine-tuning,
- low-altitude victim perception,
- procedural multi-agent policy training,
- deterministic operational safety,
- and human/Codex advisory interfaces.

No component in this repository is approved for real emergency dispatch or
physical aircraft control.

## Quick start

```powershell
uv sync --extra dev
uv run pytest
uv run uvicorn rescue_swarm.api.app:app --reload
```

The browser command center lives in `apps/command-center`.

