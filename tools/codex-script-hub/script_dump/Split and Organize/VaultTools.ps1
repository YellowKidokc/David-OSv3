# VaultTools.ps1
# Portable folder toolbox:
# 1) Renumber files (recursive, stable sort, collision-safe, numbers at END)
# 2) Split large TEXT-like files into N parts (2..10)
# 3) Group files into batches and optionally folderize and/or zip each batch
#
# Numbering format:  OriginalName_01_of_51.ext  (numbers at END before extension)
# Re-run safe: strips old numbering suffix before re-numbering.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-FolderPath([string]$Prompt = "Folder path") {
    $p = Read-Host "$Prompt"
    $p = $p.Trim('"').Trim()
    if ([string]::IsNullOrWhiteSpace($p)) { throw "No folder path provided." }
    if (!(Test-Path -LiteralPath $p -PathType Container)) { throw "Folder not found: $p" }
    return (Resolve-Path -LiteralPath $p).Path
}

function Get-Files([string]$Dir, [switch]$Recurse) {
    $opts = @{
        LiteralPath = $Dir
        File        = $true
        Force       = $true
    }
    if ($Recurse) { $opts.Recurse = $true }
    Get-ChildItem @opts
}

function Strip-OldNumberSuffix([string]$BaseName) {
    # Removes "_NN_of_TT" suffix if present (numbers at end).
    # Example: "General_Relativity_01_of_51" -> "General_Relativity"
    # Handles 2-4 digit padding.
    if ($BaseName -match '^(.+?)_\d+_of_\d+$') {
        return $Matches[1]
    }
    # Also strip old PREFIX format in case someone ran the old script:
    # "01_of_51_General_Relativity" -> "General_Relativity"
    if ($BaseName -match '^\d+_of_\d+_(.+)$') {
        return $Matches[1]
    }
    return $BaseName
}

function Renumber-Files {
    param(
        [Parameter(Mandatory=$true)][string]$Dir,
        [switch]$Recurse,
        [ValidateSet("Name","FullName")] [string]$SortBy = "Name"
    )

    $files = Get-Files -Dir $Dir -Recurse:$Recurse

    if ($files.Count -eq 0) {
        Write-Host "No files found."
        return
    }

    # Stable ordering
    if ($SortBy -eq "Name") {
        $files = $files | Sort-Object @{Expression="Name"; Ascending=$true}, @{Expression="FullName"; Ascending=$true}
    } else {
        $files = $files | Sort-Object FullName
    }

    $total = $files.Count
    $pad = if ($total -ge 1000) { 4 } elseif ($total -ge 100) { 3 } else { 2 }
    $totStr = $total.ToString().PadLeft($pad,'0')

    Write-Host ""
    Write-Host "Renumbering $total file(s) in: $Dir"
    Write-Host "Recurse: $Recurse | SortBy: $SortBy | Pad: $pad"
    Write-Host "Format: FileName_NN_of_$totStr.ext"
    Write-Host ""

    # Two-step rename to avoid collisions:
    # Step 1: rename everything to a guaranteed-unique temp name
    $tempMap = @()
    $i = 0
    foreach ($f in $files) {
        $i++
        $tempName = "__TMP__{0}__{1}{2}" -f ([guid]::NewGuid().ToString("N")), $i.ToString().PadLeft(6,'0'), $f.Extension
        Rename-Item -LiteralPath $f.FullName -NewName $tempName
        $tempMap += [pscustomobject]@{
            TempFull     = (Join-Path $f.DirectoryName $tempName)
            OriginalDir  = $f.DirectoryName
            OriginalName = $f.Name
            Extension    = $f.Extension
        }
    }

    # Step 2: rename temp files to final numbered names (numbers at END)
    $renamed = 0
    $count = 0
    foreach ($row in $tempMap) {
        $count++
        $numStr = $count.ToString().PadLeft($pad,'0')

        # Get base name without extension, strip any old numbering
        $origBase = [IO.Path]::GetFileNameWithoutExtension($row.OriginalName)
        $cleanBase = Strip-OldNumberSuffix -BaseName $origBase
        $ext = $row.Extension

        # Build new name: CleanName_NN_of_TT.ext
        $newName = "{0}_{1}_of_{2}{3}" -f $cleanBase, $numStr, $totStr, $ext

        $targetFull = Join-Path $row.OriginalDir $newName

        # Handle collision
        if (Test-Path -LiteralPath $targetFull) {
            $k = 1
            do {
                $altName = "{0}_{1}_of_{2}__dup{3}{4}" -f $cleanBase, $numStr, $totStr, $k, $ext
                $targetFull = Join-Path $row.OriginalDir $altName
                $k++
            } while (Test-Path -LiteralPath $targetFull)
            $newName = Split-Path -Leaf $targetFull
        }

        Rename-Item -LiteralPath $row.TempFull -NewName $newName
        $renamed++
        Write-Host ("[{0}/{1}] {2}" -f $numStr, $totStr, $newName)
    }

    Write-Host ""
    Write-Host "Done. Renamed: $renamed / $total"
}

