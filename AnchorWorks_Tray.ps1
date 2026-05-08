$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$workspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot = Join-Path $workspaceRoot "Anchorworks"
$launcher = Join-Path $workspaceRoot "launch_anchorworks.ps1"
$port = 8081
$url = "http://127.0.0.1:$port"
$iconPath = Join-Path $appRoot "ui\favicon.ico"

function Get-AnchorWorksProcess {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue }
}

function Show-Balloon {
    param([string]$Title, [string]$Text)
    $notifyIcon.BalloonTipTitle = $Title
    $notifyIcon.BalloonTipText = $Text
    $notifyIcon.ShowBalloonTip(2500)
}

function Start-AnchorWorks {
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`"" -WorkingDirectory $workspaceRoot -WindowStyle Hidden
    Start-Sleep -Seconds 3
    Show-Balloon "AnchorWorks" "Started D runtime on $url"
}

function Stop-AnchorWorks {
    $processes = @(Get-AnchorWorksProcess)
    if ($processes.Count -eq 0) {
        Show-Balloon "AnchorWorks" "No listener found on port $port"
        return
    }
    foreach ($process in $processes) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Show-Balloon "AnchorWorks" "Stopped port $port listener"
}

function Open-AnchorWorks {
    if (!(Get-AnchorWorksProcess)) {
        Start-AnchorWorks
    }
    Start-Process $url
}

function Show-AnchorWorksStatus {
    if (Get-AnchorWorksProcess) {
        Show-Balloon "AnchorWorks" "Running on $url`nData root: $workspaceRoot"
    } else {
        Show-Balloon "AnchorWorks" "Not running`nData root: $workspaceRoot"
    }
}

$notifyIcon = New-Object System.Windows.Forms.NotifyIcon
if (Test-Path -LiteralPath $iconPath) {
    $notifyIcon.Icon = New-Object System.Drawing.Icon($iconPath)
} else {
    $notifyIcon.Icon = [System.Drawing.SystemIcons]::Application
}
$notifyIcon.Text = "AnchorWorks"
$notifyIcon.Visible = $true

$menu = New-Object System.Windows.Forms.ContextMenuStrip
$startItem = $menu.Items.Add("Start AnchorWorks")
$openItem = $menu.Items.Add("Open UI")
$statusItem = $menu.Items.Add("Status")
$stopItem = $menu.Items.Add("Stop AnchorWorks")
$menu.Items.Add("-") | Out-Null
$exitItem = $menu.Items.Add("Exit Tray")

$startItem.add_Click({ Start-AnchorWorks })
$openItem.add_Click({ Open-AnchorWorks })
$statusItem.add_Click({ Show-AnchorWorksStatus })
$stopItem.add_Click({ Stop-AnchorWorks })
$exitItem.add_Click({
    $notifyIcon.Visible = $false
    $notifyIcon.Dispose()
    [System.Windows.Forms.Application]::Exit()
})
$notifyIcon.add_DoubleClick({ Open-AnchorWorks })
$notifyIcon.ContextMenuStrip = $menu

Show-Balloon "AnchorWorks Tray" "Tray loaded. Right-click for controls."
[System.Windows.Forms.Application]::Run()
