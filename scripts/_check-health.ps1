Start-Sleep -Seconds 20
try {
    $resp = Invoke-RestMethod 'http://localhost:8000/health' -TimeoutSec 5
    Write-Host "HEALTH_OK: $($resp.status)"
    $resp | ConvertTo-Json -Depth 3
} catch {
    Write-Host "HEALTH_FAIL: $($_.Exception.Message)"
    # Also show last log entries
    Write-Host "--- Last log entries ---"
    Get-Content 'C:\Users\Admin\AI-SOC-Brain\logs\backend-err.log' | Select-Object -Last 20
}
