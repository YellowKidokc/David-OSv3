# FIS scan chain 2 - run after chain 1 (Cannon -> DONT TOUCH HTML -> 01_Axioms
# -> 00_Canonical_PRODUCTION_v1.0 -> Theophysics) has finished.
#
# The vault leads because the concept-registry join depends on it: 3,559 typed
# concepts have nothing to attach to until Z: is in the registry.
#
# Do NOT run this while chain 1 is still going - two writers on one SQLite file
# produce lock contention, not speed.
$ErrorActionPreference = 'Continue'
Set-Location 'D:\GitHub\David-OS\file-intelligence-system'

$targets = @(
    'Z:\__New\Theophysics.new',        # vault - unblocks the concept join
    'D:\00_STAGING',
    'D:\00_CANON_REFERENCE',
    'D:\evidence',
    'D:\Evidence_HQ',
    'D:\Theophysics Data Vault',
    'D:\AI-RESEARCH-AGENTS'
)

foreach ($t in $targets) {
    if (-not (Test-Path -LiteralPath $t)) {
        Write-Output "SKIP (missing): $t"
        continue
    }
    Write-Output ""
    Write-Output "================================================================"
    Write-Output "SCAN START  $t   $(Get-Date -Format 'HH:mm:ss')"
    Write-Output "================================================================"
    python fis_folder_memory.py $t --tree --html --doc-types --no-local-ai
    Write-Output "SCAN END    $t   exit=$LASTEXITCODE   $(Get-Date -Format 'HH:mm:ss')"
}

Write-Output ""
Write-Output "CHAIN 2 COMPLETE $(Get-Date -Format 'HH:mm:ss')"
Write-Output "Next: python fis_folder_memory.py <root> --doc-types-only   (repair legacy rows)"
Write-Output "Then: python fis_visualizer.py ; python fis_meq_graph.py"
