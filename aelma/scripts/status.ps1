# AELMA Status Script for Windows
# Checks status of all AELMA components

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AelmaDir = Split-Path -Parent $ScriptDir
$PidDir = Join-Path $AelmaDir "logs\pids"
$LogDir = Join-Path $AelmaDir "logs"

# Component definitions
$Components = @{
    "bridge" = @{
        Port = 8000
        Description = "NMEA Bridge (TCP:8001, WS:8000)"
    }
    "twin" = @{
        Port = 8090
        Description = "Digital Twin (Viewer WS:8090)"
    }
    "viewer" = @{
        Port = 8080
        Description = "Web Viewer (HTTP:8080)"
    }
}

function Write-ColorLog {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Message,

        [Parameter(Mandatory=$false)]
        [ValidateSet("Info", "Warn", "Error", "Header")]
        [string]$Level = "Info"
    )

    $color = switch ($Level) {
        "Info" { "Green" }
        "Warn" { "Yellow" }
        "Error" { "Red" }
        "Header" { "Cyan" }
    }

    Write-Host "[$Level] $Message" -ForegroundColor $color
}

function Test-ProcessRunning {
    param(
        [Parameter(Mandatory=$true)]
        [int]$Pid
    )

    try {
        $process = Get-Process -Id $Pid -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Get-ProcessUptime {
    param(
        [Parameter(Mandatory=$true)]
        [int]$Pid
    )

    try {
        $process = Get-Process -Id $Pid -ErrorAction Stop
        $uptime = (Get-Date) - $process.StartTime
        return "{0:hh\:mm\:ss}" -f $uptime
    }
    catch {
        return "Unknown"
    }
}

function Test-PortListening {
    param(
        [Parameter(Mandatory=$true)]
        [int]$Port
    )

    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Show-ComponentStatus {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Name,

        [Parameter(Mandatory=$true)]
        [int]$Port,

        [Parameter(Mandatory=$true)]
        [string]$Description
    )

    Write-Host ""
    Write-ColorLog "=== $Name`: $Description ===" "Header"

    $pidFile = Join-Path $PidDir "$Name.pid"
    $logFile = Join-Path $LogDir "$Name.log"

    # Check PID file
    if (Test-Path $pidFile) {
        try {
            $pid = Get-Content $pidFile -ErrorAction Stop
            if (Test-ProcessRunning -Pid $pid) {
                $uptime = Get-ProcessUptime -Pid $pid
                Write-Host "  Status: " -NoNewline
                Write-Host "Running" -ForegroundColor Green
                Write-Host "  PID: $pid"
                Write-Host "  Uptime: $uptime"
                Write-Host "  PID file: $pidFile"
            }
            else {
                Write-Host "  Status: " -NoNewline
                Write-Host "Not Running (stale PID file)" -ForegroundColor Red
                Write-Host "  PID file: $pidFile"
            }
        }
        catch {
            Write-Host "  Status: " -NoNewline
            Write-Host "Error reading PID file" -ForegroundColor Red
        }
    }
    else {
        Write-Host "  Status: " -NoNewline
        Write-Host "Stopped (no PID file)" -ForegroundColor Yellow
    }

    # Check port
    if (Test-PortListening -Port $Port) {
        Write-Host "  Port $Port`: " -NoNewline
        Write-Host "Listening" -ForegroundColor Green
    }
    else {
        Write-Host "  Port $Port`: " -NoNewline
        Write-Host "Not listening" -ForegroundColor Red
    }

    # Check log file
    if (Test-Path $logFile) {
        $logItem = Get-Item $logFile
        Write-Host "  Log file: $logFile"
        Write-Host "  Log size: $($logItem.Length) bytes"
        Write-Host "  Log modified: $($logItem.LastWriteTime)"

        # Show last log line
        $lastLine = Get-Content $logFile -Tail 1 -ErrorAction SilentlyContinue
        if ($lastLine) {
            Write-Host "  Last log entry:"
            Write-Host "    $lastLine"
        }
    }
    else {
        Write-Host "  Log file: Not found"
    }
}

function Show-HealthChecks {
    Write-Host ""
    Write-ColorLog "=== Health Checks ===" "Header"

    # Check if we can make web requests
    try {
        # Check bridge WebSocket
        Write-Host "Checking bridge WebSocket (ws://localhost:8000)..."
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000" -Method Head -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 400 -or $response.StatusCode -eq 101 -or $response.StatusCode -eq 426) {
                Write-Host "  " -NoNewline
                Write-Host "✓" -ForegroundColor Green
                Write-Host " Bridge WebSocket server responding"
            }
            else {
                Write-Host "  " -NoNewline
                Write-Host "✗" -ForegroundColor Yellow
                Write-Host " Bridge WebSocket server responded with $($response.StatusCode)"
            }
        }
        catch {
            Write-Host "  " -NoNewline
            Write-Host "✗" -ForegroundColor Yellow
            Write-Host " Bridge WebSocket server not responding"
        }

        # Check twin WebSocket
        Write-Host "Checking twin WebSocket (ws://localhost:8090)..."
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8090" -Method Head -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 400 -or $response.StatusCode -eq 101 -or $response.StatusCode -eq 426) {
                Write-Host "  " -NoNewline
                Write-Host "✓" -ForegroundColor Green
                Write-Host " Twin WebSocket server responding"
            }
            else {
                Write-Host "  " -NoNewline
                Write-Host "✗" -ForegroundColor Yellow
                Write-Host " Twin WebSocket server responded with $($response.StatusCode)"
            }
        }
        catch {
            Write-Host "  " -NoNewline
            Write-Host "✗" -ForegroundColor Yellow
            Write-Host " Twin WebSocket server not responding"
        }

        # Check viewer HTTP
        Write-Host "Checking viewer HTTP (http://localhost:8080)..."
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8080" -Method Head -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 302) {
                Write-Host "  " -NoNewline
                Write-Host "✓" -ForegroundColor Green
                Write-Host " Viewer HTTP server responding"
            }
            else {
                Write-Host "  " -NoNewline
                Write-Host "✗" -ForegroundColor Yellow
                Write-Host " Viewer HTTP server responded with $($response.StatusCode)"
            }
        }
        catch {
            Write-Host "  " -NoNewline
            Write-Host "✗" -ForegroundColor Yellow
            Write-Host " Viewer HTTP server not responding"
        }
    }
    catch {
        Write-Host "Unable to perform health checks: $_"
    }
}

