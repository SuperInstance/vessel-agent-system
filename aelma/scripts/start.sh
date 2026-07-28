#!/usr/bin/env bash
# AELMA Start Script
# Starts all AELMA components

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get script directory
AELMA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$AELMA_DIR/.venv"
PID_DIR="$AELMA_DIR/logs/pids"
LOG_DIR="$AELMA_DIR/logs"

# Create directories
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

# Check virtual environment
if [[ ! -d "$VENV_DIR" ]]; then
    log_error "Virtual environment not found. Run install.sh first."
    exit 1
fi

# Source virtual environment
source "$VENV_DIR/bin/activate"

# Check if ports are available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_error "Port $port is already in use"
        return 1
    fi
    return 0
}

# Start a component
start_component() {
    local name=$1
    local port=$2
    shift 2
    local cmd="$@"

    log_info "Starting $name on port $port..."

    # Check if already running
    if [[ -f "$PID_DIR/$name.pid" ]]; then
        local pid=$(cat "$PID_DIR/$name.pid")
        if ps -p $pid > /dev/null 2>&1; then
            log_warn "$name already running (PID: $pid)"
            return 0
        else
            rm "$PID_DIR/$name.pid"
        fi
    fi

    # Check port availability
    if ! check_port $port; then
        log_error "Cannot start $name - port $port unavailable"
        return 1
    fi

    # Start process
    cd "$AELMA_DIR"
    nohup $cmd > "$LOG_DIR/$name.log" 2>&1 &
    local pid=$!

    # Save PID
    echo $pid > "$PID_DIR/$name.pid"

    # Wait and check if process started successfully
    sleep 2
    if ps -p $pid > /dev/null 2>&1; then
        log_info "$name started (PID: $pid)"
        return 0
    else
        log_error "$name failed to start - check $LOG_DIR/$name.log"
        return 1
    fi
}

# Start all components
log_info "Starting AELMA components..."

# Start Bridge (TCP: 8001, WS: 8000)
start_component "bridge" 8000 \
    python -m bridge --tcp-port 8001 --ws-port 8000 || exit 1

# Wait for bridge to be ready
sleep 2

# Start Twin (Viewer WS: 8090)
start_component "twin" 8090 \
    python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090 || exit 1

# Wait for twin to be ready
sleep 2

# Start Viewer (HTTP: 8080)
start_component "viewer" 8080 \
    python build_kimi_viewer/serve.py --port 8080 || exit 1

# Optionally start simulator (for testing)
# start_component "simulator" 8001 \
#     python -m build_claude.simulator.simulate --duration-min 0.1 --speedup 30

# Summary
echo ""
log_info "AELMA components started successfully!"
echo ""
echo "Bridge:"
echo "  - NMEA TCP: localhost:8001"
echo "  - WebSocket: localhost:8000"
echo "  - Logs: $LOG_DIR/bridge.log"
echo ""
echo "Twin:"
echo "  - Viewer WebSocket: localhost:8090"
echo "  - Logs: $LOG_DIR/twin.log"
echo ""
echo "Viewer:"
echo "  - HTTP: http://localhost:8080"
echo "  - Logs: $LOG_DIR/viewer.log"
echo ""
echo "To view logs:"
echo "  tail -f $LOG_DIR/bridge.log"
echo "  tail -f $LOG_DIR/twin.log"
echo "  tail -f $LOG_DIR/viewer.log"
echo ""
echo "To stop AELMA:"
echo "  $AELMA_DIR/scripts/stop.sh"
echo ""
