param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [string]$Token = $env:FIHUB_TOKEN
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Token)) {
    throw "Set FIHUB_TOKEN or pass -Token. Example: `$env:FIHUB_TOKEN='your-token'"
}

$BaseUrl = $BaseUrl.TrimEnd("/")
$headers = @{ "X-API-Token" = $Token }

function Invoke-HubJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,

        [Parameter(Mandatory = $true)]
        [string]$Path,

        [object]$Body = $null
    )

    $uri = "$BaseUrl$Path"
    if ($null -eq $Body) {
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
    }

    $json = $Body | ConvertTo-Json -Depth 20
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -ContentType "application/json" -Body $json
}

Write-Host "Testing Top-of-Mind headless hub at $BaseUrl"

$stats = Invoke-HubJson -Method Get -Path "/jobs/stats"
Write-Host "[OK] Token-protected health: /jobs/stats"

$clip = Invoke-HubJson -Method Post -Path "/clipboard/save" -Body @{
    body = "Synology hub smoke test clipboard $(Get-Date -Format o)"
    kind = "text"
    source_app = "test_synology_hub.ps1"
    folder = "Smoke Tests"
    tags = "synology,smoke-test"
    pinned = $false
}
Write-Host "[OK] Clipboard shelf write: item id $($clip.item.id)"

$message = Invoke-HubJson -Method Post -Path "/top-of-mind/messages" -Body @{
    source_id = "synology-smoke-test"
    source_label = "Synology Smoke Test"
    body = "Headless hub message route is alive."
    role = "system"
    folder = "Smoke Tests"
    wall = "main"
    metadata = @{ smoke_test = $true }
}
Write-Host "[OK] Top-of-Mind stream write: message id $($message.message.id)"

$agent = Invoke-HubJson -Method Post -Path "/agents/send" -Body @{
    agent_id = "codex"
    body = "Outbound agent route is alive."
    from_id = "synology-smoke-test"
    from_label = "Synology Smoke Test"
    folder = "Outbound"
    wall = "main"
    metadata = @{ smoke_test = $true }
}
Write-Host "[OK] Agent outbound route: target $($agent.target_agent_id)"

$memory = Invoke-HubJson -Method Post -Path "/memory/items" -Body @{
    title = "Synology hub smoke test"
    body = "Memory storage route is alive."
    source = "test_synology_hub.ps1"
    folder = "Smoke Tests"
    tags = @("synology", "smoke-test")
    metadata = @{ smoke_test = $true }
}
Write-Host "[OK] Memory route write: item id $($memory.memory_item.id)"

Write-Host ""
Write-Host "PASS: Synology headless hub is reachable, authenticated, and writing to SQLite-backed routes."