function Show-SystemInfo {
    Write-Host ""
    Write-ColorLog "=== System Information ===" "Header"

    Write-Host "Platform: Windows"
    Write-Host "Hostname: $env:COMPUTERNAME"
    Write-Host "Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

    $os = Get-CimInstance -ClassName Win32_OperatingSystem
    $uptime = (Get-Date) - $os.LastBootUpTime
    Write-Host "Uptime: $($uptime.Days)d $($uptime.Hours)h $($uptime.Minutes)m"

    $venvDir = Join-Path $AelmaDir ".venv"
    if (Test-Path $venvDir) {
        Write-Host "Virtual environment: Found"
    }
    else {
        Write-Host "Virtual environment: " -NoNewline
        Write-Host "Not found" -ForegroundColor Red
    }
}

function Show-Usage {
    Write-Host ""
    Write-ColorLog "=== Quick Commands ===" "Header"
    Write-Host "Start all:   $ScriptDir\start.ps1"
    Write-Host "Stop all:    $ScriptDir\stop.ps1"
    Write-Host "View logs:   Get-Content $LogDir\*.log -Wait"
    Write-Host "Restart:    $ScriptDir\stop.ps1; $ScriptDir\start.ps1"
}

# Main execution
try {
    Write-Host ""
    Write-ColorLog "=== AELMA Component Status ===" "Header"
    Write-Host "Checking directory: $AelmaDir"

    # Check each component
    foreach ($component in $Components.Keys) {
        $info = $Components[$component]
        Show-ComponentStatus -Name $component -Port $info.Port -Description $info.Description
    }

    # Health checks
    Show-HealthChecks

    # System information
    Show-SystemInfo

    # Usage info
    Show-Usage

    Write-Host ""
}
catch {
    Write-ColorLog "Error checking status: $_" "Error"
    exit 1
}
