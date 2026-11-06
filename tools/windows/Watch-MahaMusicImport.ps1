param(
    [string]$LogDirectory = $PSScriptRoot,
    [switch]$Once
)

$ErrorActionPreference = 'Stop'
$progressPath = Join-Path $LogDirectory 'music-transfer-progress.json'
$logPath = Join-Path $LogDirectory 'music-transfer-results.jsonl'

function Show-ImportProgress {
    if (Test-Path -LiteralPath $progressPath) {
        try {
            $status = Get-Content -LiteralPath $progressPath -Raw | ConvertFrom-Json
            $percent = if ($status.total) { 100 * $status.done / $status.total } else { 0 }
            $added = [int]$status.counts.added
            $duplicates = [int]$status.counts.skipped
            $errors = [int]$status.counts.error
            $resumed = [int]$status.counts.resumed
            $summary = '{0:N0}/{1:N0} ({2:N1}%) | Added {3:N0} | Duplicates {4:N0} | Errors {5:N0} | Resumed {6:N0} | Sent {7:N2} GB' -f $status.done, $status.total, $percent, $added, $duplicates, $errors, $resumed, $status.sentGB
            Write-Host $summary -ForegroundColor Cyan
            Write-Progress -Activity 'Music import to MAHA' -Status $summary -PercentComplete $percent
        } catch {
            # The importer may be updating this small file; read it again next time.
        }
    }
}

Write-Host 'MAHA music import monitor' -ForegroundColor Green
Write-Host 'Press Ctrl+C to stop monitoring. The import will continue.'
Write-Host "Log: $logPath"
Show-ImportProgress
if ($Once) { return }
if (-not (Test-Path -LiteralPath $logPath)) {
    Write-Host 'Waiting for the import log...'
    while (-not (Test-Path -LiteralPath $logPath)) { Start-Sleep -Seconds 2 }
}
$script:linesSinceSummary = 0
Get-Content -LiteralPath $logPath -Tail 10 -Wait | ForEach-Object {
    if ([string]::IsNullOrWhiteSpace($_)) { return }
    try { $entry = $_ | ConvertFrom-Json } catch { return }
    $color = switch ($entry.status) {
        'added' { 'Green' }
        'skipped' { 'DarkGray' }
        'error' { 'Red' }
        default { 'White' }
    }
    Write-Host ('[{0}] {1}' -f $entry.status.ToUpper(), $entry.source) -ForegroundColor $color
    if ($entry.status -eq 'error') { Write-Host ('  ' + $entry.message) -ForegroundColor Red }
    $script:linesSinceSummary++
    if ($script:linesSinceSummary -ge 20) {
        Show-ImportProgress
        $script:linesSinceSummary = 0
    }
}
