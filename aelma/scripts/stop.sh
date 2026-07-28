#!/usr/bin/env bash
# AELMA Stop Script
# Gracefully stops all AELMA components

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
PID_DIR="$AELMA_DIR/logs/pids"

# Components to stop (in reverse order of startup)
COMPONENTS=("viewer" "twin" "bridge")

# Stop a component
stop_component() {
    local name=$1
    local pid_file="$PID_DIR/$name.pid"

    if [[ ! -f "$pid_file" ]]; then
        log_warn "$name: PID file not found (may not be running)"
        return 0
    fi

    local pid=$(cat "$pid_file")

    if ! ps -p $pid > /dev/null 2>&1; then
        log_warn "$name: Process $pid not running (stale PID file)"
        rm -f "$pid_file"
        return 0
    fi

    log_info "Stopping $name (PID: $pid)..."

    # Send SIGTERM for graceful shutdown
    kill -TERM $pid 2>/dev/null || true

    # Wait for process to terminate (max 10 seconds)
    local count=0
    while ps -p $pid > /dev/null 2>&1 && [[ $count -lt 10 ]]; do
        sleep 1
        count=$((count + 1))
    done

    # Force kill if still running
    if ps -p $pid > /dev/null 2>&1; then
        log_warn "$name: Still running after 10s, forcing shutdown..."
        kill -KILL $pid 2>/dev/null || true
        sleep 1
    fi

    # Verify termination
    if ps -p $pid > /dev/null 2>&1; then
        log_error "$name: Failed to stop process $pid"
        return 1
    else
        log_info "$name: Stopped successfully"
        rm -f "$pid_file"
        return 0
    fi
}

# Stop all components
log_info "Stopping AELMA components..."

for component in "${COMPONENTS[@]}"; do
    stop_component "$component"
done

# Clean up PID directory
if [[ -d "$PID_DIR" ]] && [[ -z "$(ls -A $PID_DIR)" ]]; then
    rmdir "$PID_DIR"
fi

# Verify all processes stopped
log_info "Verifying all processes stopped..."

# Check for any remaining AELMA processes
REMAINING=$(ps aux | grep -E "(bridge|twin|viewer)" | grep -E "python.*aelma" | grep -v grep || true)

if [[ -n "$REMAINING" ]]; then
    log_warn "Found remaining AELMA processes:"
    echo "$REMAINING"
    log_warn "You may need to manually terminate them"
else
    log_info "All AELMA processes stopped successfully"
fi

echo ""
