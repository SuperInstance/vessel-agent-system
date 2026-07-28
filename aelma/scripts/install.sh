#!/usr/bin/env bash
# AELMA Installation Script
# Supports: Linux (systemd/user), macOS (launchd/user)
# Usage: sudo ./install.sh [production|development]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Default arguments
MODE="${1:-development}"
AELMA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$AELMA_DIR/.venv"
LOG_DIR="/var/log/aelma"
DATA_DIR="/var/lib/aelma"
SERVICE_NAME="aelma"

log_info "AELMA Installation - Mode: $MODE"
log_info "Installation directory: $AELMA_DIR"

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
else
    log_error "Unsupported platform: $OSTYPE"
    exit 1
fi
log_info "Platform: $PLATFORM"

# Check Python
check_python() {
    log_info "Checking Python version..."

    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3.12+"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    REQUIRED_VERSION="3.12"

    if [[ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]]; then
        log_error "Python $REQUIRED_VERSION or higher required (found $PYTHON_VERSION)"
        exit 1
    fi

    log_info "Python version: $PYTHON_VERSION ✓"
}

# Create virtual environment
create_venv() {
    log_info "Creating virtual environment..."

    if [[ -d "$VENV_DIR" ]]; then
        log_warn "Virtual environment already exists, recreating..."
        rm -rf "$VENV_DIR"
    fi

    python3 -m venv "$VENV_DIR"

    # Activate and upgrade pip
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip

    log_info "Virtual environment created at $VENV_DIR"
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."

    source "$VENV_DIR/bin/activate"

    # Install only websockets dependency
    pip install websockets

    log_info "Dependencies installed"
}

# Create directories
create_directories() {
    log_info "Creating directories..."

    if [[ "$MODE" == "production" ]]; then
        # Production: system directories
        if [[ "$PLATFORM" == "linux" ]]; then
            sudo mkdir -p "$LOG_DIR"
            sudo mkdir -p "$DATA_DIR"
            sudo chown -R $(whoami):$(whoami) "$LOG_DIR" "$DATA_DIR"
            sudo chmod 755 "$LOG_DIR" "$DATA_DIR"
        else
            # User mode for macOS
            mkdir -p "$HOME/Library/Logs/aelma"
            mkdir -p "$HOME/Library/Application Support/aelma"
        fi
    else
        # Development: local directories
        mkdir -p "$AELMA_DIR/logs"
        mkdir -p "$AELMA_DIR/data"
    fi

    log_info "Directories created"
}

# Create systemd service (Linux production)
create_systemd_service() {
    if [[ "$MODE" != "production" ]] || [[ "$PLATFORM" != "linux" ]]; then
        return
    fi

    log_info "Creating systemd service..."

    # Create bridge service
    sudo tee /etc/systemd/system/aelma-bridge.service > /dev/null <<EOF
[Unit]
Description=AELMA NMEA Bridge
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$AELMA_DIR
Environment="PATH=$VENV_DIR/bin:/usr/bin"
ExecStart=$VENV_DIR/bin/python -m bridge --tcp-port 8001 --ws-port 8000
Restart=on-failure
RestartSec=5
StandardOutput=append:$LOG_DIR/bridge.log
StandardError=append:$LOG_DIR/bridge.log

[Install]
WantedBy=multi-user.target
EOF

    # Create twin service
    sudo tee /etc/systemd/system/aelma-twin.service > /dev/null <<EOF
[Unit]
Description=AELMA Digital Twin
After=network.target aelma-bridge.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$AELMA_DIR
Environment="PATH=$VENV_DIR/bin:/usr/bin"
ExecStart=$VENV_DIR/bin/python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090
Restart=on-failure
RestartSec=5
StandardOutput=append:$LOG_DIR/twin.log
StandardError=append:$LOG_DIR/twin.log

[Install]
WantedBy=multi-user.target
EOF

    # Create viewer service
    sudo tee /etc/systemd/system/aelma-viewer.service > /dev/null <<EOF
[Unit]
Description=AELMA Viewer
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$AELMA_DIR/build_kimi_viewer
Environment="PATH=$VENV_DIR/bin:/usr/bin"
ExecStart=$VENV_DIR/bin/python serve.py --port 8080
Restart=on-failure
RestartSec=5
StandardOutput=append:$LOG_DIR/viewer.log
StandardError=append:$LOG_DIR/viewer.log

[Install]
WantedBy=multi-user.target
EOF

    # Create simulator service (optional)
    sudo tee /etc/systemd/system/aelma-simulator.service > /dev/null <<EOF
[Unit]
Description=AELMA NMEA Simulator
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$AELMA_DIR
Environment="PATH=$VENV_DIR/bin:/usr/bin"
ExecStart=$VENV_DIR/bin/python -m build_claude.simulator.simulate --duration-min 0.1 --speedup 30
Restart=on-failure
RestartSec=5
StandardOutput=append:$LOG_DIR/simulator.log
StandardError=append:$LOG_DIR/simulator.log

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    sudo systemctl daemon-reload

    log_info "Systemd services created"
}

