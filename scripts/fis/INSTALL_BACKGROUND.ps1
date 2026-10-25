param([string]$State, [string]$Python, [int]$Port=43107, [switch]$NoStart)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $State) { $State = Join-Path $Repo '.data\fis-live' }
if (-not $Python) { $Python = (Get-Command python.exe -ErrorAction Stop).Source }
$State = [IO.Path]::GetFullPath($State)
[void][IO.Directory]::CreateDirectory($State)
$scriptPath = Join-Path $PSScriptRoot 'FIS_BACKGROUND.ps1'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
foreach ($value in @($State,$Python,$scriptPath)) { if ($value.Contains('"')) { throw 'Invalid path' } }
$arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -State "{1}" -Python "{2}" -Port {3}' -f $scriptPath,$State,$Python,$Port
# The user's sign-in Startup folder needs no administrator or stored password.
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'FIS Background.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    $backup = Join-Path $State ('startup-backup-' + [Guid]::NewGuid().ToString('N') + '.lnk')
    Copy-Item -LiteralPath $shortcutPath -Destination $backup
}
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcutPath)
$link.TargetPath = $powershell
$link.Arguments = $arguments
$link.WorkingDirectory = $Repo
$link.WindowStyle = 7
$link.Description = 'FIS background file intelligence and notification-area review queue'
$link.Save()
$manifest = @{ installed_at=(Get-Date -Format o); startup=$shortcutPath; script=$scriptPath; python=$Python; state=$State; port=$Port; trigger='User sign-in'; requires_admin=$false }
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $State 'startup.json') -Encoding UTF8
if (-not $NoStart) { Start-Process -FilePath $powershell -ArgumentList $arguments -WorkingDirectory $Repo -WindowStyle Hidden }
$manifest | ConvertTo-Json
