param(
    [string]$TargetFolder,
    [string]$SourcePath,
    [string]$SourceListFile,
    [ValidateSet('single', 'super', 'independent', 'both')]
    [string]$BatchPlan = 'single',
    [ValidateSet('general', 'meq')]
    [string]$Mode = 'general',
    [switch]$OpenAfter
)

$ErrorActionPreference = 'Stop'

function Get-SafeSlug {
    param([string]$Value)
    $slug = $Value -replace '[^\p{L}\p{Nd}]+', '_'
    $slug = $slug.Trim('_')
    if ([string]::IsNullOrWhiteSpace($slug)) { return 'folder' }
    if ($slug.Length -gt 40) { return $slug.Substring(0, 40).Trim('_') }
    return $slug
}

function Get-SourceTitle {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    $name = [System.IO.Path]::GetFileNameWithoutExtension($Path)
    try {
        $lines = Get-Content -LiteralPath $Path -TotalCount 80 -ErrorAction Stop
        foreach ($line in $lines) {
            $trimmed = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
            if ($trimmed -match '^\s*#\s+(.+)$') { return $Matches[1].Trim() }
            if ($trimmed -match '^\s*<title>(.+)</title>\s*$') { return $Matches[1].Trim() }
            return $trimmed
        }
    } catch {
        return $name
    }
    return $name
}

function ConvertTo-YamlSingleQuoted {
    param([string]$Value)
    if ($null -eq $Value) { return "''" }
    return "'" + ($Value -replace "'", "''") + "'"
}

$sourcePaths = @()
if (-not [string]::IsNullOrWhiteSpace($SourceListFile)) {
    if (-not (Test-Path -LiteralPath $SourceListFile -PathType Leaf)) {
        throw "Source list file does not exist: $SourceListFile"
    }
    $sourcePaths = @(Get-Content -LiteralPath $SourceListFile | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($sourcePaths.Count -gt 0 -and [string]::IsNullOrWhiteSpace($SourcePath)) {
        $SourcePath = $sourcePaths[0]
    }
}

if (-not [string]::IsNullOrWhiteSpace($SourcePath)) {
    $sourceResolved = [System.IO.Path]::GetFullPath($SourcePath)
    if (Test-Path -LiteralPath $sourceResolved -PathType Leaf) {
        if ([string]::IsNullOrWhiteSpace($TargetFolder)) {
            $TargetFolder = Split-Path -Parent $sourceResolved
        }
    } elseif (Test-Path -LiteralPath $sourceResolved -PathType Container) {
        if ([string]::IsNullOrWhiteSpace($TargetFolder)) {
            $TargetFolder = $sourceResolved
        }
        $SourcePath = $null
    } else {
        throw "Source path does not exist: $SourcePath"
    }
}

if ([string]::IsNullOrWhiteSpace($TargetFolder)) {
    $TargetFolder = (Get-Location).Path
}

$resolved = [System.IO.Path]::GetFullPath($TargetFolder)
if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
    throw "Target folder does not exist: $resolved"
}

$mechanismRoot = Split-Path -Parent $PSCommandPath
$frameworkDir = Join-Path $resolved '_LOSSLESS_VIALS'
New-Item -ItemType Directory -Force -Path $frameworkDir | Out-Null

$promptFiles = @(
    'START_HERE_LOSSLESS_VIALS.md',
    'LOSSLESS_VIAL_FACTORY_PROMPT.md',
    'LOSS__PARAGRAPH_VIAL_TEMPLATE.md',
    'MEQ__MASTER_EQ_NABLA_VIAL_TEMPLATE.md',
    'UNIVERSAL_LOSSLESS_SUMMARY_META_PROMPT.md'
)

foreach ($file in $promptFiles) {
    $src = Join-Path $mechanismRoot $file
    if (Test-Path -LiteralPath $src -PathType Leaf) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $frameworkDir $file) -Force
    }
}

