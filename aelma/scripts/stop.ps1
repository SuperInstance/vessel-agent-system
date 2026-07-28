# AELMA Stop Script for Windows
# Gracefully stops all AELMA components

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AelmaDir = Split-Path -Parent $ScriptDir
$PidDir = Join-Path $AelmaDir "logs\pids"

# Components to stop (in reverse order of startup)
$Components = @("viewer", "twin", "bridge")

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

function Stop-Component {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Name
    )

    $pidFile = Join-Path $PidDir "$Name.pid"

    if (-not (Test-Path $pidFile)) {
        Write-ColorLog "$Name`: PID file not found (may not be running)" "Warn"
        return $true
    }

    try {
        $pid = Get-Content $pidFile -ErrorAction Stop
    }
    catch {
        Write-ColorLog "$Name`: Failed to read PID file" "Error"
        return $false
    }

    try {
        $process = Get-Process -Id $pid -ErrorAction Stop
    }
    catch {
        Write-ColorLog "$Name`: Process $pid not running (stale PID file)" "Warn"
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        return $true
    }

    Write-ColorLog "Stopping $Name (PID: $pid)..." "Info"

    try {
        # Send SIGTERM for graceful shutdown
        $process.CloseMainWindow() | Out-Null

        # Wait for process to terminate (max 10 seconds)
        $count = 0
        while (-not $process.HasExited -and $count -lt 10) {
            Start-Sleep -Seconds 1
            $count++
            $process.Refresh()
        }

        # Force kill if still running
        if (-not $process.HasExited) {
            Write-ColorLog "$Name`: Still running after 10s, forcing shutdown..." "Warn"
            $process.Kill()
            Start-Sleep -Seconds 1
            $process.Refresh()
        }

        # Verify termination
        if ($process.HasExited) {
            Write-ColorLog "$Name`: Stopped successfully" "Info"
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            return $true
        }
        else {
            Write-ColorLog "$Name`: Failed to stop process $pid" "Error"
            return $false
        }
    }
    catch {
        Write-ColorLog "$Name`: Error stopping process: $_" "Error"
        return $false
    }
}

# Main execution
try {
    Write-ColorLog "Stopping AELMA components..." "Info"

    foreach ($component in $Components) {
        Stop-Component -Name $component
    }

    # Clean up PID directory if empty
    if (Test-Path $PidDir) {
        $pidFiles = Get-ChildItem $PidDir -Filter "*.pid"
        if (-not $pidFiles) {
            Remove-Item $PidDir -Force -ErrorAction SilentlyContinue
        }
    }

    # Verify all processes stopped
    Write-ColorLog "Verifying all processes stopped..." "Info"

    # Check for any remaining AELMA processes
    $remainingProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*aelma*" -or
        $_.CommandLine -like "*bridge*" -or
        $_.CommandLine -like "*twin*" -or
        $_.CommandLine -like "*viewer*"
    }

    if ($remainingProcesses) {
        Write-ColorLog "Found remaining AELMA processes:" "Warn"
        $remainingProcesses | ForEach-Object {
            Write-Host "  - PID: $($_.Id), Command: $($_.CommandLine)"
        }
        Write-ColorLog "You may need to manually terminate them" "Warn"
    }
    else {
        Write-ColorLog "All AELMA processes stopped successfully" "Info"
    }

    Write-Host ""
}
catch {
    Write-ColorLog "Error stopping AELMA: $_" "Error"
    exit 1
}
