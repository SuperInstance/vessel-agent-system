#!/usr/bin/env bash
# AELMA Status Script
# Checks status of all AELMA components

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_header() { echo -e "${BLUE}$1${NC}"; }

# Get script directory
AELMA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$AELMA_DIR/logs/pids"
LOG_DIR="$AELMA_DIR/logs"

# Component definitions
declare -A COMPONENT_PORTS=(
    ["bridge"]="8000"
    ["twin"]="8090"
    ["viewer"]="8080"
)

declare -A COMPONENT_DESC=(
    ["bridge"]="NMEA Bridge (TCP:8001, WS:8000)"
    ["twin"]="Digital Twin (Viewer WS:8090)"
    ["viewer"]="Web Viewer (HTTP:8080)"
)

# Check if a process is running
is_process_running() {
    local pid=$1
    ps -p $pid > /dev/null 2>&1
}

# Get process uptime
get_uptime() {
    local pid=$1
    if command -v ps > /dev/null 2>&1; then
        ps -p $pid -o etime= 2>/dev/null | xargs || echo "Unknown"
    else
        echo "Unknown"
    fi
}

# Check port status
check_port() {
    local port=$1
    if command -v lsof > /dev/null 2>&1; then
        lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1
        return $?
    elif command -v netstat > /dev/null 2>&1; then
        netstat -tuln 2>/dev/null | grep ":$port " > /dev/null
        return $?
    else
        return 2 # Cannot check
    fi
}

# Check component status
check_component() {
    local name=$1
    local port="${COMPONENT_PORTS[$name]}"
    local pid_file="$PID_DIR/$name.pid"
    local log_file="$LOG_DIR/$name.log"

    echo ""
    log_header "=== $name: ${COMPONENT_DESC[$name]} ==="

    # Check PID file
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if is_process_running $pid; then
            local uptime=$(get_uptime $pid)
            echo -e "  Status: ${GREEN}Running${NC}"
            echo "  PID: $pid"
            echo "  Uptime: $uptime"
            echo "  PID file: $pid_file"
        else
            echo -e "  Status: ${RED}Not Running (stale PID file)${NC}"
            echo "  PID file: $pid_file"
        fi
    else
        echo -e "  Status: ${YELLOW}Stopped (no PID file)${NC}"
    fi

    # Check port
    if check_port $port; then
        echo -e "  Port $port: ${GREEN}Listening${NC}"
    elif [[ $? -eq 2 ]]; then
        echo "  Port $port: Unable to check"
    else
        echo -e "  Port $port: ${RED}Not listening${NC}"
    fi

    # Check log file
    if [[ -f "$log_file" ]]; then
        local log_size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo "0")
        local log_mtime=$(stat -f%Sm "$log_file" 2>/dev/null || stat -c%y "$log_file" 2>/dev/null || echo "Unknown")
        echo "  Log file: $log_file"
        echo "  Log size: $log_size bytes"
        echo "  Log modified: $log_mtime"

        # Show last log line
        if [[ $log_size -gt 0 ]]; then
            echo "  Last log entry:"
            tail -1 "$log_file" | sed 's/^/    /'
        fi
    else
        echo "  Log file: Not found"
    fi
}

# Health check for services
health_check() {
    echo ""
    log_header "=== Health Checks ==="

    # Check if bridge WebSocket is accessible
    if command -v curl > /dev/null 2>&1; then
        echo "Checking bridge WebSocket (ws://localhost:8000)..."
        if curl -s -I -N http://localhost:8000 2>/dev/null | head -n 1 | grep -q "400\|101\|Upgrade"; then
            echo -e "  ${GREEN}✓${NC} Bridge WebSocket server responding"
        else
            echo -e "  ${YELLOW}✗${NC} Bridge WebSocket server not responding"
        fi

        echo "Checking twin WebSocket (ws://localhost:8090)..."
        if curl -s -I -N http://localhost:8090 2>/dev/null | head -n 1 | grep -q "400\|101\|Upgrade"; then
            echo -e "  ${GREEN}✓${NC} Twin WebSocket server responding"
        else
            echo -e "  ${YELLOW}✗${NC} Twin WebSocket server not responding"
        fi

        echo "Checking viewer HTTP (http://localhost:8080)..."
        if curl -s -I http://localhost:8080 2>/dev/null | head -n 1 | grep -q "200\|302"; then
            echo -e "  ${GREEN}✓${NC} Viewer HTTP server responding"
        else
            echo -e "  ${YELLOW}✗${NC} Viewer HTTP server not responding"
        fi
    else
        echo "curl not available - skipping health checks"
    fi
}

# System information
system_info() {
    echo ""
    log_header "=== System Information ==="

    echo "Platform: $(uname -s)"
    echo "Hostname: $(hostname)"
    echo "Date: $(date)"
    echo "Uptime: $(uptime 2>/dev/null || echo 'Unknown')"

    if [[ -d "$VENV_DIR" ]]; then
        echo "Virtual environment: Found"
    else
        echo -e "Virtual environment: ${RED}Not found${NC}"
    fi
}

# Print usage info
print_usage() {
    echo ""
    log_header "=== Quick Commands ==="
    echo "Start all:   $AELMA_DIR/scripts/start.sh"
    echo "Stop all:    $AELMA_DIR/scripts/stop.sh"
    echo "View logs:   tail -f $LOG_DIR/*.log"
    echo "Restart:     $AELMA_DIR/scripts/stop.sh && $AELMA_DIR/scripts/start.sh"
}

# Main execution
echo ""
log_header "=== AELMA Component Status ==="
echo "Checking directory: $AELMA_DIR"

# Check each component
for component in "bridge" "twin" "viewer"; do
    check_component "$component"
done

# Health checks
health_check

# System information
system_info

# Usage info
print_usage

echo ""
