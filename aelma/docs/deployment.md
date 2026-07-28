# AELMA Deployment Guide

Complete guide for deploying AELMA (Autonomous Edge Linux Maritime Agent) on vessels.

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Quick Start](#quick-start)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
- [Platform-Specific Instructions](#platform-specific-instructions)
- [Service Management](#service-management)
- [Troubleshooting](#troubleshooting)
- [Security Hardening](#security-hardening)
- [Testing](#testing)

---

## Overview

AELMA consists of four main components:

1. **Bridge** - NMEA 0183 to WebSocket bridge (Ports: TCP 8001, WS 8000)
2. **Twin** - Digital twin core (Port: WS 8090)
3. **Viewer** - Web-based visualization (Port: HTTP 8080)
4. **Simulator** - NMEA simulator for testing (Optional)

### Deployment Modes

- **Development**: User-space processes, local directories
- **Production**: System services (systemd/launchd), system directories

### Supported Platforms

- Linux (Debian/Ubuntu, RHEL/CentOS, Alpine)
- macOS (10.15+)
- Windows (10/11, Server 2019+)

---

## System Requirements

### Minimum Requirements

- **CPU**: 2-core processor (x86_64 or ARM64)
- **RAM**: 2 GB minimum, 4 GB recommended
- **Storage**: 500 MB free space
- **Network**: Local loopback (127.0.0.1)

### Software Requirements

- **Python**: 3.12 or higher
- **pip**: Latest version
- **git**: For cloning repository

### Port Requirements

| Component | Protocol | Port | Direction |
|-----------|----------|------|-----------|
| Bridge | TCP | 8001 | Inbound (NMEA) |
| Bridge | WebSocket | 8000 | Outbound (telemetry) |
| Twin | WebSocket | 8090 | Outbound (viewer) |
| Viewer | HTTP | 8080 | Outbound (web) |

### Network Configuration

- Open ports in firewall (if enabled)
- Allow loopback connections
- For remote access: configure port forwarding

---

## Quick Start

### Clone Repository

```bash
git clone https://github.com/SuperInstance/aelma.git
cd aelma
```

### Run Installation

**Linux/macOS:**
```bash
sudo ./scripts/install.sh development
```

**Windows (PowerShell):**
```powershell
.\scripts\install.ps1 development
```

### Start Services

**Linux/macOS:**
```bash
./scripts/start.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\start.ps1
```

### Verify Deployment

Open browser: http://localhost:8080

Check status:
```bash
./scripts/status.sh
```

---

## Development Deployment

Development mode runs services as user processes with local directories.

### Installation

**Linux/macOS:**
```bash
./scripts/install.sh development
```

**Windows:**
```powershell
.\scripts\install.ps1 development
```

### What Gets Created

- **Virtual Environment**: `.venv/`
- **Log Directory**: `logs/`
- **PID Directory**: `logs/pids/`
- **Data Directory**: `data/`
- **Environment File**: `.env`

### Directory Structure

```
aelma/
├── .venv/              # Virtual environment
├── logs/                # Log files
│   ├── pids/           # Process IDs
│   ├── bridge.log
│   ├── twin.log
│   └── viewer.log
├── data/                # Runtime data
├── .env                 # Configuration
└── scripts/             # Management scripts
```

### Starting Services

```bash
./scripts/start.sh
```

Output:
```
[INFO] Starting AELMA components...
[INFO] Starting bridge on port 8000...
[INFO] bridge started (PID: 12345)
[INFO] Starting twin on port 8090...
[INFO] twin started (PID: 12346)
[INFO] Starting viewer on port 8080...
[INFO] viewer started (PID: 12347)
```

### Stopping Services

```bash
./scripts/stop.sh
```

Output:
```
[INFO] Stopping AELMA components...
[INFO] Stopping viewer (PID: 12347)...
[INFO] viewer: Stopped successfully
[INFO] Stopping twin (PID: 12346)...
[INFO] twin: Stopped successfully
[INFO] Stopping bridge (PID: 12345)...
[INFO] bridge: Stopped successfully
```

### Checking Status

```bash
./scripts/status.sh
```

Output:
```
=== AELMA Component Status ===

=== bridge: NMEA Bridge (TCP:8001, WS:8000) ===
  Status: Running
  PID: 12345
  Uptime: 00:15:32
  Port 8000: Listening
  Port 8001: Listening
  Log file: /path/to/logs/bridge.log
  Last log entry:
    2024-07-27 10:30:45 [bridge] INFO: NMEA bridge running

=== twin: Digital Twin (Viewer WS:8090) ===
  Status: Running
  PID: 12346
  Uptime: 00:15:30
  Port 8090: Listening
  Log file: /path/to/logs/twin.log

=== viewer: Web Viewer (HTTP:8080) ===
  Status: Running
  PID: 12347
  Uptime: 00:15:28
  Port 8080: Listening
  Log file: /path/to/logs/viewer.log
```

### Viewing Logs

```bash
# All logs
tail -f logs/*.log

# Specific component
tail -f logs/bridge.log

# Search logs
grep "ERROR" logs/*.log
```

---

## Production Deployment

Production mode runs as system services with proper security and persistence.

### Linux Production

#### Installation

```bash
sudo ./scripts/install.sh production
```

#### What Gets Created

- **Virtual Environment**: `/opt/aelma/.venv/`
- **Log Directory**: `/var/log/aelma/`
- **Data Directory**: `/var/lib/aelma/`
- **Service Files**: `/etc/systemd/system/aelma-*.service`
- **System User**: `aelma`

#### Creating System User

```bash
sudo useradd -r -s /bin/false -d /var/lib/aelma aelma
sudo mkdir -p /opt/aelma /var/log/aelma /var/lib/aelma
sudo chown -R aelma:aelma /opt/aelma /var/log/aelma /var/lib/aelma
```

#### Installing to /opt/aelma

```bash
sudo cp -r . /opt/aelma/
sudo chown -R aelma:aelma /opt/aelma
```

#### Installing Systemd Services

```bash
sudo cp scripts/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
```

#### Enabling Services

```bash
# Enable at boot
sudo systemctl enable aelma-bridge
sudo systemctl enable aelma-twin
sudo systemctl enable aelma-viewer

# Start now
sudo systemctl start aelma-bridge
sudo systemctl start aelma-twin
sudo systemctl start aelma-viewer
```

#### Managing Services

```bash
# Check status
sudo systemctl status aelma-bridge

# View logs
sudo journalctl -u aelma-bridge -f

# Restart
sudo systemctl restart aelma-bridge

# Stop
sudo systemctl stop aelma-bridge

# Disable
sudo systemctl disable aelma-bridge
```

#### Service Dependencies

```
aelma-twin.service
    └─ Requires: aelma-bridge.service
        └─ After: network.target

aelma-viewer.service
    └─ After: network.target
```

### macOS Production

#### Installation

```bash
sudo ./scripts/install.sh production
```

#### What Gets Created

- **Virtual Environment**: `/opt/aelma/.venv/`
- **Log Directory**: `~/Library/Logs/aelma/`
- **Data Directory**: `~/Library/Application Support/aelma/`
- **Launch Agents**: `~/Library/LaunchAgents/com.aelma.*.plist`

#### Installing Launch Agents

```bash
cp scripts/launchd/*.plist ~/Library/LaunchAgents/
```

#### Loading Services

```bash
# Load all services
launchctl load ~/Library/LaunchAgents/com.aelma.*.plist

# Unload all services
launchctl unload ~/Library/LaunchAgents/com.aelma.*.plist
```

#### Managing Services

```bash
# List services
launchctl list | grep aelma

# View logs
log show --predicate 'process == "aelma-bridge"' --info

# Start service
launchctl start com.aelma.bridge

# Stop service
launchctl stop com.aelma.bridge
```

### Windows Production

Windows production deployment uses scheduled tasks or runs as a service with NSSM.

#### Installation

```powershell
.\scripts\install.ps1 production
```

#### Creating Scheduled Tasks

```powershell
# Create bridge task
$action = New-ScheduledTaskAction -Execute "C:\aelma\.venv\Scripts\python.exe" -Argument "-m bridge --tcp-port 8001 --ws-port 8000" -WorkingDirectory "C:\aelma"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "AELMA Bridge" -Action $action -Trigger $trigger -Principal $principal
```

#### Managing Tasks

```powershell
# Start task
Start-ScheduledTask -TaskName "AELMA Bridge"

# Stop task
Stop-ScheduledTask -TaskName "AELMA Bridge"

# Check status
Get-ScheduledTask -TaskName "AELMA Bridge"

# View logs
Get-ScheduledTaskInfo -TaskName "AELMA Bridge"
```

---

## Platform-Specific Instructions

### Debian/Ubuntu

```bash
# Install dependencies
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip git

# Install AELMA
git clone https://github.com/SuperInstance/aelma.git
cd aelma
sudo ./scripts/install.sh production

# Start services
sudo systemctl start aelma-bridge aelma-twin aelma-viewer
```

### RHEL/CentOS

```bash
# Install dependencies
sudo dnf install python3.12 python3.12-pip git

# Install AELMA
git clone https://github.com/SuperInstance/aelma.git
cd aelma
sudo ./scripts/install.sh production

# Start services
sudo systemctl start aelma-bridge aelma-twin aelma-viewer
```

### Alpine Linux

```bash
# Install dependencies
sudo apk add python3 py3-pip git

# Install AELMA
git clone https://github.com/SuperInstance/aelma.git
cd aelma
sudo ./scripts/install.sh production

# Start services
sudo rc-service aelma-bridge start
sudo rc-service aelma-twin start
sudo rc-service aelma-viewer start
```

### macOS

```bash
# Install Python 3.12
brew install python@3.12

# Install AELMA
git clone https://github.com/SuperInstance/aelma.git
cd aelma
sudo ./scripts/install.sh production

# Load services
launchctl load ~/Library/LaunchAgents/com.aelma.*.plist
```

### Windows

```powershell
# Install Python 3.12 from https://www.python.org/downloads/

# Clone repository
git clone https://github.com/SuperInstance/aelma.git
cd aelma

# Install AELMA
.\scripts\install.ps1 production

# Start services
.\scripts\start.ps1
```

---

## Service Management

### Lifecycle Management

```bash
# Development mode
./scripts/start.sh    # Start all services
./scripts/stop.sh     # Stop all services
./scripts/status.sh   # Check status

# Production mode (Linux)
sudo systemctl start aelma-bridge     # Start bridge
sudo systemctl stop aelma-bridge      # Stop bridge
sudo systemctl restart aelma-bridge   # Restart bridge
sudo systemctl status aelma-bridge    # Check status
```

### Individual Component Control

**Development Mode:**

```bash
# Start only bridge
python -m bridge --tcp-port 8001 --ws-port 8000

# Start only twin
python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090

# Start only viewer
cd build_kimi_viewer
python serve.py --port 8080
```

**Production Mode (Linux):**

```bash
sudo systemctl start aelma-bridge
sudo systemctl start aelma-twin
sudo systemctl start aelma-viewer
```

### Log Management

**Development Mode:**

```bash
# View logs
tail -f logs/bridge.log
tail -f logs/twin.log
tail -f logs/viewer.log

# Rotate logs
mv logs/bridge.log logs/bridge.log.1
```

**Production Mode (Linux):**

```bash
# View journal logs
sudo journalctl -u aelma-bridge -f
sudo journalctl -u aelma-twin -f
sudo journalctl -u aelma-viewer -f

# Configure log rotation
sudo vim /etc/logrotate.d/aelma
```

### Process Monitoring

```bash
# Check processes
ps aux | grep -E "bridge|twin|viewer"

# Check resource usage
top -p $(cat logs/pids/*.pid | tr '\n' ',' | sed 's/,$//')

# Check ports
netstat -tulpn | grep -E "8000|8001|8080|8090"
```

---

## Troubleshooting

### Common Issues

#### Port Already in Use

**Symptom:** Service fails to start with "port already in use" error.

**Solution:**
```bash
# Find process using port
sudo lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in .env
vim .env
```

#### Virtual Environment Issues

**Symptom:** Python modules not found.

**Solution:**
```bash
# Recreate venv
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Permission Denied

**Symptom:** Cannot create log directories or PID files.

**Solution:**
```bash
# Fix permissions
sudo chown -R $USER:$USER /opt/aelma
sudo chmod 755 /opt/aelma
sudo chown -R $USER:$USER /var/log/aelma
```

#### Service Won't Start

**Symptom:** Service starts but immediately stops.

**Solution:**
```bash
# Check logs
tail -f logs/*.log

# Or systemd journal
sudo journalctl -u aelma-bridge -n 50

# Try manual start
python -m bridge --debug
```

#### WebSocket Connection Failed

**Symptom:** Viewer cannot connect to twin or bridge.

**Solution:**
```bash
# Check firewall
sudo ufw allow 8000/tcp
sudo ufw allow 8001/tcp
sudo ufw allow 8080/tcp
sudo ufw allow 8090/tcp

# Check service status
./scripts/status.sh

# Verify URLs
curl -I http://localhost:8000
curl -I http://localhost:8090
```

### Debug Mode

Enable debug logging:

```bash
# Development
./scripts/start.sh

# Production (edit service file)
sudo vim /etc/systemd/system/aelma-bridge.service
# Add: --debug to ExecStart
sudo systemctl daemon-reload
sudo systemctl restart aelma-bridge
```

### Health Checks

```bash
# Check all endpoints
curl http://localhost:8080/        # Viewer
curl http://localhost:8000/        # Bridge WS
curl http://localhost:8090/        # Twin WS

# Run status check
./scripts/status.sh
```

### Recovery Procedures

**If all services fail:**

```bash
# Stop everything
./scripts/stop.sh

# Clear state
rm -rf logs/pids/*
rm -f data/*.db

# Restart
./scripts/start.sh
```

**If single service fails:**

```bash
# Identify failed service
./scripts/status.sh

# Restart individually
./scripts/stop.sh
./scripts/start.sh
```

---

## Security Hardening

### System Hardening

#### Create Dedicated User

```bash
# Create aelma user
sudo useradd -r -s /bin/false -d /var/lib/aelma aelma

# Set permissions
sudo chown -R aelma:aelma /opt/aelma
sudo chown -R aelma:aelma /var/log/aelma
sudo chown -R aelma:aelma /var/lib/aelma
```

#### Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 127.0.0.1 to any port 8000
sudo ufw allow from 127.0.0.1 to any port 8001
sudo ufw allow from 127.0.0.1 to any port 8080
sudo ufw allow from 127.0.0.1 to any port 8090

# For remote access (restrict IP)
sudo ufw allow from 192.168.1.0/24 to any port 8080
```

#### Systemd Security

Service files already include:
- `NoNewPrivileges=true`
- `PrivateTmp=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- `ReadWritePaths=` (restricted)

### Network Security

#### TLS/SSL Configuration

For production, use reverse proxy with TLS:

```nginx
# /etc/nginx/sites-available/aelma
server {
    listen 443 ssl http2;
    server_name vessel.example.com;

    ssl_certificate /etc/ssl/certs/aelma.crt;
    ssl_certificate_key /etc/ssl/private/aelma.key;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### WebSocket Secure (WSS)

```python
# Modify bridge to use WSS
# Use reverse proxy or certificate
```

### Data Protection

#### Encryption

```bash
# Encrypt sensitive data
sudo cryptsetup luksFormat /dev/sdX
sudo cryptsetup luksOpen /dev/sdX aelma_data
```

#### Backup

```bash
# Backup configuration
tar -czf aelma-backup-$(date +%Y%m%d).tar.gz \
    /opt/aelma \
    /var/lib/aelma \
    /etc/systemd/system/aelma-*.service

# Backup to remote
rsync -avz /opt/aelma user@backup-server:/backups/
```

### Audit Logging

```bash
# Enable auditd
sudo apt install auditd

# Configure audit rules
sudo vim /etc/audit/rules.d/aelma.rules
```

---

## Testing

### Running Deployment Tests

```bash
# Run all tests
python tests/deployment.test.py

# Or with pytest
pytest tests/deployment.test.py -v
```

### Test Coverage

Tests validate:
- Script existence and permissions
- Virtual environment setup
- Log directory creation
- Port availability
- Component imports
- Service file validity

### Manual Testing

```bash
# Test bridge
telnet localhost 8001
# Send: $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47

# Test twin WebSocket
wscat -c ws://localhost:8090

# Test viewer
curl http://localhost:8080/
```

### Integration Testing

```bash
# Start simulator
python -m build_claude.simulator.simulate --duration-min 1 --speedup 1

# Verify bridge receives data
tail -f logs/bridge.log | grep GPGGA

# Verify twin processes data
tail -f logs/twin.log

# Verify viewer displays data
curl http://localhost:8080/api/state
```

---

## Maintenance

### Updates

```bash
# Pull latest code
git pull origin main

# Update dependencies
source .venv/bin/activate
pip install --upgrade -r requirements.txt

# Restart services
./scripts/stop.sh
./scripts/start.sh
```

### Log Rotation

**Linux (logrotate):**

```bash
# /etc/logrotate.d/aelma
/var/log/aelma/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 aelma aelma
}
```

### Monitoring

```bash
# Monitor CPU/memory
htop -p $(cat logs/pids/*.pid | tr '\n' ',' | sed 's/,$//')

# Monitor disk space
df -h /opt/aelma
df -h /var/log/aelma

# Monitor network
iftop -i eth0 -f "port 8000 or port 8001 or port 8080 or port 8090"
```

### Backup Schedule

```bash
# Daily backup (cron)
0 2 * * * /opt/aelma/scripts/backup.sh

# Weekly full backup
0 3 * * 0 /opt/aelma/scripts/full-backup.sh
```

---

## Advanced Configuration

### Custom Ports

Edit `.env`:

```bash
BRIDGE_TCP_PORT=9001
BRIDGE_WS_PORT=9000
TWIN_VIEWER_PORT=9090
VIEWER_PORT=9080
```

### Remote Access

**Allow specific IP:**

```bash
sudo ufw allow from 192.168.1.100 to any port 8080
```

**VPN Tunnel:**

```bash
# SSH tunnel
ssh -L 8080:localhost:8080 user@vessel.example.com
```

### Multiple Instances

```bash
# Clone for vessel 2
cp -r aelma aelma-vessel2

# Modify ports
vim aelma-vessel2/.env

# Install
cd aelma-vessel2
./scripts/install.sh development
```

---

## Support

### Documentation

- README: `README.md`
- Schema: `schema/`
- Examples: `examples/`

### Issues

Report issues: https://github.com/SuperInstance/aelma/issues

### Logs

Provide logs when reporting issues:

```bash
./scripts/status.sh > status-report.txt
tar -czf logs.tar.gz logs/
```

---

## Appendix

### File Locations

**Development Mode:**
- AELMA: `<clone-dir>/`
- Venv: `<clone-dir>/.venv/`
- Logs: `<clone-dir>/logs/`
- Data: `<clone-dir>/data/`

**Production (Linux):**
- AELMA: `/opt/aelma/`
- Venv: `/opt/aelma/.venv/`
- Logs: `/var/log/aelma/`
- Data: `/var/lib/aelma/`
- Services: `/etc/systemd/system/aelma-*.service`

### Port Reference

| Port | Protocol | Component | Direction |
|------|----------|-----------|-----------|
| 8001 | TCP | Bridge (NMEA) | Inbound |
| 8000 | WebSocket | Bridge (telemetry) | Outbound |
| 8090 | WebSocket | Twin (viewer) | Outbound |
| 8080 | HTTP | Viewer (web) | Outbound |

### Default Credentials

AELMA does not use authentication by default. Implement authentication for production deployments.

### Version Compatibility

- Python 3.12+
- Linux kernel 4.15+
- macOS 10.15+
- Windows 10+

---

**Last Updated:** 2024-07-27
**Version:** 1.0.0
