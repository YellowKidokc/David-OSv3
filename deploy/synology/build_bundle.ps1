param(
    [string]$OutputRoot = "dist"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$apiRoot = Join-Path $repoRoot "api"

if (-not (Test-Path (Join-Path $apiRoot "Dockerfile"))) {
    throw "Missing API Dockerfile at $apiRoot"
}

$distRoot = Join-Path $scriptDir $OutputRoot
$bundleRoot = Join-Path $distRoot "top-of-mind-api"
$bundleApi = Join-Path $bundleRoot "apps\api"
$zipPath = Join-Path $distRoot "top-of-mind-api-synology-bundle.zip"
$resolvedDistRoot = [System.IO.Path]::GetFullPath($distRoot)
$resolvedBundleRoot = [System.IO.Path]::GetFullPath($bundleRoot)

if (-not $resolvedBundleRoot.StartsWith($resolvedDistRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean a bundle path outside the Synology dist folder: $resolvedBundleRoot"
}

if (Test-Path $bundleRoot) {
    Remove-Item -LiteralPath $bundleRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $bundleApi -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $bundleRoot "data") -Force | Out-Null

$apiItems = @(
    "pyproject.toml",
    "README.md",
    "Dockerfile",
    "file_intelligence_hub",
    "config",
    "schemas"
)

foreach ($item in $apiItems) {
    $source = Join-Path $apiRoot $item
    if (Test-Path $source) {
        Copy-Item -LiteralPath $source -Destination $bundleApi -Recurse -Force
    }
}

Get-ChildItem -Path $bundleRoot -Directory -Recurse -Force |
    Where-Object { $_.Name -in @("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache") } |
    Remove-Item -Recurse -Force
Get-ChildItem -Path $bundleRoot -File -Recurse -Force -Include "*.pyc", "*.pyo", "*.pyd" |
    Remove-Item -Force

Copy-Item -LiteralPath (Join-Path $scriptDir "docker-compose.bundle.yml") -Destination (Join-Path $bundleRoot "docker-compose.yml") -Force
Copy-Item -LiteralPath (Join-Path $scriptDir ".env.example") -Destination (Join-Path $bundleRoot ".env.example") -Force
Copy-Item -LiteralPath (Join-Path $scriptDir "BUNDLE_README.md") -Destination (Join-Path $bundleRoot "README.md") -Force
Copy-Item -LiteralPath (Join-Path $scriptDir "test_synology_hub.ps1") -Destination (Join-Path $bundleRoot "test_synology_hub.ps1") -Force

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $bundleRoot "*") -DestinationPath $zipPath -Force

Write-Host "Synology bundle ready:"
Write-Host "  Folder: $bundleRoot"
Write-Host "  Zip:    $zipPath"
