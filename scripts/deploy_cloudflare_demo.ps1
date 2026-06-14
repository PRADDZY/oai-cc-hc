param(
    [string]$AccountId = $env:CLOUDFLARE_ACCOUNT_ID,
    [string]$PagesProjectName = "flood-rescue-command-center",
    [string]$PagesBranch = "main",
    [string]$WorkerUrl = $env:WORKER_URL,
    [string]$ModalInferenceUrl = $env:MODAL_INFERENCE_URL,
    [string]$ModalApiToken = $env:MODAL_API_TOKEN,
    [switch]$AllowAnyOrigin,
    [switch]$MinimalDemo,
    [switch]$SkipResourceProvision,
    [switch]$CaptureScreenshot
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$proofDir = Join-Path $repoRoot "proof"
$workerDir = Join-Path $repoRoot "apps\worker"
$commandCenterDir = Join-Path $repoRoot "apps\command-center"
$workerConfigPath = Join-Path $workerDir "wrangler.jsonc"
$tmpConfigPath = Join-Path $workerDir ".wrangler.deploy.generated.json"
$deployLogPath = Join-Path $proofDir "cloudflare_deploy_log.txt"
$deployEvidencePath = Join-Path $proofDir "cloudflare_deploy_evidence.json"

New-Item -ItemType Directory -Force $proofDir | Out-Null
Set-Content -Path $deployLogPath -Value "Cloudflare deploy started at $(Get-Date -Format o)"

function Add-DeployLog {
    param([string]$Message)
    Add-Content -Path $deployLogPath -Value "[$(Get-Date -Format o)] $Message"
}

function Invoke-Wrangler {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [string]$InputText,
        [string]$WorkingDirectory = $repoRoot
    )

    Add-DeployLog ("npx wrangler@4.100.0 " + ($Arguments -join " "))
    $npx = Get-Command npx.cmd,npx -ErrorAction Stop | Select-Object -First 1
    $previousAccountId = $env:CLOUDFLARE_ACCOUNT_ID
    if ($AccountId) {
        $env:CLOUDFLARE_ACCOUNT_ID = $AccountId
    }

    Push-Location $WorkingDirectory
    try {
        if ($InputText) {
            $output = $InputText | & $npx.Source "wrangler@4.100.0" @Arguments 2>&1 | ForEach-Object { "$_" }
        }
        else {
            $output = & $npx.Source "wrangler@4.100.0" @Arguments 2>&1 | ForEach-Object { "$_" }
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
        $env:CLOUDFLARE_ACCOUNT_ID = $previousAccountId
    }

    if ($output) {
        Add-Content -Path $deployLogPath -Value $output
    }
    if ($exitCode -ne 0) {
        throw "Wrangler failed ($exitCode): npx wrangler@4.100.0 $($Arguments -join ' ')"
    }

    return ($output -join [Environment]::NewLine)
}

function ConvertFrom-JsonFile {
    param([string]$Path)
    return Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
}

function Find-JsonItem {
    param(
        [object[]]$Items,
        [string]$Name
    )
    return $Items | Where-Object {
        $_.name -eq $Name -or $_.title -eq $Name -or $_.id -eq $Name
    } | Select-Object -First 1
}

function Ensure-D1Database {
    param([string]$Name)
    $items = @(Invoke-Wrangler -Arguments @("d1", "list", "--json") | ConvertFrom-Json)
    $existing = Find-JsonItem -Items $items -Name $Name
    if ($existing) {
        return [string]$existing.uuid
    }
    $created = Invoke-Wrangler -Arguments @("d1", "create", $Name, "--json") | ConvertFrom-Json
    foreach ($property in @("uuid", "id", "database_id")) {
        if ($created.$property) {
            return [string]$created.$property
        }
    }
    throw "Could not determine D1 database id for '$Name'."
}

function Ensure-KvNamespace {
    param([string]$Title)
    $items = @(Invoke-Wrangler -Arguments @("kv", "namespace", "list", "--json") | ConvertFrom-Json)
    $existing = Find-JsonItem -Items $items -Name $Title
    if ($existing) {
        return [string]$existing.id
    }
    $created = Invoke-Wrangler -Arguments @("kv", "namespace", "create", $Title, "--json") | ConvertFrom-Json
    foreach ($property in @("id", "namespace_id")) {
        if ($created.$property) {
            return [string]$created.$property
        }
    }
    throw "Could not determine KV namespace id for '$Title'."
}

function Ensure-R2Bucket {
    param([string]$Name)
    try {
        Invoke-Wrangler -Arguments @("r2", "bucket", "create", $Name) | Out-Null
        return "created"
    }
    catch {
        Add-DeployLog "R2 bucket '$Name' was not created; continuing because it may already exist. $($_.Exception.Message)"
        return "reused-or-unverified"
    }
}

function Ensure-Queue {
    param([string]$Name)
    try {
        Invoke-Wrangler -Arguments @("queues", "create", $Name) | Out-Null
        return "created"
    }
    catch {
        Add-DeployLog "Queue '$Name' was not created; continuing because it may already exist. $($_.Exception.Message)"
        return "reused-or-unverified"
    }
}

function Save-JsonFile {
    param(
        [object]$Value,
        [string]$Path
    )
    $Value | ConvertTo-Json -Depth 64 | Set-Content -Path $Path -Encoding utf8
}

if (-not $AccountId) {
    throw "Set CLOUDFLARE_ACCOUNT_ID or pass -AccountId before deploying Pages."
}

$config = ConvertFrom-JsonFile -Path $workerConfigPath
$pagesUrl = "https://$PagesProjectName.pages.dev"
$allowedOrigin = if ($AllowAnyOrigin) { "*" } else { $pagesUrl }

if (-not $config.vars) {
    $config | Add-Member -NotePropertyName vars -NotePropertyValue ([pscustomobject]@{})
}
$config.vars.ALLOWED_ORIGIN = $allowedOrigin
if ($ModalInferenceUrl) {
    $config.vars.MODAL_INFERENCE_URL = $ModalInferenceUrl.TrimEnd("/")
}

$resources = [ordered]@{
    d1 = $null
    kv = $null
    r2 = @()
    queues = @()
}

if ($MinimalDemo) {
    foreach ($property in @(
        "d1_databases",
        "r2_buckets",
        "kv_namespaces",
        "queues",
        "durable_objects",
        "migrations"
    )) {
        $config.PSObject.Properties.Remove($property)
    }
    $SkipResourceProvision = $true
    Add-DeployLog "Minimal demo mode enabled; unused stateful bindings were omitted."
}

if (-not $SkipResourceProvision) {
    foreach ($db in @($config.d1_databases)) {
        if (-not $db.database_id -or $db.database_id -like "replace-with-*") {
            $db.database_id = Ensure-D1Database -Name $db.database_name
        }
        $resources.d1 = $db.database_id
    }

    foreach ($namespace in @($config.kv_namespaces)) {
        if (-not $namespace.id -or $namespace.id -like "replace-with-*") {
            $namespaceTitle = if ($namespace.binding -eq "MODEL_ALIASES") { "flood-rescue-model-aliases" } else { $namespace.binding }
            $namespace.id = Ensure-KvNamespace -Title $namespaceTitle
        }
        $resources.kv = $namespace.id
    }

    foreach ($bucket in @($config.r2_buckets)) {
        $resources.r2 += [ordered]@{
            name = $bucket.bucket_name
            status = Ensure-R2Bucket -Name $bucket.bucket_name
        }
    }

    foreach ($producer in @($config.queues.producers)) {
        $resources.queues += [ordered]@{
            name = $producer.queue
            status = Ensure-Queue -Name $producer.queue
        }
    }
}
else {
    Add-DeployLog "Skipping Cloudflare resource provisioning by request."
}

Save-JsonFile -Value $config -Path $tmpConfigPath

$workerDeployOutput = Invoke-Wrangler -Arguments @("deploy", "--config", $tmpConfigPath) -WorkingDirectory $workerDir
if (-not $WorkerUrl) {
    $urlMatches = [regex]::Matches($workerDeployOutput, "https://[^\s`"']+workers\.dev[^\s`"']*")
    if ($urlMatches.Count -gt 0) {
        $WorkerUrl = $urlMatches[$urlMatches.Count - 1].Value.TrimEnd("/")
    }
}
if (-not $WorkerUrl) {
    throw "Worker deployed, but the production Worker URL could not be inferred. Re-run with -WorkerUrl https://<worker>.<subdomain>.workers.dev."
}
$WorkerUrl = $WorkerUrl.TrimEnd("/")

if ($ModalApiToken) {
    Invoke-Wrangler -Arguments @("secret", "put", "MODAL_API_TOKEN", "--config", $tmpConfigPath) -InputText $ModalApiToken -WorkingDirectory $workerDir | Out-Null
}
else {
    Add-DeployLog "MODAL_API_TOKEN not provided; Worker will use unauthenticated Modal calls or fallback."
}

Push-Location $commandCenterDir
try {
    npm ci
    $env:VITE_API_BASE_URL = $WorkerUrl
    npm run build
}
finally {
    Remove-Item Env:\VITE_API_BASE_URL -ErrorAction SilentlyContinue
    Pop-Location
}

$distDir = Join-Path $commandCenterDir "dist"
$pagesOutput = Invoke-Wrangler -Arguments @("pages", "deploy", $distDir, "--project-name=$PagesProjectName", "--branch", $PagesBranch) -WorkingDirectory $commandCenterDir
$pagesMatches = [regex]::Matches($pagesOutput, "https://[^\s`"']+\.pages\.dev[^\s`"']*")
$deployedPagesUrl = if ($pagesMatches.Count -gt 0) { $pagesMatches[$pagesMatches.Count - 1].Value.TrimEnd("/") } else { $pagesUrl }

& (Join-Path $PSScriptRoot "check_live_deploy.ps1") -WorkerUrl $WorkerUrl -FrontendUrl $deployedPagesUrl

if ($CaptureScreenshot) {
    & (Join-Path $PSScriptRoot "capture_submission_evidence.ps1") -FrontendUrl $deployedPagesUrl
}

$evidence = [ordered]@{
    generated_at = (Get-Date -Format o)
    account_id = $AccountId
    worker_url = $WorkerUrl
    pages_url = $deployedPagesUrl
    pages_project = $PagesProjectName
    pages_branch = $PagesBranch
    allowed_origin = $allowedOrigin
    modal_inference_url_configured = [bool]$ModalInferenceUrl
    modal_api_token_secret_configured = [bool]$ModalApiToken
    resources = $resources
    files = [ordered]@{
        deploy_log = $deployLogPath
        live_check = (Join-Path $proofDir "live_deploy_check.json")
        live_health = (Join-Path $proofDir "live_health.json")
        live_models = (Join-Path $proofDir "live_models.json")
        live_proof = (Join-Path $proofDir "live_proof.json")
    }
}
Save-JsonFile -Value $evidence -Path $deployEvidencePath
Add-DeployLog "Cloudflare deploy evidence written to $deployEvidencePath"
Remove-Item -LiteralPath $tmpConfigPath -ErrorAction SilentlyContinue

Write-Host "Worker: $WorkerUrl"
Write-Host "Pages:  $deployedPagesUrl"
Write-Host "Evidence: $deployEvidencePath"
