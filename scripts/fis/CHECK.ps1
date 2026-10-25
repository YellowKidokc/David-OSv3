$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Repo
try {
    python -m unittest discover -s tests -p test_fis_standalone.py -v
    if ($LASTEXITCODE -ne 0) { throw 'FIS foundation/independence acceptance failed' }
    python -m unittest discover -s tests -p test_fis_background_preferences.py -v
    if ($LASTEXITCODE -ne 0) { throw 'FIS background/preference acceptance failed' }
    node --check fis/static/app.js
    if ($LASTEXITCODE -ne 0) { throw 'FIS browser script syntax failed' }
} finally { Pop-Location }
