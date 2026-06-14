param(
    [Parameter(Mandatory = $true)]
    [string]$WorkerUrl,
    [string]$FrontendUrl
)

$ErrorActionPreference = "Stop"

$proofDir = Join-Path $PSScriptRoot "..\proof"
New-Item -ItemType Directory -Force $proofDir | Out-Null

$base = $WorkerUrl.TrimEnd("/")

function Invoke-LiveGet {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $status = curl.exe -sS -L -w "%{http_code}" -o $OutputPath $Url
    if ($LASTEXITCODE -ne 0) {
        throw "curl failed for $Name at $Url"
    }
    return [ordered]@{
        name = $Name
        url = $Url
        status = [int]$status
        output = $OutputPath
    }
}

$checks = @(
    Invoke-LiveGet -Name "worker_health" -Url "$base/api/health" -OutputPath (Join-Path $proofDir "live_health.json")
    Invoke-LiveGet -Name "active_models" -Url "$base/api/models/active" -OutputPath (Join-Path $proofDir "live_models.json")
    Invoke-LiveGet -Name "latest_proof" -Url "$base/api/proof/latest" -OutputPath (Join-Path $proofDir "live_proof.json")
)

if ($FrontendUrl) {
    $checks += Invoke-LiveGet -Name "frontend" -Url $FrontendUrl.TrimEnd("/") -OutputPath (Join-Path $proofDir "live_frontend.html")
}

$failed = @($checks | Where-Object { $_.status -lt 200 -or $_.status -ge 300 })
if ($failed.Count -gt 0) {
    $failedNames = ($failed | ForEach-Object { "$($_.name)=$($_.status)" }) -join ", "
    throw "Live deploy check failed: $failedNames"
}

$evidence = [ordered]@{
    checked_at = (Get-Date -Format o)
    worker_url = $base
    frontend_url = $FrontendUrl
    checks = $checks
}

$evidence | ConvertTo-Json -Depth 8 |
    Set-Content -Path (Join-Path $proofDir "live_deploy_check.json") -Encoding utf8

"Checked $base at $(Get-Date -Format o)" |
    Set-Content -Path (Join-Path $proofDir "live_endpoint_check.txt")
