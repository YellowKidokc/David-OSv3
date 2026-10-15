"""Windows toast notifications for 03_CLASSIFY. Clicking the toast opens `open_path` (a file or URL).

Uses the WinRT toast API through PowerShell, so nothing extra is installed. Never raises:
a notification that fails must not break the step that sent it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

# PowerShell's own app id: registered on every Windows install, so toasts show without setup.
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

PS = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml([Console]::In.ReadToEnd())
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('%s').Show(
    [Windows.UI.Notifications.ToastNotification]::new($xml))
""" % APP_ID


def toast(title: str, body: str, open_path: str | Path | None = None) -> bool:
    if sys.platform != "win32":
        return False
    launch = ""
    if open_path:
        target = str(open_path)
        if "://" not in target:
            target = Path(target).resolve().as_uri()
        launch = f' activationType="protocol" launch="{escape(target, {chr(34): "&quot;"})}"'
    xml = (f"<toast{launch}><visual><binding template=\"ToastGeneric\">"
           f"<text>{escape(title)}</text><text>{escape(body)}</text>"
           f"</binding></visual></toast>")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
                       input=xml, text=True, capture_output=True, timeout=20,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    toast(sys.argv[1] if len(sys.argv) > 1 else "03_CLASSIFY",
          sys.argv[2] if len(sys.argv) > 2 else "Test notification",
          sys.argv[3] if len(sys.argv) > 3 else None)
