# AELMA Deployment Scripts

Quick reference for AELMA deployment scripts.

## Quick Start

```bash
# Install
./install.sh development

# Start
./start.sh

# Check status
./status.sh

# Stop
./stop.sh
```

## Scripts Overview

### Installation Scripts

**install.sh** (Linux/macOS)
- Checks Python 3.12+ availability
- Creates virtual environment
- Installs dependencies (websockets)
- Creates systemd service files (production mode)
- Sets up directories and permissions

**install.ps1** (Windows)
- Same features as install.sh
- Creates PowerShell service scripts
- Configures Windows-specific paths

### Service Management Scripts

**start.sh** (Linux/macOS)
- Starts all components: bridge, twin, viewer
- Checks port availability
- Manages PIDs
- Logs to `/logs/` directory

**start.ps1** (Windows)
- Same features as start.sh
- Windows-specific process management

**stop.sh** (Linux/macOS)
- Gracefully stops all components
- Waits for cleanup
- Verifies termination
- Cleans up PID files

**stop.ps1** (Windows)
- Same features as stop.sh
- Windows process termination

**status.sh** (Linux/macOS)
- Shows component status
- Displays PID, uptime, port status
- Shows recent log entries
- Performs health checks

**status.ps1** (Windows)
- Same features as status.sh
- Windows process information

## Usage Examples

### Development Mode

```bash
# Initial setup
./install.sh development

# Start services
./start.sh

# Check status
./status.sh

# View logs
tail -f logs/bridge.log
tail -f logs/twin.log
tail -f logs/viewer.log

# Stop services
./stop.sh
```

### Production Mode (Linux)

```bash
# Initial setup
sudo ./install.sh production

# Install to /opt
sudo cp -r . /opt/aelma/
sudo chown -R aelma:aelma /opt/aelma

# Install services
sudo cp scripts/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable aelma-bridge aelma-twin aelma-viewer
sudo systemctl start aelma-bridge aelma-twin aelma-viewer

# Check status
sudo systemctl status aelma-bridge
```

### Production Mode (macOS)

```bash
# Initial setup
sudo ./install.sh production

# Load launch agents
launchctl load ~/Library/LaunchAgents/com.aelma.*.plist

# Check status
launchctl list | grep aelma
```

### Production Mode (Windows)

```powershell
# Initial setup
.\install.ps1 production

# Create scheduled tasks
# (see deployment.md for details)

# Start services
.\start.ps1
```

## Component Details

### Bridge (NMEA to WebSocket)

- **Ports**: TCP 8001 (NMEA), WS 8000 (telemetry)
- **Command**: `python -m bridge --tcp-port 8001 --ws-port 8000`
- **Log**: `logs/bridge.log`
- **PID**: `logs/pids/bridge.pid`

### Twin (Digital Twin)

- **Ports**: WS 8090 (viewer connection)
- **Command**: `python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090`
- **Log**: `logs/twin.log`
- **PID**: `logs/pids/twin.pid`
- **Dependency**: Requires bridge

### Viewer (Web Interface)

- **Ports**: HTTP 8080 (web UI)
- **Command**: `python build_kimi_viewer/serve.py --port 8080`
- **Log**: `logs/viewer.log`
- **PID**: `logs/pids/viewer.pid`

### Simulator (Optional)

- **Ports**: TCP 8001 (NMEA output)
- **Command**: `python -m build_claude.simulator.simulate --duration-min 0.1 --speedup 30`
- **Log**: `logs/simulator.log`
- **PID**: `logs/pids/simulator.pid`

## Directory Structure

```
aelma/
├── scripts/
│   ├── install.sh          # Installation script (Linux/macOS)
│   ├── install.ps1         # Installation script (Windows)
│   ├── start.sh            # Start script (Linux/macOS)
│   ├── start.ps1           # Start script (Windows)
│   ├── stop.sh             # Stop script (Linux/macOS)
│   ├── stop.ps1            # Stop script (Windows)
│   ├── status.sh           # Status script (Linux/macOS)
│   ├── status.ps1          # Status script (Windows)
│   └── systemd/            # Systemd service files
│       ├── aelma-bridge.service
│       ├── aelma-twin.service
│       ├── aelma-viewer.service
│       └── aelma-simulator.service
├── logs/                   # Log files
│   ├── pids/              # Process IDs
│   ├── bridge.log
│   ├── twin.log
│   ├── viewer.log
│   └── simulator.log
├── data/                   # Runtime data
├── .env                    # Configuration
└── .venv/                  # Virtual environment
```

## Environment Variables

Edit `.env` to customize:

```bash
# Mode
MODE=development
PLATFORM=linux

# Virtual Environment
VENV_DIR=/opt/aelma/.venv

# Bridge
BRIDGE_TCP_PORT=8001
BRIDGE_WS_PORT=8000

# Twin
TWIN_BRIDGE_URL=ws://localhost:8000
TWIN_VIEWER_PORT=8090
TWIN_VESSEL_ID=US-AK-FVEILEEN-51
TWIN_BATHYMETRY_PATH=/opt/aelma/bathymetry.json

# Viewer
VIEWER_PORT=8080
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
sudo lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in .env
```

### Permission Denied

```bash
# Fix permissions
sudo chown -R $USER:$USER /opt/aelma
chmod +x scripts/*.sh
```

### Service Won't Start

```bash
# Check logs
tail -f logs/*.log

# Try manual start with debug
python -m bridge --debug
```

### Virtual Environment Issues

```bash
# Recreate venv
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install websockets
```

## Testing

Run deployment tests:

```bash
python tests/deployment.test.py
```

## Platform Support

| Platform | Install Script | Service Manager | Status |
|----------|---------------|-----------------|--------|
| Linux (Debian/Ubuntu) | install.sh | systemd | ✓ Supported |
| Linux (RHEL/CentOS) | install.sh | systemd | ✓ Supported |
| Linux (Alpine) | install.sh | OpenRC | ✓ Supported |
| macOS (10.15+) | install.sh | launchd | ✓ Supported |
| Windows (10+) | install.ps1 | Scheduled Task | ✓ Supported |

## System Requirements

- **Python**: 3.12+
- **RAM**: 2 GB minimum, 4 GB recommended
- **Storage**: 500 MB free space
- **Network**: Local loopback (127.0.0.1)

## Security Notes

- Development mode runs as user (no privilege isolation)
- Production mode creates dedicated user
- Systemd services include security hardening
- Configure firewall for production
- Use TLS/SSL for remote access

## Documentation

Full deployment guide: `docs/deployment.md`

## Support

Issues: https://github.com/SuperInstance/aelma/issues
