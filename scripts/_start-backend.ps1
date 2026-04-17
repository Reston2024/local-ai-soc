# ---------------------------------------------------------------------------
# Pre-flight GPU check (advisory — non-fatal)
# Warns when Ollama is running in CPU-only mode so inference is slow.
# ---------------------------------------------------------------------------
try {
    $ollamaPs = & ollama ps 2>&1
    $gpuLayersLine = $ollamaPs | Where-Object { $_ -match 'GPU\s+Layers' }
    $gpuOk = $false
    if ($gpuLayersLine) {
        # Extract the numeric value that follows "GPU Layers"
        if ($gpuLayersLine -match 'GPU\s+Layers\D+(\d+)') {
            $gpuOk = [int]$Matches[1] -gt 0
        }
    }
    if (-not $gpuOk) {
        Write-Host -ForegroundColor Yellow (
            "WARNING: Ollama appears to be running in CPU-only mode. " +
            "Set CUDA_VISIBLE_DEVICES=0 at Machine scope and restart the Ollama service " +
            "for GPU acceleration. " +
            "See .planning/phases/54-hf-model-integration/54-02-PLAN.md for steps."
        )
    }
} catch {
    # ollama not on PATH or not running — skip check silently
}
# ---------------------------------------------------------------------------

$proc = Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList @('-m', 'uvicorn', 'backend.main:create_app', '--factory', '--host', '0.0.0.0', '--port', '8001', '--log-level', 'info') -WorkingDirectory 'C:\Users\Admin\AI-SOC-Brain' -PassThru -WindowStyle Hidden -RedirectStandardOutput 'logs\backend.log' -RedirectStandardError 'logs\backend-err.log'
$proc.Id | Out-File '.backend.pid'
Write-Host "Started PID $($proc.Id)"
Start-Sleep -Seconds 6
$resp = Invoke-RestMethod -Uri 'http://localhost:8001/health' -TimeoutSec 8 -ErrorAction SilentlyContinue
if ($resp) { Write-Host "HEALTH_OK:$($resp.status)" } else { Write-Host "HEALTH_FAIL" }