function New-GeneralVialContent {
    param(
        [string]$InternalName,
        [string]$Id,
        [string]$SourceLine,
        [string]$SourceTitleYaml,
        [string]$ExtraYaml = ""
    )
@"
# $InternalName

~~~yaml
vial:
  id: "$Id"
  internal_name: "$InternalName"
  external_filename_policy: "preserve original/familiar filename unless user explicitly asks to rename"
  kind: "lossless_paragraph_vial"
  $SourceLine
  source_title: $SourceTitleYaml
$ExtraYaml  fidelity: "compact paragraph-by-paragraph compression; no important detail intentionally omitted"
  p:
    p001: {gist: "", keep: [], logic: "", tone: "", status: "", xrefs: []}
  threads:
    decisions: []
    constraints: []
    symbols: []
    open_loops: []
    implemented: []
    blocked: []
  decode:
    p: "paragraph id"
    keep: "exact survival tokens"
    xrefs: "relationships to other paragraph ids"
~~~
"@
}

function New-MeqVialContent {
    param(
        [string]$InternalName,
        [string]$Id,
        [string]$SourceLine,
        [string]$SourceTitleYaml,
        [string]$ExtraYaml = ""
    )
@"
# $InternalName

~~~yaml
vial:
  id: "$Id"
  internal_name: "$InternalName"
  external_filename_policy: "preserve original/familiar filename unless user explicitly asks to rename"
  kind: "master_equation_nabla_vial"
  $SourceLine
  source_title: $SourceTitleYaml
$ExtraYaml  guardrails:
    - "Nabla C is not Master Equation C_W."
    - "C_W is wrapper/context, not a tenth Nabla factor."
    - "Do not multiply the 10-vector as canonical chi."
    - "Keep theology, math, empirical claim, and operational naming separate."
  p:
    p001:
      gist: ""
      meq: {C_W: "", law: "", claim_tier: ""}
      nabla: {D: "", N: "", V: "", A: "", U: "", R: "", vector: ""}
      keep: []
      logic: ""
      status: ""
      xrefs: []
~~~
"@
}

$date = Get-Date -Format 'yyyy-MM-dd'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$folderName = Split-Path -Leaf $resolved
$sourceTitle = Get-SourceTitle $SourcePath
$slugBase = if ([string]::IsNullOrWhiteSpace($sourceTitle)) { $folderName } else { $sourceTitle }
$slug = Get-SafeSlug $slugBase
$lossInternalName = "LOSS__$slug`__$date"
$meqInternalName = "MEQ__$slug`__$date"
$sourceLine = if ([string]::IsNullOrWhiteSpace($SourcePath)) { "source_folder: $(ConvertTo-YamlSingleQuoted $resolved)" } else { "source_file: $(ConvertTo-YamlSingleQuoted $sourceResolved)" }
$sourceTitleYaml = ConvertTo-YamlSingleQuoted $sourceTitle
$effectiveMode = $Mode
if ($Mode -eq 'general' -and -not [string]::IsNullOrWhiteSpace($SourcePath)) {
    $modeProbe = "$sourceTitle $sourceResolved"
    if ($modeProbe -match '(?i)\b(master\s*equation|nabla|meq|master[_ -]?eq)\b') {
        $effectiveMode = 'meq'
    }
}

