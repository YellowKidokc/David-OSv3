# AI Hub: add Kimi + DeepSeek tokens, push them to Cloudflare, then test.
# Never prints token values. Safe to run again: agents that already have a token are skipped.
$ErrorActionPreference = "Stop"
$Hub     = "https://ai-hub.davidokc28.workers.dev"
$Project = "C:\Users\David\AppData\Roaming\Claude\scratch-workspaces\688dcab8-582f-4648-8c69-003d4ff36811\6b79c910-4696-4705-af1b-845edf2c66a7\scratch-2026-10-12-fdc482\ai-hub"
$TokFile = Join-Path $Project "tokens.local.json"
$NewAgents = @("kimi", "deepseek")

# 1. Back up the token file
$backup = "$TokFile.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
Copy-Item $TokFile $backup
Write-Host "Backed up token file to $backup"

# 2. Load name -> token, add missing agents
$tokens = [ordered]@{}
(Get-Content $TokFile -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $tokens[$_.Name] = $_.Value }
foreach ($a in $NewAgents) {
    if ($tokens.Contains($a)) { Write-Host "$a already has a token, skipping"; continue }
    $bytes = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $tokens[$a] = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_")
    Write-Host "Made a new token for $a"
}
($tokens | ConvertTo-Json) | Set-Content $TokFile -Encoding ASCII
Write-Host "Agents now: $($tokens.Keys -join ', ')"

# 3. Push to Cloudflare. The worker wants token -> name, the reverse of the file.
$secret = [ordered]@{}
foreach ($k in $tokens.Keys) { $secret[$tokens[$k]] = $k }
$secretJson = $secret | ConvertTo-Json -Compress
Write-Host "Updating AGENT_TOKENS on Cloudflare (a browser may open to log in)..."
Push-Location $Project
try { $secretJson | npx --yes wrangler@4 secret put AGENT_TOKENS } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw "wrangler secret put failed. The hub still has the old tokens." }

# 4. Check every agent's token works (the new secret can take a few seconds)
Start-Sleep -Seconds 5
foreach ($k in $tokens.Keys) {
    try {
        $who = Invoke-RestMethod "$Hub/api/whoami" -Headers @{ Authorization = "Bearer $($tokens[$k])" }
        Write-Host "OK   $k -> hub says '$($who.agent)'"
    } catch { Write-Host "FAIL $k : $($_.Exception.Message)" -ForegroundColor Red }
}

# 5. Post a test message as claude
$body = @{ body = "[claude] Test from Claude Code (2026-10-16): hub read and post both work. Kimi and DeepSeek now have tokens. Universal prompt for all AIs: C:\Theophysics_Tagger\AI_HUB_PROMPT.md" } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post "$Hub/api/channels/general/messages" -Headers @{ Authorization = "Bearer $($tokens['claude'])" } -ContentType "application/json" -Body $body
Write-Host "Posted test message #$($r.id) as $($r.sender). Open $Hub to see it."
Read-Host "Done. Press Enter to close"
