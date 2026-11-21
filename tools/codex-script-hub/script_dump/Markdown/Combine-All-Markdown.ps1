# Combine All Markdown Files Script
# Combines all .md files in this folder and subfolders into one file

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$outputFile = Join-Path $scriptPath "COMBINED_MARKDOWN_$timestamp.md"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Markdown Combiner Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get all markdown files, sorted by path
$mdFiles = Get-ChildItem -Path $scriptPath -Recurse -Filter "*.md" |
    Where-Object { $_.Name -notlike "COMBINED_*" } |
    Sort-Object FullName

Write-Host "Found $($mdFiles.Count) markdown files" -ForegroundColor Yellow
Write-Host "Output file: $outputFile" -ForegroundColor Yellow
Write-Host ""

# Create the combined file
$content = @()

# Add header
$content += "# Combined Markdown Files"
$content += ""
$content += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$content += "Source folder: $scriptPath"
$content += "Total files: $($mdFiles.Count)"
$content += ""
$content += "---"
$content += ""

# Add table of contents
$content += "## Table of Contents"
$content += ""
$tocNum = 1
foreach ($file in $mdFiles) {
    $relativePath = $file.FullName.Replace($scriptPath, "").TrimStart("\")
    $anchor = $relativePath -replace "[^a-zA-Z0-9]", "-"
    $content += "$tocNum. [$relativePath](#$anchor)"
    $tocNum++
}
$content += ""
$content += "---"
$content += ""

# Add each file's content
$fileNum = 1
foreach ($file in $mdFiles) {
    $relativePath = $file.FullName.Replace($scriptPath, "").TrimStart("\")
    $anchor = $relativePath -replace "[^a-zA-Z0-9]", "-"

    Write-Host "[$fileNum/$($mdFiles.Count)] Processing: $relativePath" -ForegroundColor Gray

    $content += "<a name=`"$anchor`"></a>"
    $content += ""
    $content += "## FILE: $relativePath"
    $content += ""
    $content += "---"
    $content += ""

    # Read and add file content
    $fileContent = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($fileContent) {
        $content += $fileContent
    } else {
        $content += "*[Empty or unreadable file]*"
    }

    $content += ""
    $content += ""
    $content += "---"
    $content += ""
    $content += "[Back to Table of Contents](#table-of-contents)"
    $content += ""
    $content += "---"
    $content += ""

    $fileNum++
}

# Write the combined file
$content | Out-File -FilePath $outputFile -Encoding UTF8

$fileSize = (Get-Item $outputFile).Length / 1MB
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  DONE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Combined file created: $outputFile" -ForegroundColor Green
Write-Host "File size: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