function Split-TextFile {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][ValidateRange(2,10)][int]$Parts
    )

    if (!(Test-Path -LiteralPath $FilePath -PathType Leaf)) { throw "File not found: $FilePath" }

    $ext = [IO.Path]::GetExtension($FilePath).ToLowerInvariant()
    $textLike = @(".txt",".md",".log",".csv",".json",".yaml",".yml",".xml",".ini",".ps1",".bat",".cmd",".py",".ts",".js")
    if ($textLike -notcontains $ext) {
        throw "Split currently supports text-like files only. Got '$ext'. For PDFs you need external tools."
    }

    $bytes = (Get-Item -LiteralPath $FilePath).Length
    $dir = Split-Path -Parent $FilePath
    $nameNoExt = [IO.Path]::GetFileNameWithoutExtension($FilePath)

    $lines = Get-Content -LiteralPath $FilePath -Encoding UTF8
    if ($lines.Count -eq 0) { throw "File is empty." }

    $totalLines = $lines.Count
    $base = [math]::Floor($totalLines / $Parts)
    $extra = $totalLines % $Parts

    $idx = 0
    for ($p=1; $p -le $Parts; $p++) {
        $take = $base + ($(if ($p -le $extra) { 1 } else { 0 }))
        $chunk = $lines[$idx..($idx+$take-1)]
        $idx += $take

        $partStr = $p.ToString().PadLeft(2,'0')
        $out = Join-Path $dir ("{0}__part{1}_of_{2}{3}" -f $nameNoExt, $partStr, $Parts.ToString().PadLeft(2,'0'), $ext)
        $chunk | Set-Content -LiteralPath $out -Encoding UTF8
        Write-Host "Wrote: $out  ($($chunk.Count) lines)"
    }

    Write-Host ""
    Write-Host "Split complete. Size: $bytes bytes | Lines: $totalLines | Parts: $Parts"
}

