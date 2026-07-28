# AELMA Phase 2 — Migration Guide

**Version:** 2.0.0
**Last Updated:** 2026-07-27
**For Users Upgrading From:** Phase 1

---

## Table of Contents

- [Overview](#overview)
- [What's New in Phase 2](#whats-new-in-phase-2)
- [Pre-Migration Checklist](#pre-migration-checklist)
- [Migration Steps](#migration-steps)
- [Configuration Changes](#configuration-changes)
- [Data Migration](#data-migration)
- [API Changes](#api-changes)
- [Breaking Changes](#breaking-changes)
- [Testing Your Migration](#testing-your-migration)
- [Rollback Plan](#rollback-plan)
- [Troubleshooting](#troubleshooting)

---

## Overview

This guide helps you upgrade from AELMA Phase 1 to Phase 2. Phase 2 is **backward compatible** with Phase 1 — all existing functionality continues to work, but new features are available.

### Migration Complexity

- **Time Required:** 15-30 minutes
- **Downtime:** None (can upgrade live)
- **Data Loss Risk:** Zero (append-only architecture)
- **Rollback:** Simple (git checkout)

### What Changes

- **New Components:** 8 new modules (watchers, A2A log, health, metrics, etc.)
- **New Endpoints:** `/health`, `/ready`, `/live`, `/metrics`
- **New UI:** Dashboard viewer at `dashboard.html`
- **Enhanced Protocol:** Action messages over WebSocket

### What Stays The Same

- **Core Protocol:** Telemetry packets unchanged
- **State Schema:** VesselState backward compatible
- **WebSocket Format:** VesselStateSnapshot unchanged
- **File Formats:** Bathymetry JSON unchanged
- **Dependencies:** Still stdlib-only (no new deps)

---

## What's New in Phase 2

### New Features

#### 1. Watcher-Based Alerting

**Phase 1:** No built-in alerting
**Phase 2:** Deterministic threshold rules with cooldown suppression

```python
# Add a shallow water warning
twin.add_watcher({
    "id": "shallow-water",
    "name": "Shallow water warning",
    "when": lambda f: f.get("depth_m", 999) < 2.0,
    "action": {
        "name": "raise_alert",
        "payload": lambda f: {"kind": "shallow_water", "depth": f["depth_m"]},
        "priority": lambda f: 0.85,
    },
    "cooldown_s": 30.0,
})
```

#### 2. A2A Action Logging

**Phase 1:** No action audit trail
**Phase 2:** Append-only log with full provenance

```json
{
  "kind": "action",
  "action": "raise_alert",
  "payload": {"kind": "shallow_water", "depth": 1.4},
  "source": "watcher",
  "reason": "depth=1.40m",
  "priority": 0.85,
  "ts": "2026-07-27T15:04:23.181000+00:00",
  "_loggedAt": "2026-07-27T15:04:23.204112+00:00",
  "_seq": 42
}
```

#### 3. Health Endpoints

**Phase 1:** No health monitoring
**Phase 2:** Kubernetes-ready health probes

```bash
curl http://localhost:8091/health
curl http://localhost:8091/ready
curl http://localhost:8091/live
```

#### 4. Prometheus Metrics

**Phase 1:** No metrics export
**Phase 2:** Prometheus text format at `/metrics`

```
# HELP aelma_packets_received_total Telemetry packets received
# TYPE aelma_packets_received_total counter
aelma_packets_received_total 1234
```

#### 5. Dashboard UI

**Phase 1:** 3D viewer only
**Phase 2:** Real-time dashboard with gauges, charts, alerts

```
http://localhost:8080/dashboard.html
```

#### 6. Signal K Support

**Phase 1:** NMEA 0183 only
**Phase 2:** NMEA 2000 via Signal K delta parsing

#### 7. Circuit Breaker

**Phase 1:** Basic retry logic
**Phase 2:** Circuit breaker pattern for resilience

#### 8. Historical Queries

**Phase 1:** Current state only
**Phase 2:** Time-range queries with aggregation

---

## Pre-Migration Checklist

### Before You Start

- [ ] **Review Phase 2 features** — Read `PHASE2_COMPLETE.md`
- [ ] **Check compatibility** — Verify your Python version (3.11+)
- [ ] **Backup data** — Copy bathymetry files (optional, safe upgrade)
- [ ] **Test environment** — Have a test vessel ready
- [ ] **Schedule window** — 15-30 minutes (no downtime required)

### System Requirements

**Phase 2 requirements are identical to Phase 1:**

- **Python:** 3.11 or later
- **OS:** Linux, macOS, or Windows
- **Memory:** 512 MB recommended
- **Disk:** 100 MB for logs + data
- **Network:** Local LAN only (air-gap capable)

### Dependencies

**No new dependencies!** Phase 2 remains stdlib-only:

```bash
# Phase 1 deps (still the same)
pip install websockets

# That's it! No new packages for Phase 2
```

---

## Migration Steps

### Step 1: Update Code

```bash
# Navigate to AELMA directory
cd /path/to/aelma

# Check current branch
git branch
git status

# Pull latest changes
git pull origin phase2

# Or checkout phase2 branch
git checkout phase2
```

### Step 2: Verify Installation

```bash
# Verify Python version
python --version  # Should be 3.11+

# Verify dependencies (still just websockets)
pip list | grep websockets

# Run tests to verify
python -m pytest
# Expected: 407 tests collected, 407 passed
```

### Step 3: Review Configuration

Phase 2 adds **optional** command-line arguments. Your existing commands still work:

```bash
# Phase 1 command (still works in Phase 2)
python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090

# Phase 2 command with new features (optional)
python -m twin \
    --bridge-url ws://localhost:8000 \
    --viewer-port 8090 \
    --health-port 8091 \
    --metrics-port 9090 \
    --a2a-log logs/a2a.jsonl \
    --bathymetry-path data/bathymetry.json
```

### Step 4: Start Phase 2 Services

```bash
# Terminal 1 — Bridge (unchanged)
cd aelma/bridge
python -m bridge --ws-port 8000 --tcp-port 8001

# Terminal 2 — Simulator (unchanged)
cd aelma/simulator
python -m simulator --duration-min 60 --speedup 10

# Terminal 3 — TwinCore with Phase 2 features
cd aelma/twin
python -m twin \
    --bridge-url ws://localhost:8000 \
    --viewer-port 8090 \
    --health-port 8091 \
    --metrics-port 9090

# Terminal 4 — Viewer (unchanged)
cd aelma/viewer
python serve.py --port 8080
```

### Step 5: Verify Phase 2 Features

```bash
# Check health endpoint
curl http://localhost:8091/health
# Expected: {"status": "healthy", ...}

# Check metrics endpoint
curl http://localhost:9090/metrics
# Expected: Prometheus text format

# Open dashboard
# http://localhost:8080/dashboard.html
```

### Step 6: Add Watcher Rules (Optional)

Create a watcher configuration file:

```python
# watchers.py
WATCHERS = [
    {
        "id": "shallow-water",
        "name": "Shallow water warning",
        "when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {"kind": "shallow_water", "depth": f["depth_m"]},
            "reason": lambda f: f"depth={f['depth_m']:.2f}m",
            "priority": lambda f: 0.85,
        },
        "cooldown_s": 30.0,
    },
    {
        "id": "high-speed",
        "name": "High speed alert",
        "when": lambda f: f.get("speed_kn", 0) > 10.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {"kind": "high_speed", "speed": f["speed_kn"]},
            "reason": lambda f: f"speed={f['speed_kn']:.1f}kn",
            "priority": lambda f: 0.7,
        },
        "cooldown_s": 60.0,
    },
]
```

Load watchers in your twin startup:

```python
from twin.core import TwinCore
from watchers import WATCHERS

twin = TwinCore(...)
for rule in WATCHERS:
    twin.add_watcher(rule)
```

---

## Configuration Changes

### Command-Line Arguments

#### New Arguments (All Optional)

| Argument | Default | Purpose |
|----------|---------|---------|
| `--health-port` | 8091 | HTTP health server port |
| `--metrics-port` | 9090 | Prometheus metrics port |
| `--a2a-log` | logs/a2a.jsonl | A2A log file path |
| `--bathymetry-path` | data/bathymetry.json | Bathymetry persistence path |
| `--memory-limit-mb` | 512.0 | Memory threshold for degraded health |

#### Phase 1 Arguments (Unchanged)

| Argument | Required | Purpose |
|----------|----------|---------|
| `--bridge-url` | Yes | Bridge WebSocket URL |
| `--viewer-port` | Yes | Viewer WebSocket port |

### Environment Variables

Phase 2 supports environment variables (new in Phase 2):

```bash
export AELMA_VESSEL_ID="FV-EILEEN"
export AELMA_BRIDGE_URL="ws://localhost:8000"
export AELMA_VIEWER_PORT="8090"
export AELMA_HEALTH_PORT="8091"
export AELMA_METRICS_PORT="9090"
export AELMA_A2A_LOG="logs/a2a.jsonl"
export AELMA_BATHYMETRY_PATH="data/bathymetry.json"
```

### Configuration Files

Phase 2 adds optional configuration file support:

```yaml
# aelma-config.yaml
vessel_id: "FV-EILEEN"
bridge_url: "ws://localhost:8000"
viewer_port: 8090
health_port: 8091
metrics_port: 9090
a2a_log: "logs/a2a.jsonl"
bathymetry_path: "data/bathymetry.json"
memory_limit_mb: 512.0

watchers:
  - id: "shallow-water"
    name: "Shallow water warning"
    threshold_m: 2.0
    cooldown_s: 30.0
```

Load configuration:

```bash
python -m twin --config aelma-config.yaml
```

---

## Data Migration

### Bathymetry Data

**No migration needed!** Bathymetry files are compatible:

```python
# Phase 1 format (still works)
{
  "voxels": [
    {"x": 0, "y": 0, "z": 73.2, "confidence": 0.9}
  ],
  "count": 1
}

# Phase 2 format (backward compatible)
{
  "voxels": [
    {"x": 0, "y": 0, "z": 73.2, "confidence": 0.9}
  ],
  "count": 1,
  "metadata": {
    "version": "2.0",
    "created_at": "2026-07-27T15:04:23Z"
  }
}
```

Phase 2 automatically adds metadata on first save, but reads Phase 1 files without issues.

### A2A Log

**New file, created automatically:**

```bash
# First time running Phase 2
# A2A log is created automatically
ls logs/a2a.jsonl  # Created if not exists
```

### State History

**Phase 1:** No built-in history
**Phase 2:** In-memory history (configurable size)

```python
twin = TwinCore(
    ...,
    history_size=1000  # Keep last 1000 state snapshots
)
```

History is **not persisted** by default — configure persistence if needed.

---

## API Changes

### TwinCore API

#### New Methods (Phase 2)

```python
# Add watcher rules
twin.add_watcher(rule) -> str

# Remove watcher rules
twin.remove_watcher(rule_id) -> bool

# Query A2A log
await twin.query_actions(...) -> list[dict]

# Query telemetry history
await twin.query_telemetry(...) -> dict

# Get health report
twin.health.health_report() -> (int, dict)

# Get metrics snapshot
twin.metrics.snapshot() -> dict
```

#### Unchanged Methods (Phase 1)

```python
await twin.start()
await twin.stop()
await twin.handle_packet(packet)
```

### WebSocket Protocol

#### Phase 1 Messages (Still Work)

```json
{"type": "state", "timestamp": 1234567890.123, "vessel_id": "FV-EILEEN", ...}
```

#### Phase 2 Additions (New)

```json
{"type": "action", "action": "raise_alert", "payload": {...}, "priority": 0.85}
```

Phase 2 clients should handle both message types. Phase 1 clients ignore unknown message types (safe).

### HTTP Endpoints

#### New Endpoints (Phase 2)

```bash
GET /health       # Overall health + components
GET /ready        # Readiness probe
GET /live         # Liveness probe
GET /metrics      # Prometheus metrics
```

---

## Breaking Changes

### Command-Line Changes

**None!** All Phase 1 commands work in Phase 2.

```bash
# This works in both phases
python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090
```

### Schema Changes

**None!** All Phase 1 schemas work in Phase 2.

```python
# Phase 1 VesselState (still works)
{
  "timestamp": 1234567890.123,
  "position": {"lat": 56.8, "lon": -135.3},
  "depth_m": 73.2
}

# Phase 2 VesselState (adds optional metadata)
{
  "timestamp": 1234567890.123,
  "position": {"lat": 56.8, "lon": -135.3},
  "depth_m": 73.2,
  "metadata": {  # Optional, backward compatible
    "source": "nmea0183",
    "quality": "good"
  }
}
```

### File Format Changes

**None!** All Phase 1 file formats read by Phase 2.

- Bathymetry JSON: Compatible
- Telemetry packets: Compatible
- WebSocket messages: Compatible

### Dependency Changes

**None!** Still stdlib-only.

```bash
# Phase 1 deps
pip install websockets

# Phase 2 deps (same!)
pip install websockets
```

---

## Testing Your Migration

### Smoke Tests

#### Test 1: Bridge Connection

```bash
# Terminal 1
python -m bridge --ws-port 8000 --tcp-port 8001

# Terminal 2
python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090

# Expected: Twin connects successfully
# Look for: "Connected to bridge"
```

#### Test 2: Health Endpoint

```bash
curl http://localhost:8091/health

# Expected: {"status": "healthy", "vessel_id": "...", ...}
```

#### Test 3: Metrics Endpoint

```bash
curl http://localhost:9090/metrics

# Expected: Prometheus text format
# aelma_packets_received_total 0
# aelma_websocket_connections 0
```

#### Test 4: Dashboard

```bash
# Open browser
http://localhost:8080/dashboard.html

# Expected: Dashboard loads, shows connection status
```

### Integration Tests

```bash
# Run full test suite
python -m pytest

# Expected: 407 tests collected, 407 passed
```

### Watcher Tests

```python
# Add a test watcher
twin.add_watcher({
    "id": "test-watcher",
    "name": "Test watcher",
    "when": lambda f: True,
    "action": {"name": "announce"},
    "cooldown_s": 10.0,
})

# Trigger it
# Expected: Action appears in dashboard
```

---

## Rollback Plan

### If Something Goes Wrong

#### Option 1: Revert to Phase 1

```bash
# Stop Phase 2 services
# (Ctrl+C in all terminals)

# Checkout Phase 1
git checkout phase1

# Restart Phase 1 services
python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090
```

#### Option 2: Disable Phase 2 Features

```bash
# Run Phase 2 code without Phase 2 features
python -m twin \
    --bridge-url ws://localhost:8000 \
    --viewer-port 8090
    # (omit health-port, metrics-port, etc.)
```

This runs Phase 2 code in Phase 1 compatibility mode.

### Data Safety

**No data loss risk:**

- Bathymetry: Append-only, safe rollback
- A2A log: New file, doesn't affect Phase 1
- State: In-memory,重建 on restart

### Backup Recommendations

Optional but recommended:

```bash
# Backup bathymetry before migration
cp data/bathymetry.json data/bathymetry.json.backup

# Backup any custom configurations
cp aelma-config.yaml aelma-config.yaml.backup
```

---

## Troubleshooting

### Common Issues

#### Issue: Health Port Already in Use

```bash
# Error: [Errno 48] Address already in use
# Solution: Use a different port
python -m twin --health-port 8092
```

#### Issue: Metrics Port Already in Use

```bash
# Error: [Errno 48] Address already in use
# Solution: Use a different port
python -m twin --metrics-port 9091
```

#### Issue: A2A Log Path Not Writable

```bash
# Error: Permission denied
# Solution: Create logs directory
mkdir -p logs
chmod 755 logs
```

#### Issue: Dashboard Not Connecting

```bash
# Check: TwinCore viewer server running
curl http://localhost:8090  # Should get WebSocket upgrade response

# Check: WebSocket URL in dashboard
# Open browser console, look for WebSocket errors
```

#### Issue: Watchers Not Firing

```python
# Check: Watcher rule syntax
# Make sure 'when' returns a boolean
when=lambda f: f.get("depth_m", 999) < 2.0  # Correct
when=lambda f: print(f.get("depth_m"))       # Wrong! Returns None

# Check: Action name is allowed
ALLOWED_ACTIONS = frozenset({
    "morph_to_hazard_mode",
    "morph_to_navigation_mode",
    "morph_to_engineering_mode",
    "highlight_waypoint",
    "raise_alert",
    "clear_alerts",
    "set_panel_focus",
    "announce",
})
```

### Getting Help

#### Documentation

- `PHASE2_COMPLETE.md` — Phase 2 overview
- `PHASE2_API_REFERENCE.md` — Complete API docs
- `README.md` — Project overview

#### Component Docs

- `docs/watcher_registry_guide.md` — Watcher system
- `docs/a2a_system.md` — A2A log and queries
- `docs/signalk_integration.md` — Signal K support
- `docs/deployment.md` — Production deployment

#### Debug Mode

```bash
# Enable debug logging
export AELMA_LOG_LEVEL=DEBUG

# Run with verbose output
python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090 --verbose
```

---

## Post-Migration Checklist

### After Migration

- [ ] **Verify health endpoint** — `curl http://localhost:8091/health`
- [ ] **Verify metrics endpoint** — `curl http://localhost:9090/metrics`
- [ ] **Open dashboard** — `http://localhost:8080/dashboard.html`
- [ ] **Add watcher rules** — Configure alert thresholds
- [ ] **Test alert delivery** — Trigger a watcher condition
- [ ] **Check A2A log** — Verify actions are logged
- [ ] **Run full test suite** — `python -m pytest`
- [ ] **Monitor performance** — Check memory usage
- [ ] **Update documentation** — Note any custom configurations
- [ ] **Train users** — Introduce dashboard and new features

### Optional Enhancements

- [ ] **Configure Prometheus** — Scrape metrics endpoint
- [ ] **Set up health monitoring** — Kubernetes probes
- [ ] **Create custom watchers** — Vessel-specific rules
- [ ] **Configure Signal K** — NMEA 2000 integration
- [ ] **Set up log rotation** — A2A log management
- [ ] **Backup automation** — Regular bathymetry backups

---

## Summary

### Migration Complexity

- **Difficulty:** Easy
- **Time:** 15-30 minutes
- **Downtime:** None
- **Risk:** Very low

### Key Points

1. **Backward Compatible** — All Phase 1 code works in Phase 2
2. **Optional Features** — New features are opt-in
3. **No Data Loss** — Append-only architecture
4. **Easy Rollback** — Simple git checkout
5. **Tested** — 407 tests ensure reliability

### What You Get

- **Alerting:** Watcher-based threshold rules
- **Audit Trail:** A2A log with full provenance
- **Health Monitoring:** Kubernetes-ready probes
- **Metrics:** Prometheus integration
- **Dashboard:** Real-time UI
- **Signal K:** NMEA 2000 support
- **Resilience:** Circuit breaker pattern
- **Queries:** Historical data access

---

**Migration Guide Version:** 2.0.0
**Last Updated:** 2026-07-27
**Status:** Production Ready
**Questions?** See `PHASE2_COMPLETE.md` and `PHASE2_API_REFERENCE.md`
