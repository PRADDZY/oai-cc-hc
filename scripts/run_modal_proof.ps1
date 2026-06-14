param(
    [ValidateSet("smoke", "medium")]
    [string]$Stage = "smoke"
)

$ErrorActionPreference = "Stop"

$proofDir = Join-Path $PSScriptRoot "..\proof"
New-Item -ItemType Directory -Force $proofDir | Out-Null

modal run --write-result (Join-Path $proofDir "data_prep.json") modal_apps/prepare_data.py --stage $Stage
modal run --write-result (Join-Path $proofDir "perception_eval.json") modal_apps/perception_train.py --stage $Stage
modal run --write-result (Join-Path $proofDir "rl_eval.json") modal_apps/rl_train.py --stage $Stage
modal run --write-result (Join-Path $proofDir "release_gate.json") modal_apps/evaluate.py --stage $Stage

modal deploy modal_apps/inference.py

"Modal proof generated for stage '$Stage' at $(Get-Date -Format o)" |
    Set-Content -Path (Join-Path $proofDir "modal_run_log.txt")
