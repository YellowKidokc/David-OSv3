param([Parameter(Mandatory=$true)][string]$SeriesRoot)

# One-time cleanup: remove the 5 bulk-copied subfolders from the explicitly supplied series folder
# These are entire production/support project trees (16K+ files, 2.9GB)
# that were incorrectly copied during the Nov 11 consolidation session.
# The 4 root-level series files are kept.
#
# DRY RUN by default — remove -WhatIf to execute

$folders = @(
    (Join-Path $SeriesRoot "_from_APOLOGETICS_01_GOD_IS")
    (Join-Path $SeriesRoot "_from_APOLOGETICS_DEBATE_MAP")
    (Join-Path $SeriesRoot "_from_APOLOGETICS_First_Principles")
    (Join-Path $SeriesRoot "_from_PRODUCTION_000_GOD")
    (Join-Path $SeriesRoot "_from_PRODUCTION_01_GOD_Character")
)

foreach ($f in $folders) {
    if (Test-Path $f) {
        $count = (Get-ChildItem $f -Recurse -File).Count
        $sizeMB = [math]::Round((Get-ChildItem $f -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
        Write-Host "REMOVE: $f ($count files, $sizeMB MB)" -ForegroundColor Yellow
        Remove-Item $f -Recurse -Force -WhatIf
    } else {
        Write-Host "SKIP: $f (not found)" -ForegroundColor Gray
    }
}

Write-Host "`nDone. Remove -WhatIf from Remove-Item to actually delete." -ForegroundColor Cyan
