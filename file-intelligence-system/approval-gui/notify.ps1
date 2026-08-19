# FIS toast notification -> click opens the Approval GUI.
# Call this from the daemon when new proposals land:
#   powershell -ExecutionPolicy Bypass -File notify.ps1 -Count 12
param([int]$Count = 0)

$url = "http://127.0.0.1:10778"
$title = "FIS: names awaiting approval"
$msg = if ($Count -gt 0) { "$Count new naming proposals are ready for review." }
       else { "Naming proposals are ready for review." }

try {
  # Windows 10/11 toast via WinRT
  [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
  [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
  $template = @"
<toast activationType="protocol" launch="$url">
  <visual><binding template="ToastGeneric">
    <text>$title</text><text>$msg</text>
  </binding></visual>
</toast>
"@
  $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
  $xml.LoadXml($template)
  $toast = New-Object Windows.UI.Notifications.ToastNotification($xml)
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("FIS").Show($toast)
} catch {
  # Fallback: just open the GUI
  Start-Process $url
}
