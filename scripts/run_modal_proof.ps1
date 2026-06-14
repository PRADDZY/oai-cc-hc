param(
    [ValidateSet("smoke", "medium")]
    [string]$Stage = "smoke"
)

$ErrorActionPreference = "Stop"

$proofDir = Join-Path $PSScriptRoot "..\proof"
New-Item -ItemType Directory -Force $proofDir | Out-Null

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$dataProof = Join-Path $proofDir "data_prep.json"
$perceptionProof = Join-Path $proofDir "perception_eval.json"
$rlProof = Join-Path $proofDir "rl_eval.json"
$gateProof = Join-Path $proofDir "release_gate.json"

modal run --quiet --write-result $dataProof modal_apps/prepare_data.py --stage $Stage
modal run --quiet --write-result $perceptionProof modal_apps/perception_train.py --stage $Stage
modal run --quiet --write-result $rlProof modal_apps/rl_train.py --stage $Stage
modal run --quiet --write-result $gateProof modal_apps/evaluate.py --stage $Stage

foreach ($path in @($dataProof, $perceptionProof, $rlProof, $gateProof)) {
    if (-not (Test-Path $path)) {
        throw "Expected Modal proof file was not created: $path"
    }
}

modal deploy modal_apps/inference.py

"Modal proof generated for stage '$Stage' at $(Get-Date -Format o)" |
    Set-Content -Path (Join-Path $proofDir "modal_run_log.txt")
