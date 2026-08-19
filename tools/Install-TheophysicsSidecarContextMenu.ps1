param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'
$Tool = Join-Path $PSScriptRoot 'sidecar_creator.py'
if (-not (Test-Path -LiteralPath $Tool)) { throw "Missing tool: $Tool" }
$Python = Join-Path (Split-Path -Parent (Get-Command python -ErrorAction Stop).Source) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw "pythonw.exe was not found beside Python: $Python" }
$Key = 'HKCU:\Software\Classes\*\shell\CreateTheophysicsSidecar'

if ($Uninstall) {
  Remove-Item -LiteralPath $Key -Recurse -Force -ErrorAction SilentlyContinue
  Write-Host 'Removed Explorer menu: Create Theophysics Sidecar'
  exit
}

New-Item -Path "$Key\command" -Force | Out-Null
Set-ItemProperty -LiteralPath $Key -Name '(default)' -Value 'Create Theophysics Sidecar'
Set-ItemProperty -LiteralPath "$Key\command" -Name '(default)' -Value ('"{0}" "{1}" "%1"' -f $Python, $Tool)
Write-Host 'Installed Explorer menu: Create Theophysics Sidecar'