if ($sourcePaths.Count -gt 1 -and $BatchPlan -ne 'single') {
    $validFiles = @()
    foreach ($p in $sourcePaths) {
        $rp = [System.IO.Path]::GetFullPath($p)
        if (Test-Path -LiteralPath $rp -PathType Leaf) {
            $validFiles += $rp
        }
    }
    if ($validFiles.Count -eq 0) {
        throw "No valid files found in source list."
    }

    $batchTitle = "BATCH_$folderName"
    $batchSlug = Get-SafeSlug $batchTitle
    $sourceListYaml = "  sources:`r`n"
    foreach ($vf in $validFiles) {
        $title = Get-SourceTitle $vf
        $sourceListYaml += "    - path: $(ConvertTo-YamlSingleQuoted $vf)`r`n"
        $sourceListYaml += "      title: $(ConvertTo-YamlSingleQuoted $title)`r`n"
    }

    $openFile = $null
    if ($BatchPlan -in @('super', 'both')) {
        $superInternal = "LOSS__$batchSlug`__$date"
        $superFile = Join-Path $frameworkDir 'SUPER_LOSSLESS_WORKING_VIAL.md'
        if (-not (Test-Path -LiteralPath $superFile)) {
            $content = New-GeneralVialContent -InternalName $superInternal -Id "LOSS_$date`_$batchSlug" -SourceLine "source_folder: $(ConvertTo-YamlSingleQuoted $resolved)" -SourceTitleYaml (ConvertTo-YamlSingleQuoted $batchTitle) -ExtraYaml $sourceListYaml
            Set-Content -LiteralPath $superFile -Value $content -Encoding UTF8
        }
        $openFile = $superFile

        $superMeqInternal = "MEQ__$batchSlug`__$date"
        $superMeqFile = Join-Path $frameworkDir 'SUPER_MASTER_EQ_WORKING_VIAL.md'
        if (-not (Test-Path -LiteralPath $superMeqFile)) {
            $content = New-MeqVialContent -InternalName $superMeqInternal -Id "MEQ_$date`_$batchSlug" -SourceLine "source_folder: $(ConvertTo-YamlSingleQuoted $resolved)" -SourceTitleYaml (ConvertTo-YamlSingleQuoted $batchTitle) -ExtraYaml $sourceListYaml
            Set-Content -LiteralPath $superMeqFile -Value $content -Encoding UTF8
        }
    }

    if ($BatchPlan -in @('independent', 'both')) {
        foreach ($vf in $validFiles) {
            $title = Get-SourceTitle $vf
            $itemSlug = Get-SafeSlug $(if ([string]::IsNullOrWhiteSpace($title)) { [System.IO.Path]::GetFileNameWithoutExtension($vf) } else { $title })
            $itemInternal = "LOSS__$itemSlug`__$date"
            $itemFile = Join-Path $frameworkDir ([System.IO.Path]::GetFileName($vf))
            if (-not (Test-Path -LiteralPath $itemFile)) {
                $content = New-GeneralVialContent -InternalName $itemInternal -Id "LOSS_$date`_$itemSlug" -SourceLine "source_file: $(ConvertTo-YamlSingleQuoted $vf)" -SourceTitleYaml (ConvertTo-YamlSingleQuoted $title)
                Set-Content -LiteralPath $itemFile -Value $content -Encoding UTF8
            }
            $probe = "$title $vf"
            if ($probe -match '(?i)\b(master\s*equation|nabla|meq|master[_ -]?eq)\b') {
                $meqInternal = "MEQ__$itemSlug`__$date"
                $meqFile = Join-Path $frameworkDir ([System.IO.Path]::GetFileNameWithoutExtension($vf) + '.MEQ' + [System.IO.Path]::GetExtension($vf))
                if (-not (Test-Path -LiteralPath $meqFile)) {
                    $content = New-MeqVialContent -InternalName $meqInternal -Id "MEQ_$date`_$itemSlug" -SourceLine "source_file: $(ConvertTo-YamlSingleQuoted $vf)" -SourceTitleYaml (ConvertTo-YamlSingleQuoted $title)
                    Set-Content -LiteralPath $meqFile -Value $content -Encoding UTF8
                }
            }
        }
        if ($null -eq $openFile) { $openFile = $frameworkDir }
    }

    $receipt = @"
# Lossless Framework Receipt

Created/updated: $stamp
Target folder: $resolved
Source list file: $SourceListFile
Framework folder: $frameworkDir
Batch plan: $BatchPlan
Source count: $($validFiles.Count)

Batch choices:

- super: one combined vial for the selected batch.
- independent: one vial per selected file.
- both: creates both the combined vial and independent file vials.

No source files were renamed or deleted.
"@
    Set-Content -LiteralPath (Join-Path $frameworkDir 'LOSSLESS_FRAMEWORK_RECEIPT.md') -Value $receipt -Encoding UTF8
    if ($OpenAfter) {
        if (Test-Path -LiteralPath $openFile -PathType Leaf) { Invoke-Item -LiteralPath $openFile } else { Start-Process explorer.exe -ArgumentList "`"$frameworkDir`"" }
    }
    Write-Output $frameworkDir
    return
}

$lossFile = Join-Path $frameworkDir 'LOSSLESS_WORKING_VIAL.md'
$selectedLossFile = $null
if (-not [string]::IsNullOrWhiteSpace($SourcePath)) {
    $selectedLossFile = Join-Path $frameworkDir ([System.IO.Path]::GetFileName($sourceResolved))
    $lossFile = $selectedLossFile
}
if (-not (Test-Path -LiteralPath $lossFile)) {
    $loss = New-GeneralVialContent -InternalName $lossInternalName -Id "LOSS_$date`_$slug" -SourceLine $sourceLine -SourceTitleYaml $sourceTitleYaml
    Set-Content -LiteralPath $lossFile -Value $loss -Encoding UTF8
}

$meqFile = Join-Path $frameworkDir 'MASTER_EQ_WORKING_VIAL.md'
$selectedMeqFile = $null
if (-not [string]::IsNullOrWhiteSpace($SourcePath)) {
    $sourceBase = [System.IO.Path]::GetFileNameWithoutExtension($sourceResolved)
    $sourceExt = [System.IO.Path]::GetExtension($sourceResolved)
    $selectedMeqFile = Join-Path $frameworkDir ($sourceBase + '.MEQ' + $sourceExt)
    $meqFile = $selectedMeqFile
}
if (-not (Test-Path -LiteralPath $meqFile)) {
    $meq = New-MeqVialContent -InternalName $meqInternalName -Id "MEQ_$date`_$slug" -SourceLine $sourceLine -SourceTitleYaml $sourceTitleYaml
    Set-Content -LiteralPath $meqFile -Value $meq -Encoding UTF8
}

$receipt = @"
# Lossless Framework Receipt

Created/updated: $stamp
Target folder: $resolved
Source path: $SourcePath
Framework folder: $frameworkDir
Mode requested: $Mode
Effective mode: $effectiveMode

Hotkey behavior:

- Ctrl+Shift+L tries to use the selected File Explorer item first.
- If a selected file is found, it uses that file's parent folder and title/header.
- If no selection is detected, it uses the active File Explorer folder.
- If no folder is detected, it asks you to pick a file or folder.
- It creates or refreshes `_LOSSLESS_VIALS` in that folder.
- It preserves outside filenames by default; compact names live inside `vial.internal_name`.
- Each working vial puts the compact internal name on line 1 as an H1 header for systems that save/index the first line.

Use:

1. Open `LOSSLESS_VIAL_FACTORY_PROMPT.md`.
2. Paste source material into an AI chat.
3. Ask it to produce/update `LOSSLESS_WORKING_VIAL.md` or `MASTER_EQ_WORKING_VIAL.md`.

No source files were renamed or deleted.
"@

Set-Content -LiteralPath (Join-Path $frameworkDir 'LOSSLESS_FRAMEWORK_RECEIPT.md') -Value $receipt -Encoding UTF8

if ($OpenAfter) {
    $openFile = if ($effectiveMode -eq 'meq') { $meqFile } else { $lossFile }
    if (Test-Path -LiteralPath $openFile -PathType Leaf) {
        Invoke-Item -LiteralPath $openFile
    } else {
        Start-Process explorer.exe -ArgumentList "`"$frameworkDir`""
    }
}

Write-Output $frameworkDir
