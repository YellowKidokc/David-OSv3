$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Codex Script Hub.lnk")
$Shortcut.TargetPath = Join-Path $PSScriptRoot "launch_script_hub.bat"
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Codex Script Hub Launcher"
$Shortcut.Save()
Write-Host "Startup shortcut created/updated."
