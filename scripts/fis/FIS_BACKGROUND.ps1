param(
    [string]$State,
    [string]$Python,
    [int]$Port = 43107,
    [switch]$NoTray
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $State) { $State = Join-Path $Repo '.data\fis-live' }
if (-not $Python) { $Python = (Get-Command python.exe -ErrorAction Stop).Source }
$State = [IO.Path]::GetFullPath($State)
[void][IO.Directory]::CreateDirectory($State)
$mutex = New-Object Threading.Mutex($false, 'Local\FISStandaloneBackground')
if (-not $mutex.WaitOne(0)) { exit 0 }
$baseUrl = "http://127.0.0.1:$Port"
$child = $null
$logRoot = Join-Path $State 'logs'
[void][IO.Directory]::CreateDirectory($logRoot)
function Write-FisLog([string]$Message) {
    Add-Content -LiteralPath (Join-Path $logRoot 'supervisor.log') -Value ((Get-Date -Format o) + ' ' + $Message)
}
function Open-Fis([string]$Screen = 'home') { Start-Process "$baseUrl/#$Screen" }
function Get-FisHealth {
    try { return Invoke-RestMethod "$baseUrl/api/health" -TimeoutSec 3 } catch { return $null }
}
function Start-FisServer {
    $health = Get-FisHealth
    if ($health) {
        if ($health.application -ne 'fis-standalone' -or $health.state -ne $State) {
            throw "Port $Port is already used by another FIS state; refusing to adopt it."
        }
        return
    }
    if ($script:child -and -not $script:child.HasExited) {
        return # Keep one live child while it starts or handles a long request.
    }
    $stamp = [Guid]::NewGuid().ToString('N')
    # Start-Process joins ArgumentList; quote paths explicitly, with no interpolated shell code.
    if ($State.Contains('"') -or $Python.Contains('"')) { throw 'Invalid quoted path' }
    $processArgs = @('-m', 'fis', '--state', ('"' + $State + '"'), 'background', '--port', "$Port")
    $script:child = Start-Process -FilePath $Python -ArgumentList $processArgs -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logRoot "$stamp.out.log") -RedirectStandardError (Join-Path $logRoot "$stamp.err.log")
    Write-FisLog "Started server PID $($script:child.Id)"
}
function Invoke-FisAction([string]$Action) {
    $page = (Invoke-WebRequest "$baseUrl/" -UseBasicParsing -TimeoutSec 5).Content
    $token = [regex]::Match($page, 'name="fis-token" content="([^"]+)').Groups[1].Value
    if (-not $token) { throw 'Local FIS session unavailable' }
    $body = @{ action = $Action } | ConvertTo-Json -Compress
    Invoke-RestMethod "$baseUrl/api/action" -Method Post -Headers @{'X-FIS-Token'=$token; Origin=$baseUrl} -ContentType 'application/json' -Body $body -TimeoutSec 10 | Out-Null
}
try {
    Start-FisServer
    if ($NoTray) {
        while ($true) {
            Start-Sleep -Seconds 15
            try { Start-FisServer } catch { Write-FisLog $_.Exception.Message }
        }
    }
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [Windows.Forms.Application]::EnableVisualStyles()
    $icon = New-Object Windows.Forms.NotifyIcon
    $icon.Icon = [Drawing.SystemIcons]::Information
    $icon.Text = 'FIS - Background file intelligence'
    $icon.Visible = $true
    $menu = New-Object Windows.Forms.ContextMenuStrip
    $open = $menu.Items.Add('Open FIS')
    $open.add_Click({ Open-Fis 'home' })
    $review = $menu.Items.Add('Review rename proposals')
    $review.add_Click({ Open-Fis 'review' })
    $pause = $menu.Items.Add('Pause background work')
    $pause.add_Click({ try { Invoke-FisAction 'crawl-pause' } catch { Write-FisLog $_.Exception.Message } })
    $resume = $menu.Items.Add('Resume background work')
    $resume.add_Click({ try { Invoke-FisAction 'background-resume' } catch { Write-FisLog $_.Exception.Message } })
    [void]$menu.Items.Add('-')
    $exit = $menu.Items.Add('Exit until next sign-in')
    $exit.add_Click({
        try { Invoke-FisAction 'crawl-pause' } catch { Write-FisLog $_.Exception.Message }
        if ($script:child -and -not $script:child.HasExited) { Stop-Process -Id $script:child.Id }
        [Windows.Forms.Application]::Exit()
    })
    $icon.ContextMenuStrip = $menu
    $icon.add_DoubleClick({ Open-Fis 'home' })
    $icon.add_BalloonTipClicked({ Open-Fis 'review' })
    $script:lastNotice = [DateTime]::MinValue
    $script:lastSignature = ''
    $timer = New-Object Windows.Forms.Timer
    $timer.Interval = 15000
    $timer.add_Tick({
        try {
            Start-FisServer
            $q = Invoke-RestMethod "$baseUrl/api/notifications" -TimeoutSec 5
            $icon.Text = ("FIS: {0} names waiting - {1}" -f $q.renames, $q.background.status).Substring(0, [Math]::Min(63,("FIS: {0} names waiting - {1}" -f $q.renames, $q.background.status).Length))
            $review.Text = "Review rename proposals ($($q.renames))"
            $signature = "$($q.renames)|$($q.templates)|$($q.conflicts)|$($q.errors)"
            $total = $q.renames + $q.templates + $q.conflicts + $q.errors
            if ($total -gt 0 -and $signature -ne $script:lastSignature -and ((Get-Date)-$script:lastNotice).TotalMinutes -ge 15) {
                $icon.BalloonTipTitle = 'FIS has something for you to review'
                $icon.BalloonTipText = "$($q.renames) names, $($q.templates) template choices, $($q.conflicts + $q.errors) issues. Click to review. Nothing is renamed automatically."
                $icon.ShowBalloonTip(10000)
                $script:lastNotice = Get-Date
                $script:lastSignature = $signature
            }
        } catch { Write-FisLog $_.Exception.Message }
    })
    $timer.Start()
    Write-FisLog 'Notification-area icon and watchdog are running'
    [Windows.Forms.Application]::Run()
} catch {
    Write-FisLog $_.Exception.ToString()
    throw
} finally {
    if ($timer) { $timer.Dispose() }
    if ($icon) { $icon.Visible = $false; $icon.Dispose() }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
