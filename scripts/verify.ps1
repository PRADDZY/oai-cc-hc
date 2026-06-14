$ErrorActionPreference = "Stop"

uv sync --extra dev --locked
uv run ruff check .
uv run pytest

$commandCenter = Join-Path $PSScriptRoot "..\apps\command-center"
if (Test-Path (Join-Path $commandCenter "package-lock.json")) {
    Push-Location $commandCenter
    try {
        npm ci
        npm test -- --run
        npm run build
    }
    finally {
        Pop-Location
    }
}

