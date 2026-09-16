# Sequential full-pipeline scan. One SQLite writer. Skip Desktop 2.
$ErrorActionPreference = 'Continue'
Set-Location 'D:\GitHub\David-OS\file-intelligence-system'
$log = Join-Path $PWD 'scan_log.txt'

$targets = @(
    'H:\Desktop',
    'D:\DONT TOUCH HTML',
    'D:\01_Axioms',
    'D:\00_Canonical_PRODUCTION_v1.0',
    'D:\Theophysics',
    'Z:\__New\Theophysics.new',
    'H:\'
)

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss')  $msg"
    Write-Output $line
    Add-Content -LiteralPath $log -Value $line
}

Write-Log "SCALE_SCAN_ALL START"
foreach ($t in $targets) {
    if (-not (Test-Path -LiteralPath $t)) {
        Write-Log "SKIP (missing): $t"
        continue
    }
    if ($t -eq 'H:\' -or $t -eq 'H:') {
        Write-Log "NOTE: H:\ includes Desktop 2 — skipped as a root; Desktop one already listed first."
        continue
    }
    Write-Log "SCAN START  $t"
    python fis_folder_memory.py $t --tree --html --doc-types --no-local-ai
    Write-Log "SCAN END    $t  exit=$LASTEXITCODE"
}

Write-Log "Building fis_html_index"
python -c @"
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
db = Path('fis_folder_memory.sqlite')
conn = sqlite3.connect(db, timeout=180)
conn.execute('''CREATE TABLE IF NOT EXISTS fis_html_index (
    folder_path TEXT PRIMARY KEY, fis_html_path TEXT NOT NULL,
    folder_scan_date TEXT, file_count INTEGER)''')
rows = conn.execute('SELECT path, file_count, last_scanned FROM folder_memory').fetchall()
n = 0
for path, count, scanned in rows:
    page = Path(path) / 'FIS.html'
    if page.exists():
        conn.execute('''INSERT INTO fis_html_index(folder_path,fis_html_path,folder_scan_date,file_count)
                        VALUES(?,?,?,?) ON CONFLICT(folder_path) DO UPDATE SET
                        fis_html_path=excluded.fis_html_path, folder_scan_date=excluded.folder_scan_date,
                        file_count=excluded.file_count''',
                     (path, str(page), scanned, count or 0))
        n += 1
conn.commit()
print(f'fis_html_index rows={n}')
conn.close()
"@
Write-Log "SCALE_SCAN_ALL COMPLETE"