# Create launchd plist (macOS production)
create_launchd_service() {
    if [[ "$MODE" != "production" ]] || [[ "$PLATFORM" != "macos" ]]; then
        return
    fi

    log_info "Creating launchd services..."

    AGENT_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$AGENT_DIR"

    # Create bridge agent
    cat > "$AGENT_DIR/com.aelma.bridge.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aelma.bridge</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>-m</string>
        <string>bridge</string>
        <string>--tcp-port</string>
        <string>8001</string>
        <string>--ws-port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$AELMA_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/aelma/bridge.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/aelma/bridge.log</string>
</dict>
</plist>
EOF

    # Create twin agent
    cat > "$AGENT_DIR/com.aelma.twin.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aelma.twin</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>-m</string>
        <string>twin</string>
        <string>--bridge-url</string>
        <string>ws://localhost:8000</string>
        <string>--viewer-port</string>
        <string>8090</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$AELMA_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/aelma/twin.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/aelma/twin.log</string>
</dict>
</plist>
EOF

    log_info "Launchd services created"
}

# Set permissions
set_permissions() {
    log_info "Setting permissions..."

    chmod +x "$AELMA_DIR/scripts"/*.sh

    if [[ "$MODE" == "production" ]]; then
        if [[ "$PLATFORM" == "linux" ]]; then
            sudo chown -R $(whoami):$(whoami) "$LOG_DIR" "$DATA_DIR"
        fi
    fi

    log_info "Permissions set"
}

# Create environment file
create_env_file() {
    log_info "Creating environment file..."

    cat > "$AELMA_DIR/.env" <<EOF
# AELMA Configuration
MODE=$MODE
PLATFORM=$PLATFORM
VENV_DIR=$VENV_DIR

# Bridge
BRIDGE_TCP_PORT=8001
BRIDGE_WS_PORT=8000

# Twin
TWIN_BRIDGE_URL=ws://localhost:8000
TWIN_VIEWER_PORT=8090
TWIN_VESSEL_ID=US-AK-FVEILEEN-51
TWIN_BATHYMETRY_PATH=$AELMA_DIR/bathymetry.json

# Viewer
VIEWER_PORT=8080
EOF

    log_info "Environment file created"
}

# Print summary
print_summary() {
    echo ""
    log_info "Installation complete!"
    echo ""
    echo "Mode: $MODE"
    echo "Platform: $PLATFORM"
    echo "Virtual Environment: $VENV_DIR"
    echo ""

    if [[ "$MODE" == "development" ]]; then
        echo "To start AELMA:"
        echo "  $AELMA_DIR/scripts/start.sh"
        echo ""
        echo "To stop AELMA:"
        echo "  $AELMA_DIR/scripts/stop.sh"
        echo ""
        echo "To check status:"
        echo "  $AELMA_DIR/scripts/status.sh"
    else
        if [[ "$PLATFORM" == "linux" ]]; then
            echo "To start AELMA:"
            echo "  sudo systemctl start aelma-bridge aelma-twin aelma-viewer"
            echo ""
            echo "To stop AELMA:"
            echo "  sudo systemctl stop aelma-bridge aelma-twin aelma-viewer"
            echo ""
            echo "To check status:"
            echo "  sudo systemctl status aelma-*"
            echo ""
            echo "To enable at boot:"
            echo "  sudo systemctl enable aelma-bridge aelma-twin aelma-viewer"
        else
            echo "To start AELMA:"
            echo "  launchctl load ~/Library/LaunchAgents/com.aelma.*.plist"
            echo ""
            echo "To stop AELMA:"
            echo "  launchctl unload ~/Library/LaunchAgents/com.aelma.*.plist"
            echo ""
            echo "To check status:"
            echo "  launchctl list | grep aelma"
        fi
    fi
    echo ""
}

# Run installation
main() {
    check_python
    create_venv
    install_dependencies
    create_directories
    create_systemd_service
    create_launchd_service
    set_permissions
    create_env_file
    print_summary
}

main
