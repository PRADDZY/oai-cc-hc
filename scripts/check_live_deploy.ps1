param(
    [Parameter(Mandatory = $true)]
    [string]$WorkerUrl
)

$ErrorActionPreference = "Stop"

$proofDir = Join-Path $PSScriptRoot "..\proof"
New-Item -ItemType Directory -Force $proofDir | Out-Null

$base = $WorkerUrl.TrimEnd("/")
curl.exe -sS "$base/api/health" -o (Join-Path $proofDir "live_health.txt")
curl.exe -sS "$base/api/models/active" -o (Join-Path $proofDir "live_models.json")
curl.exe -sS "$base/api/proof/latest" -o (Join-Path $proofDir "live_proof.json")

"Checked $base at $(Get-Date -Format o)" |
    Set-Content -Path (Join-Path $proofDir "live_endpoint_check.txt")