function Group-Files {
    param(
        [Parameter(Mandatory=$true)][string]$Dir,
        [switch]$Recurse,
        [Parameter(Mandatory=$true)][int]$GroupSize,
        [ValidateSet("Name","FullName")] [string]$SortBy = "Name",
        [switch]$MakeFolders,
        [switch]$ZipGroups
    )

    if ($GroupSize -lt 1) { throw "GroupSize must be >= 1" }

    $files = Get-Files -Dir $Dir -Recurse:$Recurse
    if ($files.Count -eq 0) { Write-Host "No files found."; return }

    if ($SortBy -eq "Name") {
        $files = $files | Sort-Object @{Expression="Name"; Ascending=$true}, @{Expression="FullName"; Ascending=$true}
    } else {
        $files = $files | Sort-Object FullName
    }

    $total = $files.Count
    $groups = [math]::Ceiling($total / $GroupSize)

    Write-Host ""
    Write-Host "Grouping $total file(s) into $groups group(s) of $GroupSize"
    Write-Host "MakeFolders: $MakeFolders | ZipGroups: $ZipGroups"
    Write-Host ""

    $baseOut = Join-Path $Dir "_groups"
    if ($MakeFolders -or $ZipGroups) {
        New-Item -ItemType Directory -Path $baseOut -Force | Out-Null
    }

    for ($g=1; $g -le $groups; $g++) {
        $start = ($g-1)*$GroupSize
        $end = [math]::Min($start + $GroupSize - 1, $total - 1)
        $slice = $files[$start..$end]

        $gStr = $g.ToString().PadLeft(3,'0')
        $groupFolder = Join-Path $baseOut ("group_{0}" -f $gStr)

        if ($MakeFolders) {
            New-Item -ItemType Directory -Path $groupFolder -Force | Out-Null
            foreach ($f in $slice) {
                Move-Item -LiteralPath $f.FullName -Destination $groupFolder
            }
            Write-Host "Moved group $gStr -> $groupFolder  ($($slice.Count) files)"
        }

        if ($ZipGroups) {
            if (-not $MakeFolders) {
                New-Item -ItemType Directory -Path $groupFolder -Force | Out-Null
                foreach ($f in $slice) {
                    Copy-Item -LiteralPath $f.FullName -Destination $groupFolder
                }
            }

            $zipPath = Join-Path $baseOut ("group_{0}.zip" -f $gStr)
            if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
            Compress-Archive -Path (Join-Path $groupFolder "*") -DestinationPath $zipPath
            Write-Host "Zipped group $gStr -> $zipPath"

            if (-not $MakeFolders) {
                Remove-Item -LiteralPath $groupFolder -Recurse -Force
            }
        }
    }

    Write-Host ""
    Write-Host "Done grouping."
}

# ============================================================
#  MAIN MENU
# ============================================================

while ($true) {
    Write-Host ""
    Write-Host "========================================"
    Write-Host " VaultTools v1.0"
    Write-Host "========================================"
    Write-Host " 1) Renumber files  (Name_01_of_51.ext)"
    Write-Host " 2) Split a big TEXT file (2-10 parts)"
    Write-Host " 3) Group files into batches"
    Write-Host " Q) Quit"
    Write-Host ""

    $choice = (Read-Host "Select").Trim().ToUpperInvariant()

    if ($choice -eq "Q") { break }

    switch ($choice) {
        "1" {
            $dir = Read-FolderPath "Folder to renumber"
            $rec = (Read-Host "Recurse subfolders? (y/n)").Trim().ToLowerInvariant() -eq "y"
            $sort = (Read-Host "Sort by Name or FullName? [Name]").Trim()
            if ([string]::IsNullOrWhiteSpace($sort)) { $sort = "Name" }
            Renumber-Files -Dir $dir -Recurse:$rec -SortBy $sort
        }
        "2" {
            $file = (Read-Host "Full path to TEXT file").Trim('"').Trim()
            $parts = [int](Read-Host "How many parts? (2-10)")
            Split-TextFile -FilePath $file -Parts $parts
        }
        "3" {
            $dir = Read-FolderPath "Folder to group"
            $rec = (Read-Host "Recurse subfolders? (y/n)").Trim().ToLowerInvariant() -eq "y"
            $groupSize = [int](Read-Host "Group size (e.g. 2, 5, 10, 20)")
            $sort = (Read-Host "Sort by Name or FullName? [Name]").Trim()
            if ([string]::IsNullOrWhiteSpace($sort)) { $sort = "Name" }

            $mk = (Read-Host "Move into group folders? (y/n)").Trim().ToLowerInvariant() -eq "y"
            $zip = (Read-Host "Zip each group? (y/n)").Trim().ToLowerInvariant() -eq "y"

            Group-Files -Dir $dir -Recurse:$rec -GroupSize $groupSize -SortBy $sort -MakeFolders:$mk -ZipGroups:$zip
        }
        default {
            Write-Host "Unknown selection."
        }
    }
}

Write-Host "Goodbye."
