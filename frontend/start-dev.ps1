param(
    [ValidateRange(1, 65535)]
    [int]$Port = 3000
)

$ErrorActionPreference = 'Stop'
$frontendRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $frontendRoot
$logRoot = Join-Path $projectRoot '.local'
$viteEntry = Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'

if (-not (Test-Path -LiteralPath $viteEntry)) {
    throw 'Frontend dependencies are missing. Run npm ci in the frontend directory first.'
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "Port $Port is already listening. Open http://127.0.0.1:$Port/ or inspect that process before restarting."
    return
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stdoutLog = Join-Path $logRoot "frontend-$Port.stdout.log"
$stderrLog = Join-Path $logRoot "frontend-$Port.stderr.log"
$nodeRuntime = (Get-Command node.exe -ErrorAction Stop).Source

# A separate hidden Windows process keeps Vite running after the launching shell exits.
$devProcess = Start-Process -FilePath $nodeRuntime `
    -ArgumentList @("`"$viteEntry`"", '--host', '127.0.0.1', '--port', "$Port") `
    -WorkingDirectory $frontendRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 250
    $devProcess.Refresh()
    if ($devProcess.HasExited) {
        $details = Get-Content -LiteralPath $stderrLog -Raw -ErrorAction SilentlyContinue
        throw "Vite exited with code $($devProcess.ExitCode). $details"
    }
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -TimeoutSec 1 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "Frontend ready: http://127.0.0.1:$Port/ (PID $($devProcess.Id))"
            Write-Host "Logs: $stdoutLog ; $stderrLog"
            return
        }
    } catch {
        # Vite may still be starting; the process and HTTP response are checked again.
    }
}

throw "Vite did not respond in time. Inspect $stdoutLog and $stderrLog (PID $($devProcess.Id))."
