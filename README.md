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
uv run uvicorn rescue_swarm.api.app:create_app --factory --reload
```

The browser command center lives in `apps/command-center`.

## Cloudflare + Modal deployment

The intended hackathon deployment is:

- Cloudflare Pages: Vite command center frontend.
- Cloudflare Worker: public API gateway, CORS, cached proof fallback, and safety-gated proposal path.
- Modal: training proof jobs, model artifacts, evaluation, and live inference endpoints.

Modal CLI is used for training/evaluation proof:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_modal_proof.ps1 -Stage smoke
```

The script writes proof JSON/TXT under `proof/` and deploys the Modal inference
app. Use `-Stage medium` after the smoke run if time and GPU budget allow.

Cloudflare Worker checks:

```powershell
npm --prefix apps/worker install
npm --prefix apps/worker test
npm --prefix apps/worker run typecheck
```

Live deployment proof:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_live_deploy.ps1 `
  -WorkerUrl https://<worker-url>
```

## Training evidence

The submission should quote `proof/release_gate.json` after a Modal run:

- `simulation_only: true`
- trained perception proof from TerraMind S1 metadata
- trained swarm policy proof against a baseline
- zero executed safety violations
- active policy and perception artifact IDs

If screenshots are needed later, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\capture_submission_evidence.ps1 `
  -FrontendUrl https://<pages-url>
```

## Safety boundary

This project is for simulation-only decision support. The deployed system can
show live Modal-backed proposals, but no component is approved for real
emergency dispatch, aircraft control, or bypassing deterministic safety checks.
