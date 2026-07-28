# AELMA Start Script for Windows
# Starts all AELMA components

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AelmaDir = Split-Path -Parent $ScriptDir
$VenvDir = Join-Path $AelmaDir ".venv"
$PidDir = Join-Path $AelmaDir "logs\pids"
$LogDir = Join-Path $AelmaDir "logs"

function Write-ColorLog {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Message,

        [Parameter(Mandatory=$false)]
        [ValidateSet("Info", "Warn", "Error")]
        [string]$Level = "Info"
    )

    $color = switch ($Level) {
        "Info" { "Green" }
        "Warn" { "Yellow" }
        "Error" { "Red" }
    }

    Write-Host "[$Level] $Message" -ForegroundColor $color
}

function Test-VirtualEnvironment {
    if (-not (Test-Path $VenvDir)) {
        Write-ColorLog "Virtual environment not found. Run install.ps1 first." "Error"
        exit 1
    }
}

function Test-PortAvailable {
    param(
        [Parameter(Mandatory=$true)]
        [int]$Port
    )

    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($connection) {
            Write-ColorLog "Port $Port is already in use" "Error"
            return $false
        }
        return $true
    }
    catch {
        # No connection found, port is available
        return $true
    }
}

function Start-Component {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Name,

        [Parameter(Mandatory=$true)]
        [int]$Port,

        [Parameter(Mandatory=$true)]
        [string]$Command,

        [Parameter(Mandatory=$true)]
        [string]$Arguments,

        [Parameter(Mandatory=$false)]
        [string]$WorkingDirectory = $AelmaDir
    )

    Write-ColorLog "Starting $Name on port $Port..." "Info"

    # Create directories
    New-Item -Path $PidDir -ItemType Directory -Force | Out-Null
    New-Item -Path $LogDir -ItemType Directory -Force | Out-Null

    $pidFile = Join-Path $PidDir "$Name.pid"
    $logFile = Join-Path $LogDir "$Name.log"

    # Check if already running
    if (Test-Path $pidFile) {
        $existingPid = Get-Content $pidFile
        $process = Get-Process -Id $existingPid -ErrorAction SilentlyContinue

        if ($process) {
            Write-ColorLog "$Name already running (PID: $existingPid)" "Warn"
            return $true
        }
        else {
            Remove-Item $pidFile -Force
        }
    }

    # Check port availability
    if (-not (Test-PortAvailable -Port $Port)) {
        Write-ColorLog "Cannot start $Name - port $Port unavailable" "Error"
        return $false
    }

    try {
        # Start process
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = $Command
        $processInfo.Arguments = $Arguments
        $processInfo.WorkingDirectory = $WorkingDirectory
        $processInfo.UseShellExecute = $false
        $processInfo.RedirectStandardOutput = $true
        $processInfo.RedirectStandardError = $true
        $processInfo.CreateNoWindow = $true

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $processInfo
        $process.Start() | Out-Null

        # Save PID
        $process.Id | Out-File -FilePath $pidFile -Encoding utf8

        # Wait and check if process started successfully
        Start-Sleep -Seconds 2

        if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
            Write-ColorLog "$Name started (PID: $($process.Id))" "Info"
            return $true
        }
        else {
            Write-ColorLog "$Name failed to start - check $logFile" "Error"
            return $false
        }
    }
    catch {
        Write-ColorLog "Failed to start $Name: $_" "Error"
        return $false
    }
}

# Main execution
try {
    Write-ColorLog "Starting AELMA components..." "Info"

    Test-VirtualEnvironment

    $pythonPath = Join-Path $VenvDir "Scripts" "python.exe"

    # Start Bridge (TCP: 8001, WS: 8000)
    $bridgeStarted = Start-Component -Name "bridge" -Port 8000 -Command $pythonPath -Arguments "-m bridge --tcp-port 8001 --ws-port 8000"

    if (-not $bridgeStarted) {
        Write-ColorLog "Failed to start bridge" "Error"
        exit 1
    }

    Start-Sleep -Seconds 2

    # Start Twin (Viewer WS: 8090)
    $twinStarted = Start-Component -Name "twin" -Port 8090 -Command $pythonPath -Arguments "-m twin --bridge-url ws://localhost:8000 --viewer-port 8090"

    if (-not $twinStarted) {
        Write-ColorLog "Failed to start twin" "Error"
        exit 1
    }

    Start-Sleep -Seconds 2

    # Start Viewer (HTTP: 8080)
    $viewerWorkingDir = Join-Path $AelmaDir "build_kimi_viewer"
    $viewerStarted = Start-Component -Name "viewer" -Port 8080 -Command $pythonPath -Arguments "serve.py --port 8080" -WorkingDirectory $viewerWorkingDir

    if (-not $viewerStarted) {
        Write-ColorLog "Failed to start viewer" "Error"
        exit 1
    }

    # Summary
    Write-Host ""
    Write-ColorLog "AELMA components started successfully!" "Info"
    Write-Host ""
    Write-Host "Bridge:"
    Write-Host "  - NMEA TCP: localhost:8001"
    Write-Host "  - WebSocket: localhost:8000"
    Write-Host "  - Logs: $LogDir\bridge.log"
    Write-Host ""
    Write-Host "Twin:"
    Write-Host "  - Viewer WebSocket: localhost:8090"
    Write-Host "  - Logs: $LogDir\twin.log"
    Write-Host ""
    Write-Host "Viewer:"
    Write-Host "  - HTTP: http://localhost:8080"
    Write-Host "  - Logs: $LogDir\viewer.log"
    Write-Host ""
    Write-Host "To view logs:"
    Write-Host "  Get-Content $LogDir\bridge.log -Wait"
    Write-Host "  Get-Content $LogDir\twin.log -Wait"
    Write-Host "  Get-Content $LogDir\viewer.log -Wait"
    Write-Host ""
    Write-Host "To stop AELMA:"
    Write-Host "  $ScriptDir\stop.ps1"
    Write-Host ""
}
catch {
    Write-ColorLog "Failed to start AELMA: $_" "Error"
    exit 1
}
