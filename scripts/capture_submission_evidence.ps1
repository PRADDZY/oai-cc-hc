param(
    [Parameter(Mandatory = $true)]
    [string]$FrontendUrl
)

$ErrorActionPreference = "Stop"

$shotDir = Join-Path $PSScriptRoot "..\proof\screenshots"
New-Item -ItemType Directory -Force $shotDir | Out-Null

npx playwright@latest screenshot --full-page $FrontendUrl (Join-Path $shotDir "command-center.png")

"Captured command center screenshot from $FrontendUrl at $(Get-Date -Format o)" |
    Set-Content -Path (Join-Path $shotDir "README.txt")
