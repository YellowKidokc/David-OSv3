# Explicit provisioning only. AGENT_TOKENS is the worker's token -> agent JSON map.
# Credentials are supplied through the process environment; no local token file.
$ErrorActionPreference = "Stop"
if (-not $env:AGENT_TOKENS) { throw "Set AGENT_TOKENS in the environment first." }
if (-not $env:AI_HUB_PROJECT) { throw "Set AI_HUB_PROJECT to the worker project folder." }
$null = $env:AGENT_TOKENS | ConvertFrom-Json
Push-Location $env:AI_HUB_PROJECT
try {
    $env:AGENT_TOKENS | npx --yes wrangler@4 secret put AGENT_TOKENS
    if ($LASTEXITCODE -ne 0) { throw "Secret update failed." }
} finally { Pop-Location }
