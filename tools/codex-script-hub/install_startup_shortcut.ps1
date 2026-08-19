$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Codex Script Hub.lnk")
$Shortcut.TargetPath = "D:\GitHub\David-OS\tools\codex-script-hub\launch_script_hub.bat"
$Shortcut.WorkingDirectory = "D:\GitHub\David-OS\tools\codex-script-hub"
$Shortcut.Description = "Codex Script Hub Launcher"
$Shortcut.Save()
Write-Host "Startup shortcut created/updated."
