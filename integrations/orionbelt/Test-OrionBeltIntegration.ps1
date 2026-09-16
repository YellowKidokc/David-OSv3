[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ExpectedTag = 'v2.26.0'
$ExpectedCommit = '3a35445437deecb924fdb6eab28e6a8acefd935a'
$OrionRoot = 'D:\GitHub\orionbelt-semantic-layer'
$CanonRoot = 'D:\GitHub\Faith-through-physics-atoms'
$CanonDatabase = Join-Path $CanonRoot '_canon\index.sqlite'
$IntegrationRoot = $PSScriptRoot

$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    $checks.Add([pscustomobject]@{
        Check = $Name
        Passed = $Passed
        Detail = $Detail
    })
}

Add-Check 'OrionBelt checkout exists' (Test-Path -LiteralPath $OrionRoot) $OrionRoot
Add-Check 'Upstream license retained' (Test-Path -LiteralPath (Join-Path $OrionRoot 'LICENSE')) 'BSL-1.1 file expected'
Add-Check 'Canon repository exists' (Test-Path -LiteralPath $CanonRoot) $CanonRoot
Add-Check 'Canon database located' (Test-Path -LiteralPath $CanonDatabase) 'Existence only; database is not opened'
Add-Check 'Integration mapping exists' (Test-Path -LiteralPath (Join-Path $IntegrationRoot 'canon_projection.mapping.yaml')) 'Specification-only mapping'

if (Test-Path -LiteralPath (Join-Path $OrionRoot '.git')) {
    $head = (git -C $OrionRoot rev-parse HEAD).Trim()
    $tags = @(git -C $OrionRoot tag --points-at HEAD)
    Add-Check 'Pinned commit' ($head -eq $ExpectedCommit) "expected=$ExpectedCommit actual=$head"
    Add-Check 'Pinned tag' ($tags -contains $ExpectedTag) "expected=$ExpectedTag actual=$($tags -join ',')"
}
else {
    Add-Check 'Pinned commit' $false 'No .git directory found'
    Add-Check 'Pinned tag' $false 'No .git directory found'
}

$configPath = Join-Path $IntegrationRoot 'integration.json'
try {
    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Add-Check 'Configuration parses' $true $configPath
    Add-Check 'Canon writes forbidden' ($config.capabilities.canon_write -eq 'FORBIDDEN') "canon_write=$($config.capabilities.canon_write)"
    Add-Check 'Direct live connection disabled' ($config.canon.connection_policy -eq 'NO_DIRECT_CONNECTION_UNTIL_APPROVED') "policy=$($config.canon.connection_policy)"
}
catch {
    Add-Check 'Configuration parses' $false $_.Exception.Message
}

$checks | Format-Table -AutoSize

if ($checks.Where({ -not $_.Passed }).Count -gt 0) {
    throw 'OrionBelt integration preflight failed. No service was started and no database was opened.'
}

Write-Host ''
Write-Host 'PASS: OrionBelt source is pinned and the David-OS integration remains specification-only/read-only.' -ForegroundColor Green
Write-Host 'No package was installed, no service was started, and Canon SQLite was not opened.'
