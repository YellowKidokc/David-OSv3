$Excel = New-Object -ComObject Excel.Application
$Excel.Visible = $false
$Excel.DisplayAlerts = $false
$Excel.ScreenUpdating = $false
$Excel.EnableEvents = $false
$Excel.Calculation = -4135  # Manual

$InputFolder  = "C:\Excel\Input"
$OutputFolder = "C:\Excel\CSV"

if (!(Test-Path $OutputFolder)) {
    New-Item -ItemType Directory -Path $OutputFolder | Out-Null
}

Get-ChildItem $InputFolder -Filter *.xlsx | ForEach-Object {

    Write-Host "Processing $($_.Name)..."

    $Workbook = $Excel.Workbooks.Open($_.FullName, $null, $true)

    $SheetCount = $Workbook.Worksheets.Count

    foreach ($Sheet in $Workbook.Worksheets) {

        if ($Sheet.UsedRange.Count -eq 1) { continue }  # skip empty sheets

        $SafeSheetName = $Sheet.Name -replace '[\\/:*?"<>|]', '_'

        if ($SheetCount -eq 1) {
            $OutputFile = Join-Path $OutputFolder "$($_.BaseName).csv"
        } else {
            $OutputFile = Join-Path $OutputFolder "$($_.BaseName)_$SafeSheetName.csv"
        }

        $Sheet.SaveAs($OutputFile, 6)
    }

    $Workbook.Close($false)
}

$Excel.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($Excel) | Out-Null
