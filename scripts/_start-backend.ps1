$proc = Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList @('-m', 'uvicorn', 'backend.main:create_app', '--factory', '--host', '0.0.0.0', '--port', '8001', '--log-level', 'info') -WorkingDirectory 'C:\Users\Admin\AI-SOC-Brain' -PassThru -WindowStyle Hidden -RedirectStandardOutput 'logs\backend.log' -RedirectStandardError 'logs\backend-err.log'
$proc.Id | Out-File '.backend.pid'
Write-Host "Started PID $($proc.Id)"
Start-Sleep -Seconds 6
$resp = Invoke-RestMethod -Uri 'http://localhost:8001/health' -TimeoutSec 8 -ErrorAction SilentlyContinue
if ($resp) { Write-Host "HEALTH_OK:$($resp.status)" } else { Write-Host "HEALTH_FAIL" }
