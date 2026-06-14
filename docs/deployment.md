# Cloudflare + Modal Deployment

This project deploys as a simulation-only decision-support system.

## Modal

Modal owns GPU-oriented training, evaluation, model artifact storage, and model
inference. Cloudflare should be the public caller; the browser should not call
Modal directly.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_modal_proof.ps1 -Stage smoke
```

For a stronger run, use `-Stage medium` after the smoke proof succeeds. The
script writes proof JSON/TXT files under `proof/` and deploys
`modal_apps/inference.py`.

Required Modal resources are created by the apps when missing:

- Volumes: `flood-rescue-data`, `flood-rescue-models`, `flood-rescue-runs`
- Apps: `flood-rescue-training`, `flood-rescue-inference`

Optional secrets:

- `huggingface-secret`
- `wandb-secret`
- `cloudflare-r2-secret`

## Cloudflare

The frontend is the Vite app in `apps/command-center`. The backend is the
Worker in `apps/worker`.

Create Cloudflare resources or replace placeholders in `apps/worker/wrangler.jsonc`:

- D1 database: `flood_rescue`
- R2 bucket: `flood-rescue-artifacts`
- KV namespace: `flood-rescue-model-aliases`
- Queue: `flood-rescue-observations`
- Durable Object class: `MissionRoom`

Set Worker secrets/vars:

```powershell
npm --prefix apps/worker exec --package wrangler@4.100.0 -- wrangler secret put MODAL_API_TOKEN
npm --prefix apps/worker run deploy
```

Set `MODAL_INFERENCE_URL` to the deployed Modal inference base URL and
`ALLOWED_ORIGIN` to the production Pages URL.

## Live Checks

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_live_deploy.ps1 `
  -WorkerUrl https://<worker-url>
```

The expected proof path is:

1. Modal writes `proof/release_gate.json`.
2. Modal inference exposes latest proof.
3. Cloudflare Worker exposes `/api/proof/latest`.
4. Frontend displays the proof panel while keeping `simulation only` visible.

## Screenshot Plan

Screenshots are optional. If needed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\capture_submission_evidence.ps1 `
  -FrontendUrl https://<pages-url>
```

Capture the command center, proof panel, active model IDs, and visible
simulation-only boundary.
