$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot = Join-Path $workspaceRoot "Anchorworks"
$dataRoot = $workspaceRoot
$port = 8081
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outLog = Join-Path $appRoot "anchorworks-8081-$stamp.out.log"
$errLog = Join-Path $appRoot "anchorworks-8081-$stamp.err.log"

$pythonCmd = Get-Command python.exe -ErrorAction Stop

Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }

$env:PYTHONPATH = Join-Path $appRoot "src"
$args = "-m AnchorWorks.cli serve --data-root `"$dataRoot`" --host 127.0.0.1 --port $port"
Start-Process -FilePath $pythonCmd.Source -ArgumentList $args -WorkingDirectory $appRoot -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog

Start-Sleep -Seconds 3
$url = "http://127.0.0.1:$port"
Start-Process $url
Write-Host "AnchorWorks UI launched: $url"
Write-Host "App root: $appRoot"
Write-Host "Data root: $dataRoot"