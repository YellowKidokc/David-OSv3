# bridge_listener.ps1 - HTTP front door for the AI Input Overlay
# Receives POST /send, normalizes JSON, writes it to the overlay's _inbox folder.
# Run alongside ai_input_overlay.ahk (start_bridge.bat launches both).
param([int]$Port = 8765, [string]$Token = "davidos-bridge-2026")
$inbox = Join-Path $PSScriptRoot "_inbox"
New-Item -ItemType Directory -Path $inbox -Force | Out-Null
$allowedTargets = @("claude", "codex", "gpt", "kimi")
$l = New-Object Net.HttpListener
$l.Prefixes.Add("http://+:$Port/")
try { $l.Start() } catch {
    Write-Host "Bind failed. Run once as admin:  netsh http add urlacl url=http://+:$Port/ user=Everyone"
    $l = New-Object Net.HttpListener; $l.Prefixes.Add("http://localhost:$Port/"); $l.Start()
    Write-Host "Fell back to localhost-only."
}
Write-Host "Bridge listener up on port $Port -> $inbox"
while ($true) {
    $c = $l.GetContext(); $q = $c.Request; $r = $c.Response
    try {
        if ($q.Url.AbsolutePath -eq "/health") {
            $b = [Text.Encoding]::UTF8.GetBytes('{"ok":true,"service":"davidos-ahk-bridge"}')
        } elseif ($q.Url.AbsolutePath -eq "/send" -and $q.HttpMethod -eq "POST") {
            if ($q.Headers["X-Bridge-Token"] -ne $Token) {
                $r.StatusCode = 401
                $b = [Text.Encoding]::UTF8.GetBytes('{"ok":false,"err":"bad token"}')
            } else {
                $body = (New-Object IO.StreamReader($q.InputStream, $q.ContentEncoding)).ReadToEnd()
                try {
                    $payload = $body | ConvertFrom-Json -ErrorAction Stop
                } catch {
                    $r.StatusCode = 400
                    $b = [Text.Encoding]::UTF8.GetBytes('{"ok":false,"err":"invalid json"}')
                    $r.ContentType = "application/json"
                    $r.OutputStream.Write($b, 0, $b.Length)
                    $r.Close()
                    continue
                }

                $target = "codex"
                if ($null -ne $payload.target -and -not [string]::IsNullOrWhiteSpace([string]$payload.target)) {
                    $target = [string]$payload.target
                }
                if ($allowedTargets -notcontains $target) {
                    $r.StatusCode = 400
                    $b = [Text.Encoding]::UTF8.GetBytes('{"ok":false,"err":"invalid target"}')
                    $r.ContentType = "application/json"
                    $r.OutputStream.Write($b, 0, $b.Length)
                    $r.Close()
                    continue
                }

                $text = ""
                if ($null -ne $payload.text) {
                    $text = [string]$payload.text
                } elseif ($null -ne $payload.message) {
                    $text = [string]$payload.message
                } elseif ($null -ne $payload.prompt) {
                    $text = [string]$payload.prompt
                }
                if ([string]::IsNullOrWhiteSpace($text)) {
                    $r.StatusCode = 400
                    $b = [Text.Encoding]::UTF8.GetBytes('{"ok":false,"err":"missing text"}')
                    $r.ContentType = "application/json"
                    $r.OutputStream.Write($b, 0, $b.Length)
                    $r.Close()
                    continue
                }

                $normalized = @{
                    target = $target
                    text = $text
                    created = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
                    source = if ($payload.source) { [string]$payload.source } else { "bridge-listener" }
                } | ConvertTo-Json -Compress
                $f = Join-Path $inbox ((Get-Date).Ticks.ToString() + ".json")
                [IO.File]::WriteAllText($f, $normalized, [Text.Encoding]::UTF8)
                $response = @{ ok = $true; queued = $true; target = $target } | ConvertTo-Json -Compress
                $b = [Text.Encoding]::UTF8.GetBytes($response)
            }
        } else {
            $r.StatusCode = 404
            $b = [Text.Encoding]::UTF8.GetBytes('{"ok":false,"err":"not found"}')
        }
    } catch {
        $r.StatusCode = 500
        $b = [Text.Encoding]::UTF8.GetBytes('{"ok":false,"err":"server"}')
    }
    $r.ContentType = "application/json"
    $r.OutputStream.Write($b, 0, $b.Length)
    $r.Close()
}
