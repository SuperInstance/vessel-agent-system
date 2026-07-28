# AELMA Installation Script for Windows
# Usage: .\install.ps1 [production|development]

param(
    [Parameter(Position=0)]
    [ValidateSet("development", "production")]
    [string]$Mode = "development"
)

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AelmaDir = Split-Path -Parent $ScriptDir
$VenvDir = Join-Path $AelmaDir ".venv"

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

function Test-PythonVersion {
    Write-ColorLog "Checking Python version..." "Info"

    try {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue

        if (-not $pythonCmd) {
            Write-ColorLog "Python 3 not found. Please install Python 3.12+ from https://www.python.org/downloads/" "Error"
            exit 1
        }

        $versionOutput = & python --version 2>&1
        if ($versionOutput -match "Python (\d+\.\d+)") {
            $pythonVersion = [version]$matches[1]
            $requiredVersion = [version]"3.12"

            if ($pythonVersion -lt $requiredVersion) {
                Write-ColorLog "Python 3.12 or higher required (found $($matches[1]))" "Error"
                exit 1
            }

            Write-ColorLog "Python version: $($matches[1])" "Info"
        }
    }
    catch {
        Write-ColorLog "Failed to check Python version: $_" "Error"
        exit 1
    }
}

function New-VirtualEnvironment {
    Write-ColorLog "Creating virtual environment..." "Info"

    try {
        if (Test-Path $VenvDir) {
            Write-ColorLog "Virtual environment already exists, recreating..." "Warn"
            Remove-Item -Path $VenvDir -Recurse -Force
        }

        & python -m venv $VenvDir

        # Upgrade pip
        $pipPath = Join-Path $VenvDir "Scripts" "pip.exe"
        & $pipPath install --upgrade pip | Out-Null

        Write-ColorLog "Virtual environment created at $VenvDir" "Info"
    }
    catch {
        Write-ColorLog "Failed to create virtual environment: $_" "Error"
        exit 1
    }
}

function Install-Dependencies {
    Write-ColorLog "Installing dependencies..." "Info"

    try {
        $pipPath = Join-Path $VenvDir "Scripts" "pip.exe"
        & $pipPath install websockets | Out-Null

        Write-ColorLog "Dependencies installed" "Info"
    }
    catch {
        Write-ColorLog "Failed to install dependencies: $_" "Error"
        exit 1
    }
}

function New-Directories {
    Write-ColorLog "Creating directories..." "Info"

    try {
        $logDir = Join-Path $AelmaDir "logs"
        $dataDir = Join-Path $AelmaDir "data"

        New-Item -Path $logDir -ItemType Directory -Force | Out-Null
        New-Item -Path $dataDir -ItemType Directory -Force | Out-Null

        Write-ColorLog "Directories created" "Info"
    }
    catch {
        Write-ColorLog "Failed to create directories: $_" "Error"
        exit 1
    }
}

function New-EnvironmentFile {
    Write-ColorLog "Creating environment file..." "Info"

    try {
        $envPath = Join-Path $AelmaDir ".env"

        @"
# AELMA Configuration
MODE=$Mode
PLATFORM=windows
VENV_DIR=$VenvDir

# Bridge
BRIDGE_TCP_PORT=8001
BRIDGE_WS_PORT=8000

# Twin
TWIN_BRIDGE_URL=ws://localhost:8000
TWIN_VIEWER_PORT=8090
TWIN_VESSEL_ID=US-AK-FVEILEEN-51
TWIN_BATHYMETRY_PATH=$AelmaDir\bathymetry.json

# Viewer
VIEWER_PORT=8080
"@ | Out-File -FilePath $envPath -Encoding utf8

        Write-ColorLog "Environment file created" "Info"
    }
    catch {
        Write-ColorLog "Failed to create environment file: $_" "Error"
        exit 1
    }
}

function New-ServiceScripts {
    Write-ColorLog "Creating service scripts..." "Info"

    try {
        $bridgeScript = @"
`$AelmaDir = "$AelmaDir"
`$VenvDir = "$VenvDir"
`$python = Join-Path `$VenvDir "Scripts" "python.exe"
Set-Location `$AelmaDir
& `$python -m bridge --tcp-port 8001 --ws-port 8000
"@

        $twinScript = @"
`$AelmaDir = "$AelmaDir"
`$VenvDir = "$VenvDir"
`$python = Join-Path `$VenvDir "Scripts" "python.exe"
Set-Location `$AelmaDir
& `$python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090
"@

        $viewerScript = @"
`$AelmaDir = "$AelmaDir"
`$VenvDir = "$VenvDir"
`$python = Join-Path `$VenvDir "Scripts" "python.exe"
Set-Location (Join-Path `$AelmaDir "build_kimi_viewer")
& `$python serve.py --port 8080
"@

        $bridgeScript | Out-File -FilePath (Join-Path $ScriptDir "run-bridge.ps1") -Encoding utf8
        $twinScript | Out-File -FilePath (Join-Path $ScriptDir "run-twin.ps1") -Encoding utf8
        $viewerScript | Out-File -FilePath (Join-Path $ScriptDir "run-viewer.ps1") -Encoding utf8

        Write-ColorLog "Service scripts created" "Info"
    }
    catch {
        Write-ColorLog "Failed to create service scripts: $_" "Error"
        exit 1
    }
}

function Show-Summary {
    Write-Host ""
    Write-ColorLog "Installation complete!" "Info"
    Write-Host ""
    Write-Host "Mode: $Mode"
    Write-Host "Platform: windows"
    Write-Host "Virtual Environment: $VenvDir"
    Write-Host ""
    Write-Host "To start AELMA:"
    Write-Host "  $ScriptDir\start.ps1"
    Write-Host ""
    Write-Host "To stop AELMA:"
    Write-Host "  $ScriptDir\stop.ps1"
    Write-Host ""
    Write-Host "To check status:"
    Write-Host "  $ScriptDir\status.ps1"
    Write-Host ""
}

# Main installation
try {
    Write-ColorLog "AELMA Installation - Mode: $Mode" "Info"
    Write-ColorLog "Installation directory: $AelmaDir" "Info"

    Test-PythonVersion
    New-VirtualEnvironment
    Install-Dependencies
    New-Directories
    New-EnvironmentFile
    New-ServiceScripts
    Show-Summary
}
catch {
    Write-ColorLog "Installation failed: $_" "Error"
    exit 1
}
